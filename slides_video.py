"""Slides-style promo video (kinetic typography) — brand-themed.

Mirrors the reference clip: bold sans-serif statements with ONE handwritten
script accent word, a glassy feature card that slides up over a brand gradient,
and a clean logo outro — all set to a soft music bed.

Pillow renders sprites; frames are piped to ffmpeg (no PNGs on disk). Requires
ffmpeg on PATH. This is the SECOND video type (slot :15 in each block); the
first video slot (:12) stays the AI-voice Blotato video.
"""

import math
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFilter

from images import font, _wrap

VW, VH = 1080, 1920          # vertical 9:16 (Reels / Shorts / TikTok)
FPS = 30
XF = 0.40                    # cross-fade between scenes (seconds)


def _ffmpeg_exe():
    """Path to an ffmpeg binary: the system one if it's on PATH, otherwise the
    binary bundled by the pip package `imageio-ffmpeg` (so it works on Windows
    with no manual install). Returns None only if neither is available."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def ffmpeg_ok():
    return _ffmpeg_exe() is not None



# --------------------------------------------------------------- easing
def _cl(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = _cl(x); return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = _cl(x)
    return 4 * x * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x):
    x = _cl(x); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


# --------------------------------------------------------------- theme
def vtheme(brand_key):
    import designs
    th = designs.THEME[brand_key]
    dark = tuple(int(c * 0.42) for c in th["base"])
    return dict(base=th["base"], base2=th["base2"], accent=th["accent"],
                accent_text=th["accent_text"], text=th["text"],
                cream=th["cream"], cream_text=th["cream_text"], soft=th["soft"],
                spectrum=th["spectrum"], name=th["name"], dark=dark)


# --------------------------------------------------------------- backgrounds
def _bg_solid(color):
    return Image.new("RGB", (VW, VH), color)


def _bg_gradient(c1, c2, glow=None):
    base = Image.new("RGB", (VW, VH), c1)
    d = ImageDraw.Draw(base)
    for y in range(VH):
        t = y / VH
        d.line([(0, y), (VW, y)], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    if glow:
        g = Image.new("L", (VW, VH), 0)
        ImageDraw.Draw(g).ellipse([int(VW * 0.1), int(VH * 0.05), int(VW * 0.9), int(VH * 0.5)], fill=70)
        g = g.filter(ImageFilter.GaussianBlur(160))
        base = Image.composite(Image.new("RGB", (VW, VH), glow), base, g)
    return base


# --------------------------------------------------------------- sprites
def _alpha(sprite, a):
    if a >= 0.999:
        return sprite
    s = sprite.copy()
    s.putalpha(s.split()[3].point(lambda p: int(p * _cl(a))))
    return s


def _paste(base, sprite, cx, cy, scale=1.0, alpha=1.0):
    """Paste an RGBA sprite centered at (cx, cy), scaled about its center."""
    if sprite is None:
        return
    w, h = sprite.size
    if scale != 1.0:
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        sprite = sprite.resize((nw, nh), Image.LANCZOS)
        w, h = nw, nh
    sprite = _alpha(sprite, alpha)
    base.alpha_composite(sprite, (int(cx - w / 2), int(cy - h / 2)))


def _line_sprite(words, base_f, acc_f, base_fill, acc_fill, accent_word, gap):
    """One centered text line, with the accent word drawn in the script font.
    Baselines are aligned across the two fonts. Returns a tight RGBA sprite."""
    probe = Image.new("RGBA", (8, 8)); pd = ImageDraw.Draw(probe)
    aw = (accent_word or "").lower().strip(",.!?")
    parts = []
    for wd in words:
        is_acc = aw and wd.lower().strip(",.!?") == aw
        f = acc_f if is_acc else base_f
        parts.append((wd, f, is_acc, pd.textlength(wd, font=f)))
    total = sum(p[3] for p in parts) + gap * (len(parts) - 1)
    asc = max(f.getmetrics()[0] for _, f, _, _ in parts)
    desc = max(f.getmetrics()[1] for _, f, _, _ in parts)
    h = asc + desc + 12
    spr = Image.new("RGBA", (int(total) + 8, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(spr); x = 0
    for wd, f, is_acc, ww in parts:
        a, _ = f.getmetrics()
        d.text((x, asc - a + 6), wd, font=f, fill=(acc_fill if is_acc else base_fill))
        x += ww + gap
    return spr.crop(spr.getbbox() or (0, 0, 1, 1))


def _block_sprites(lines, base_f, acc_f, base_fill, acc_fill, accent_word, gap):
    return [_line_sprite(ln.split(" "), base_f, acc_f, base_fill, acc_fill, accent_word, gap) for ln in lines]


def _fit_block(text, accent, base_weight, acc_weight, acc_ratio, max_w, start_px, min_px):
    """Wrap `text` to fit `max_w`, shrinking the font until every line fits.
    Returns (list_of_word_lists, base_font, accent_font, gap_px)."""
    probe = Image.new("RGBA", (8, 8)); pd = ImageDraw.Draw(probe)
    aw = (accent or "").lower().strip(",.!?")
    words = text.split()
    size = start_px
    while True:
        bf = font(size, base_weight); af = font(int(size * acc_ratio), acc_weight)
        gap = int(size * 0.26)

        def wlen(ws):
            w = sum(pd.textlength(wd, font=(af if aw and wd.lower().strip(",.!?") == aw else bf))
                    for wd in ws)
            return w + gap * (len(ws) - 1)
        lines, cur = [], []
        for wd in words:
            if not cur or wlen(cur + [wd]) <= max_w:
                cur.append(wd)
            else:
                lines.append(cur); cur = [wd]
        if cur:
            lines.append(cur)
        if size <= min_px or all(wlen(l) <= max_w for l in lines):
            return lines, bf, af, gap
        size -= 6


def _small_sprite(text, f, fill):
    probe = Image.new("RGBA", (8, 8)); w = ImageDraw.Draw(probe).textlength(text, font=f)
    a, dsc = f.getmetrics()
    spr = Image.new("RGBA", (int(w) + 8, a + dsc + 8), (0, 0, 0, 0))
    ImageDraw.Draw(spr).text((2, 2), text, font=f, fill=fill)
    return spr.crop(spr.getbbox() or (0, 0, 1, 1))


def _feature_card(th, title, bullets, button):
    """A glassy white product-style card (like the reference's UI card)."""
    cw, ch = int(VW * 0.78), int(VH * 0.40)
    card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    r = int(cw * 0.05)
    d.rounded_rectangle([0, 0, cw, ch], r, fill=(255, 255, 255, 255))
    # header row: brand chip + title
    pad = int(cw * 0.06)
    chip = int(ch * 0.10)
    d.rounded_rectangle([pad, pad, pad + chip, pad + chip], int(chip * 0.28), fill=th["base"])
    _ccx, _ccy, _ds = pad + chip / 2, pad + chip / 2, chip * 0.24
    d.polygon([(_ccx, _ccy - _ds), (_ccx + _ds, _ccy), (_ccx, _ccy + _ds), (_ccx - _ds, _ccy)], fill=th["accent"])
    tf = font(int(ch * 0.085), "extrabold")
    tx = pad + chip + int(cw * 0.04)
    avail = cw - pad - tx
    tsize = int(ch * 0.085)
    while tsize > int(ch * 0.05) and d.textlength(title, font=tf) > avail:
        tsize -= 3; tf = font(tsize, "extrabold")
    d.text((tx, pad + chip * 0.5 - tf.getmetrics()[0] * 0.5 + chip * 0.05), title, font=tf, fill=(20, 24, 30))
    # inner panel with bullets
    iy = pad + chip + int(ch * 0.06)
    d.rounded_rectangle([pad, iy, cw - pad, ch - int(ch * 0.20)], int(cw * 0.03), fill=(244, 246, 249, 255))
    bf = font(int(ch * 0.052), "semibold")
    by = iy + int(ch * 0.05)
    for b in bullets[:3]:
        cyr = by + int(ch * 0.03)
        r = int(ch * 0.022); left = pad + int(cw * 0.04); cxr = left + r
        d.ellipse([left, cyr - r, left + 2 * r, cyr + r], fill=th["base"])
        lw = max(3, int(r * 0.34))
        d.line([(cxr - r * 0.45, cyr + r * 0.02), (cxr - r * 0.05, cyr + r * 0.38),
                (cxr + r * 0.5, cyr - r * 0.4)], fill=(255, 255, 255), width=lw, joint="curve")
        d.text((pad + int(cw * 0.11), by), b, font=bf, fill=(40, 46, 54))
        by += int(ch * 0.085)
    # button pill
    bh = int(ch * 0.13); bw = cw - 2 * pad; bx = pad; bty = ch - int(ch * 0.16)
    d.rounded_rectangle([bx, bty, bx + bw, bty + bh], int(bh / 2), fill=th["base"])
    btf = font(int(bh * 0.42), "bold")
    tw = d.textlength(button, font=btf)
    d.text((bx + (bw - tw) / 2, bty + bh * 0.27), button, font=btf, fill=th["text"])
    # soft drop shadow baked into a larger sprite
    pad2 = 60
    out = Image.new("RGBA", (cw + pad2 * 2, ch + pad2 * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad2, pad2 + 14, pad2 + cw, pad2 + ch + 14], r, fill=(0, 0, 0, 120))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(34)))
    out.alpha_composite(card, (pad2, pad2))
    return out


def _logo(th):
    """Simple wordmark: a brand mark tile + brand name. Mark uses the spectrum
    for AutismWorks, gold diagonal for Agent Broker Coach."""
    name = th["name"]
    nf = font(int(VH * 0.052), "extrabold")
    tile = int(VH * 0.075)
    probe = Image.new("RGBA", (8, 8)); nw = ImageDraw.Draw(probe).textlength(name, font=nf)
    gap = int(VW * 0.025)
    a, dsc = nf.getmetrics()
    w = tile + gap + int(nw) + 8
    h = max(tile, a + dsc) + 8
    spr = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(spr)
    ty = (h - tile) // 2
    d.rounded_rectangle([0, ty, tile, ty + tile], int(tile * 0.22), fill=th["text"])
    if th["spectrum"]:
        import designs
        sw = tile / len(designs.SPECTRUM)
        for i, c in enumerate(designs.SPECTRUM):
            d.rectangle([int(tile * 0.18 + i * sw * 0.64), ty + int(tile * 0.22),
                         int(tile * 0.18 + (i + 1) * sw * 0.64), ty + int(tile * 0.78)], fill=c)
    else:
        d.polygon([(int(tile * 0.2), ty + int(tile * 0.8)), (int(tile * 0.8), ty + int(tile * 0.2)),
                   (int(tile * 0.8), ty + int(tile * 0.8))], fill=th["accent"])
    d.text((tile + gap, (h - (a + dsc)) // 2), name, font=nf, fill=th["text"])
    return spr.crop(spr.getbbox() or (0, 0, 1, 1))


# --------------------------------------------------------------- scenes
def _bg_for(th, style):
    """Background image for a statement scene, chosen by the look's style key."""
    if style == "cream":
        return _bg_solid(th["cream"]).convert("RGBA"), th["cream_text"]
    if style == "dark":
        return _bg_solid(th["dark"]).convert("RGBA"), th["text"]
    if style == "navy":
        return _bg_solid(th["base"]).convert("RGBA"), th["text"]
    if style == "grad":
        return _bg_gradient(th["base"], th["base2"]).convert("RGBA"), th["text"]
    if style == "glow":
        return _bg_gradient(th["base"], th["base2"], glow=th["base2"]).convert("RGBA"), th["text"]
    if style == "accent":
        return _bg_solid(th["accent"]).convert("RGBA"), th["accent_text"]
    # default
    return _bg_solid(th["cream"]).convert("RGBA"), th["cream_text"]


def _scene_statement(th, spec):
    # background: explicit spec["bg"] style wins; else legacy dark/cream toggle
    style = spec.get("bg") or ("dark" if spec.get("dark", False) else "cream")
    bg, base_fill = _bg_for(th, style)
    acc_fill = th["accent"] if style != "accent" else th["accent_text"]
    accent = spec.get("accent")
    align = spec.get("align", "center")
    mw = int(VW * (0.84 if align == "left" else 0.88))

    big_sprs = sub_sprs = body_sprs = []
    kick_spr = foot_spr = None
    big = spec.get("big")
    body = spec.get("text") or " ".join(spec.get("lines", []))
    sub = spec.get("sub")

    if big:
        wl, bf, af, gap = _fit_block(big, accent, "extrabold", "script", 1.26, mw, int(VH * 0.155), int(VH * 0.085))
        big_sprs = [_line_sprite(w, bf, af, base_fill, acc_fill, accent, gap) for w in wl]
        big_total = sum(s.height for s in big_sprs)
        if sub:
            wl2, bf2, _, gap2 = _fit_block(sub, None, "medium", "medium", 1.0, mw, int(VH * 0.052), int(VH * 0.034))
            sub_sprs = [_line_sprite(w, bf2, bf2, base_fill, base_fill, None, gap2) for w in wl2]
    elif body:
        wl, bf, af, gap = _fit_block(body, accent, "extrabold", "script", 1.28, mw, int(VH * 0.072), int(VH * 0.042))
        body_sprs = [_line_sprite(w, bf, af, base_fill, acc_fill, accent, gap) for w in wl]

    if spec.get("kicker"):
        kick_spr = _small_sprite(spec["kicker"].upper(), font(int(VH * 0.027), "bold"), acc_fill)
    if spec.get("footer"):
        foot_spr = _small_sprite(spec["footer"], font(int(VH * 0.023), "regular"), th["soft"])

    lm = int(VW * 0.08)   # left margin when align == "left"

    def _ax(s):
        return (lm + s.width / 2) if align == "left" else VW / 2

    def _stack(f, sprs, cy, t, stagger=0.1, lh=0.014):
        total = sum(s.height for s in sprs) + int(VH * lh) * (len(sprs) - 1)
        y = cy - total / 2
        for i, s in enumerate(sprs):
            a = ease_out(_cl((t - i * stagger) / 0.5))
            sc = 0.93 + 0.07 * ease_out_back(_cl((t - i * stagger) / 0.6))
            _paste(f, s, _ax(s), y + s.height / 2, sc, a)
            y += s.height + int(VH * lh)
        return total

    def fn(t):
        f = bg.copy()
        rise = (1 - ease_out(_cl(t / 0.6))) * VH * 0.03
        if big_sprs:
            if kick_spr is not None:
                ky = VH * 0.50 + rise - big_total / 2 - VH * 0.05
                _paste(f, kick_spr, _ax(kick_spr), ky, 1, ease_out(t / 0.55))
            bh = _stack(f, big_sprs, VH * 0.50 + rise, t, 0.08, 0.0)
            if sub_sprs:
                _stack(f, sub_sprs, VH * 0.50 + bh / 2 + VH * 0.06 + rise, t - 0.25, 0.08, 0.005)
        elif body_sprs:
            _stack(f, body_sprs, VH * 0.50 + rise, t, 0.12, 0.018)
        if foot_spr is not None:
            _paste(f, foot_spr, _ax(foot_spr), VH * 0.93, 1, ease_out(t / 0.55))
        return f.convert("RGB")
    return fn


def _scene_cards(th, spec):
    _cbg = spec.get("card_bg", "glow")
    if _cbg == "navy":
        bg = _bg_solid(th["base"]).convert("RGBA")
    elif _cbg == "grad":
        bg = _bg_gradient(th["base"], th["base2"]).convert("RGBA")
    elif _cbg == "dark":
        bg = _bg_solid(th["dark"]).convert("RGBA")
    else:
        bg = _bg_gradient(th["base"], th["base2"], glow=th["base2"]).convert("RGBA")
    accent = spec.get("accent")
    card = _feature_card(th, spec["title"], spec["bullets"], spec.get("button", "Learn more"))
    wl, bf, af, gap = _fit_block(spec.get("label", ""), accent, "extrabold", "script", 1.28,
                                 int(VW * 0.88), int(VH * 0.052), int(VH * 0.034))
    label_sprs = [_line_sprite(w, bf, af, th["text"], th["accent"], accent, gap) for w in wl]

    def fn(t):
        f = bg.copy()
        total = sum(s.height for s in label_sprs) + int(VH * 0.01) * (len(label_sprs) - 1)
        y = VH * 0.17 - total / 2
        for i, s in enumerate(label_sprs):
            a = ease_out(_cl((t - i * 0.1) / 0.5))
            _paste(f, s, VW / 2, y + s.height / 2, 1, a)
            y += s.height + int(VH * 0.01)
        cprog = ease_out(_cl((t - 0.25) / 0.7))
        cy = VH * 0.60 + (1 - cprog) * VH * 0.10
        _paste(f, card, VW / 2, cy, 0.96 + 0.04 * cprog, cprog)
        return f.convert("RGB")
    return fn


def _scene_outro(th, spec):
    bg = _bg_solid(th["dark"]).convert("RGBA")
    logo = _logo(th)
    tag_spr = _small_sprite(spec.get("tagline", ""), font(int(VH * 0.034), "semibold"), th["soft"])
    web_spr = _small_sprite(spec.get("website", ""), font(int(VH * 0.030), "medium"), th["accent"])

    def fn(t):
        f = bg.copy()
        a = ease_out(t / 0.5)
        _paste(f, logo, VW / 2, VH * 0.46, 0.9 + 0.1 * ease_out_back(_cl(t / 0.6)), a)
        _paste(f, tag_spr, VW / 2, VH * 0.46 + logo.height * 0.9, 1, ease_out(_cl((t - 0.3) / 0.5)))
        _paste(f, web_spr, VW / 2, VH * 0.56 + logo.height * 0.9, 1, ease_out(_cl((t - 0.5) / 0.5)))
        return f.convert("RGB")
    return fn


_SCENE = {"statement": _scene_statement, "cards": _scene_cards, "outro": _scene_outro}


# --------------------------------------------------------------- timeline
def _timeline(th, script):
    fns, starts = [], []
    s = 0.0
    for i, spec in enumerate(script):
        fns.append(_SCENE[spec["type"]](th, spec))
        starts.append(s)
        s += spec["dur"] - (XF if i < len(script) - 1 else 0)
    total = starts[-1] + script[-1]["dur"]
    durs = [spec["dur"] for spec in script]

    def frame(g):
        active = [i for i in range(len(fns)) if starts[i] <= g < starts[i] + durs[i]]
        if not active:
            active = [len(fns) - 1]
        if len(active) == 1:
            return fns[active[0]](g - starts[active[0]])
        i, j = active[0], active[1]
        a = fns[i](g - starts[i]); b = fns[j](g - starts[j])
        o0 = starts[j]; o1 = starts[i] + durs[i]
        w = ease_in_out((g - o0) / max(1e-6, (o1 - o0)))
        return Image.blend(a, b, w)
    return frame, total


# --------------------------------------------------------------- music
MUSIC_DIR = os.path.join(os.path.dirname(__file__), "assets", "music")


def _synth_track(dur, wav_path):
    """Synthesize an upbeat, produced-style promo track (kick + hats + bass +
    plucked chords), like modern SaaS/Kajabi-style promo music. Pure numpy ->
    WAV. Returns wav_path, or None if numpy is unavailable."""
    try:
        import numpy as np
    except Exception:
        return None
    sr = 48000
    n = int(dur * sr)
    t = np.arange(n) / sr
    bpm = 112.0
    beat = 60.0 / bpm                       # ~0.536s
    bar = 4 * beat
    # I–V–vi–IV in C: C, G, Am, F (one bar each, loops)
    chords = [
        (261.63, 329.63, 392.00, 130.81),   # C  (E G + C bass)
        (246.94, 293.66, 392.00, 98.00),    # G  (B D G + G bass)
        (220.00, 261.63, 329.63, 110.00),   # Am
        (261.63, 349.23, 440.00, 87.31),    # F  (C F A + F bass)
    ]

    def env(times, decay, length=None):
        """Sum of exponential-decay envelopes triggered at `times`."""
        out = np.zeros(n)
        for st in times:
            i0 = int(st * sr)
            if i0 >= n:
                continue
            i1 = n if length is None else min(n, i0 + int(length * sr))
            tt = np.arange(i1 - i0) / sr
            out[i0:i1] += np.exp(-tt / decay)
        return out

    nbars = int(np.ceil(dur / bar)) + 1
    kick_times = [b * bar + k * beat for b in range(nbars) for k in range(4)]
    hat_times = [b * bar + k * beat / 2 for b in range(nbars) for k in range(1, 8, 2)]

    # KICK: pitch-swept sine thump on every beat
    ke = env(kick_times, 0.10, 0.30)
    kick_phase = 2 * np.pi * (55 + 60 * np.exp(-t * 18)) * t
    kick = 0.9 * ke * np.sin(kick_phase)

    # HATS: short filtered-noise ticks on the offbeats
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n)
    noise = np.diff(noise, prepend=0.0)     # brighten (high-pass-ish)
    hats = 0.16 * env(hat_times, 0.025, 0.06) * noise

    music = kick + hats
    pump = 1.0 - 0.45 * env(kick_times, 0.09, 0.25).clip(0, 1)   # sidechain feel

    bass = np.zeros(n)
    pluck = np.zeros(n)
    pad = np.zeros(n)
    for b in range(nbars):
        f1, f2, f3, fb = chords[b % 4]
        s0, s1 = int(b * bar * sr), min(n, int((b + 1) * bar * sr))
        if s0 >= n:
            break
        tt = t[s0:s1]
        # BASS: eighth-note pulses on the root
        bt = [b * bar + k * beat / 2 for k in range(8)]
        be = env(bt, 0.11, 0.22)[s0:s1]
        bass[s0:s1] = 0.5 * be * (np.sin(2 * np.pi * fb * tt)
                                  + 0.35 * np.sin(2 * np.pi * fb * 2 * tt))
        # PLUCKS: chord-tone arpeggio on eighths
        for k in range(8):
            st = b * bar + k * beat / 2
            i0 = int(st * sr)
            if i0 >= n:
                continue
            i1 = min(n, i0 + int(0.30 * sr))
            td = np.arange(i1 - i0) / sr
            f = (f1, f2, f3)[k % 3]
            pluck[i0:i1] += 0.34 * np.exp(-td / 0.09) * (
                np.sin(2 * np.pi * f * td) + 0.4 * np.sin(2 * np.pi * f * 2 * td))
        # PAD: soft sustained chord under everything
        pad[s0:s1] = 0.10 * (np.sin(2 * np.pi * f1 * tt) + np.sin(2 * np.pi * f2 * tt)
                             + np.sin(2 * np.pi * f3 * tt))

    music = music + (bass + pluck + pad) * pump
    # gentle fades + peak normalize
    fade_n = int(min(1.0, dur / 6) * sr)
    music[:fade_n] *= np.linspace(0, 1, fade_n)
    music[-fade_n:] *= np.linspace(1, 0, fade_n)
    music = music / (np.max(np.abs(music)) + 1e-9) * 0.9
    pcm = (music * 32767).astype(np.int16)

    import wave
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return wav_path


def _pick_music(variant=0):
    """If the operator drops audio files in assets/music/, use them (rotating by
    variant). Returns a path or None (None -> synthesized music bed)."""
    try:
        files = sorted(f for f in os.listdir(MUSIC_DIR)
                       if f.lower().endswith((".mp3", ".m4a", ".wav", ".aac", ".ogg")))
    except Exception:
        return None
    if not files:
        return None
    return os.path.join(MUSIC_DIR, files[variant % len(files)])


def _build_audio(dur, out_path, music_file=None):
    """Use a provided track if present, else a synthesized upbeat promo track
    (kick/hats/bass/plucks). Loudness-normalized to a punchy social level.
    Returns out_path or None."""
    ff = _ffmpeg_exe()
    if not ff:
        return None
    fade = min(1.2, dur / 6)
    # punchy social loudness, then fade in/out
    norm = (f"loudnorm=I=-14:TP=-1.2:LRA=11,"
            f"afade=t=in:st=0:d={fade},afade=t=out:st={dur - fade:.2f}:d={fade}")
    tmp_wav = None
    if music_file and os.path.exists(music_file):
        cmd = [ff, "-y", "-stream_loop", "-1", "-i", music_file, "-t", f"{dur:.2f}",
               "-af", norm, "-ar", "48000",
               "-ac", "2", "-c:a", "aac", "-b:a", "160k", out_path]
    else:
        tmp_wav = out_path + ".synth.wav"
        made = _synth_track(dur, tmp_wav)
        if made:
            cmd = [ff, "-y", "-i", made, "-t", f"{dur:.2f}",
                   "-af", norm, "-ar", "48000",
                   "-ac", "2", "-c:a", "aac", "-b:a", "160k", out_path]
        else:
            # last-resort chord bed if numpy is somehow missing
            def chord(f1, f2, f3, f4):
                return (f"0.30*sin(2*PI*{f1}*t)+0.26*sin(2*PI*{f2}*t)"
                        f"+0.24*sin(2*PI*{f3}*t)+0.16*sin(2*PI*{f4}*t)")
            c0 = chord(130.81, 164.81, 196.00, 261.63)
            c1 = chord(110.00, 130.81, 164.81, 220.00)
            c2 = chord(87.31, 174.61, 220.00, 261.63)
            c3 = chord(98.00, 196.00, 246.94, 293.66)
            expr = (f"if(lt(mod(t,16),4),{c0},"
                    f"if(lt(mod(t,16),8),{c1},"
                    f"if(lt(mod(t,16),12),{c2},{c3})))")
            af = f"lowpass=f=2200,tremolo=f=2.1:d=0.35,{norm}"
            cmd = [ff, "-y", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=48000:d={dur:.2f}",
                   "-af", af, "-ac", "2", "-c:a", "aac", "-b:a", "160k", out_path]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path
    except Exception:
        return None
    finally:
        if tmp_wav:
            try:
                os.remove(tmp_wav)
            except OSError:
                pass


# --------------------------------------------------------------- render
def render(brand_key, out_path, variant=0, headline=None, music_file=None, script=None):
    """Render one brand slides video to out_path (mp4). Returns out_path."""
    ff = _ffmpeg_exe()
    if not ff:
        raise RuntimeError("ffmpeg not available (install with: pip install imageio-ffmpeg)")
    if music_file is None:
        music_file = _pick_music(variant)   # auto-use tracks dropped in assets/music/
    th = vtheme(brand_key)
    if script is None:
        script = default_script(brand_key, th, variant=variant, headline=headline)
    frame_at, total = _timeline(th, script)
    tmp = tempfile.mkdtemp(prefix="slides_")
    silent = os.path.join(tmp, "video.mp4")
    enc = subprocess.Popen(
        [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}",
         "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-profile:v", "high", "-level", "4.2", "-preset", "medium", "-crf", "18",
         "-x264-params", "keyint=60:min-keyint=30",
         "-movflags", "+faststart", silent],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    n = int(round(total * FPS))
    for k in range(n):
        enc.stdin.write(frame_at(k / FPS).tobytes())
    enc.stdin.close(); enc.wait()

    audio = _build_audio(total, os.path.join(tmp, "audio.m4a"), music_file)
    if audio:
        subprocess.run([ff, "-y", "-i", silent, "-i", audio, "-c:v", "copy",
                        "-c:a", "aac", "-shortest", "-movflags", "+faststart", out_path],
                       check=True, capture_output=True)
    else:
        shutil.copyfile(silent, out_path)
    shutil.rmtree(tmp, ignore_errors=True)
    return out_path


# --------------------------------------------------------------- design looks
# Each "look" is a distinct visual template: a different scene sequence, a
# different mix of backgrounds, and left/center alignment. Rotating looks across
# the run means consecutive videos never share the same design, while the script
# (built from a unique content post) means the content is never repeated either.
LOOKS = [
    {"name": "editorial",   "align": "center",
     "seq": [("hook", "cream"), ("line", "navy"), ("card", "glow"), ("line", "dark"), ("outro", None)]},
    {"name": "leftbold",    "align": "left",
     "seq": [("hook", "dark"), ("line", "cream"), ("card", "navy"), ("outro", None)]},
    {"name": "quote",       "align": "center",
     "seq": [("quote", "navy"), ("line", "cream"), ("card", "grad"), ("line", "dark"), ("outro", None)]},
    {"name": "gradleft",    "align": "left",
     "seq": [("hook", "grad"), ("line", "dark"), ("card", "glow"), ("outro", None)]},
    {"name": "stacked",     "align": "left",
     "seq": [("hook", "cream"), ("line", "navy"), ("line", "dark"), ("card", "navy"), ("outro", None)]},
    {"name": "quotecard",   "align": "center",
     "seq": [("quote", "dark"), ("card", "glow"), ("line", "cream"), ("outro", None)]},
    {"name": "navyhero",    "align": "center",
     "seq": [("hook", "navy"), ("line", "cream"), ("card", "dark"), ("line", "navy"), ("outro", None)]},
    {"name": "goldhero",    "align": "center",
     "seq": [("hook", "accent"), ("line", "navy"), ("card", "glow"), ("outro", None)]},
    {"name": "gradstack",   "align": "center",
     "seq": [("hook", "grad"), ("line", "cream"), ("line", "navy"), ("card", "grad"), ("outro", None)]},
]

# feature cards that rotate independently so the "card" scene also varies
CARD_BANK = [
    ("Follow-up, handled",   ["Daily priority call list", "Scripts that book appointments", "Nothing slips through"]),
    ("Your pipeline, organized", ["Know who to call today", "Say the right thing", "Track every lead"]),
    ("Coaching that shows up", ["Weekly game plans", "Real accountability", "Proven playbooks"]),
    ("The listing framework", ["A presentation you rehearse", "Price with confidence", "Handle every objection"]),
    ("Lead-gen that sticks",  ["One source, mastered", "Daily conversations", "Follow up till they buy"]),
    ("Your daily game plan",  ["Win your first two hours", "Time-block lead-gen", "Track what matters"]),
    ("Built for working agents", ["Been-there mentorship", "Systems, not theory", "Momentum every week"]),
    ("Turn talk into closings", ["A pipeline you trust", "Confidence on every call", "More listings won"]),
]

_STOP_ACCENT = {"the","a","an","and","or","of","to","for","in","on","is","are","your",
                "you","that","with","this","it","they","not","but","most","every"}


def _clean_body(text):
    """Drop the CTA/website tail from a post body, keep the substance."""
    t = " ".join((text or "").split())
    for cut in ("agentbrokercoach.com", "  ", "\n"):
        pass
    # remove trailing url
    t = t.replace("agentbrokercoach.com", "").strip()
    return t


def _sentences(text):
    import re
    parts = re.split(r"(?<=[.!?])\s+", _clean_body(text))
    return [p.strip() for p in parts if len(p.strip()) >= 8]


def _accent_word(line):
    for w in line.replace(",", " ").replace(".", " ").split():
        lw = w.lower().strip(",.!?'\"")
        if len(lw) >= 4 and lw not in _STOP_ACCENT:
            return lw
    return None


def script_from_post(brand_key, th, post, look, idx=0):
    """Build a unique video script from one content post, rendered in `look`."""
    web = {"agent_broker_coach": "agentbrokercoach.com",
           "autismworks": "autismworks.com"}.get(brand_key, "")
    headline = post.get("headline", "").strip()
    fb = (post.get("variants", {}).get("facebook", {}) or {}).get("text", "")
    sents = _sentences(fb) or _sentences(post.get("variants", {}).get("instagram", {}).get("text", ""))
    # pick body lines that aren't just the headline
    body_lines = [s for s in sents if s.rstrip(".!?").lower() != headline.rstrip(".!?").lower()]
    if not body_lines:
        body_lines = sents or [headline]
    align = look.get("align", "center")
    card_title, card_bullets = CARD_BANK[idx % len(CARD_BANK)]
    kicker = th["name"]
    li = 0
    script = []
    for role, bg in look["seq"]:
        if role == "hook":
            script.append({"type": "statement", "dur": 3.0, "big": headline, "sub": "",
                           "kicker": kicker, "footer": web, "bg": bg, "align": align})
        elif role == "quote":
            script.append({"type": "statement", "dur": 3.2, "lines": [body_lines[0]],
                           "accent": _accent_word(body_lines[0]), "footer": web,
                           "bg": bg, "align": align})
            li = max(li, 1)
        elif role == "line":
            ln = body_lines[li % len(body_lines)]; li += 1
            script.append({"type": "statement", "dur": 2.8, "lines": [ln],
                           "accent": _accent_word(ln), "footer": web,
                           "bg": bg, "align": align})
        elif role == "card":
            script.append({"type": "cards", "dur": 4.4, "label": headline,
                           "accent": _accent_word(headline) or None,
                           "title": card_title, "bullets": card_bullets,
                           "button": "Let's talk", "card_bg": bg or "glow"})
        elif role == "outro":
            script.append({"type": "outro", "dur": 3.4,
                           "tagline": "Coaching with Jody McNamer", "website": web})
    return script


# --------------------------------------------------------------- brand scripts
def default_script(brand_key, th, variant=0, headline=None):
    web = {"agent_broker_coach": "agentbrokercoach.com", "autismworks": "autismworks.com"}[brand_key]
    if brand_key == "agent_broker_coach":
        hooks = [("Most deals", "are lost in the follow-up"),
                 ("The deal", "is in the follow-up"),
                 ("Quiet months", "build loud years"),
                 ("Your next deal", "is already in your phone"),
                 ("Winging it", "is costing you listings"),
                 ("Consistency", "beats intensity every time"),
                 ("Your database", "is a deal machine"),
                 ("Talk to", "more people, close more deals"),
                 ("Boring reps", "build a real business"),
                 ("Referrals", "don't happen by accident"),
                 ("Your calendar", "is your income plan"),
                 ("Price it right", "or chase it down")]
        props = [("The call you are avoiding is the deal", "deal"),
                 ("Coaching from someone who still sells", "sells"),
                 ("Knowledge closes deals", "closes"),
                 ("Referrals do not happen by accident", "accident"),
                 ("Stop winging your listing presentation", "winging"),
                 ("Five follow-ups win the client", "five"),
                 ("Your next deal is in your phone", "phone"),
                 ("Systems beat hustle every time", "systems"),
                 ("Show up on the boring days", "boring"),
                 ("Serve first, sell second", "serve"),
                 ("Small daily reps compound", "compound"),
                 ("Confidence is built on preparation", "preparation")]
        cards = [("A system that does the chasing", "chasing", "Follow-up, handled",
                  ["Daily priority call list", "Scripts that book appointments", "Nothing slips through"]),
                 ("Turn conversations into closings", "closings", "Your pipeline, organized",
                  ["Know who to call today", "Say the right thing", "Track every lead"]),
                 ("Built for agents who mean it", "mean it", "Coaching that shows up",
                  ["Weekly game plans", "Real accountability", "Proven playbooks"]),
                 ("Win more listings", "listings", "The listing framework",
                  ["A presentation you rehearse", "Price with confidence", "Handle every objection"]),
                 ("Fill your pipeline", "pipeline", "Lead-gen that sticks",
                  ["One source, mastered", "Daily conversations", "Follow up till they buy"]),
                 ("Build the habits that pay", "habits", "Your daily game plan",
                  ["Win your first two hours", "Time-block lead-gen", "Track what matters"])]
        big, sub = hooks[variant % len(hooks)]
        if headline:
            big, sub = headline, ""
        p1 = props[variant % len(props)]
        p2 = props[(variant + 2) % len(props)]
        clabel, caccent, ctitle, cbul = cards[(variant * 2 + 1) % len(cards)]
        return [
            {"type": "statement", "dur": 3.2, "big": big, "sub": sub, "kicker": th["name"],
             "footer": web},
            {"type": "statement", "dur": 3.2, "lines": [p1[0]], "accent": p1[1], "footer": web},
            {"type": "cards", "dur": 5.0, "label": clabel, "accent": caccent, "title": ctitle,
             "bullets": cbul, "button": "Let's talk"},
            {"type": "statement", "dur": 3.2, "lines": [p2[0]], "accent": p2[1], "dark": True,
             "footer": web},
            {"type": "outro", "dur": 3.8, "tagline": "Coaching with Jody McNamer", "website": web},
        ]
    else:
        hooks = [("Your kid", "belongs in the workforce"),
                 ("Talent", "is everywhere"),
                 ("A prism", "not a puzzle")]
        props = [("Not despite autism. Because of strengths", "strengths"),
                 ("A prism, not a puzzle", "prism"),
                 ("Opportunity should match the talent", "talent")]
        big, sub = hooks[variant % len(hooks)]
        if headline:
            big, sub = headline, ""
        p1 = props[variant % len(props)]
        p2 = props[(variant + 1) % len(props)]
        return [
            {"type": "statement", "dur": 3.2, "big": big, "sub": sub, "kicker": th["name"],
             "footer": web},
            {"type": "statement", "dur": 3.2, "lines": [p1[0]], "accent": p1[1], "footer": web},
            {"type": "cards", "dur": 5.0, "label": "Strengths-first, person-first",
             "accent": "person", "title": "How AutismWorks helps",
             "bullets": ["Match real skills to real roles", "Coaching that actually sticks",
                         "Inclusive, ready workplaces"], "button": "Learn more"},
            {"type": "statement", "dur": 3.2, "lines": [p2[0]], "accent": p2[1], "dark": True,
             "footer": web},
            {"type": "outro", "dur": 3.8, "tagline": "Strengths-first employment", "website": web},
        ]
