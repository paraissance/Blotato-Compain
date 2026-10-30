"""Brand-aware premium design system (portrait 1080x1350).

Agent Broker Coach: navy/gold, 5 Jody cut-out designs + 3 simple + 4 photo.
AutismWorks: deep teal + spectrum (prism-not-puzzle), 6 simple + 6 photo.

Photo posts use a duotone brand treatment + graphic overlays so they look
designed, never like a plain stock photo. Each recipe is a distinct structure.
"""

import glob
import math
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from images import font, _wrap
from photos import _cover, _rounded, fetch_photo

W, H = 1080, 1350
WHITE = (255, 255, 255)

# --- Agent Broker Coach palette
NAVY = (11, 37, 69)
NAVY2 = (18, 56, 100)
GOLD = (242, 183, 5)
CREAM = (244, 238, 224)

# --- AutismWorks palette (prism, not puzzle)
TEAL = (94, 200, 209)
TEAL_D = (15, 58, 70)
TEAL_D2 = (22, 84, 100)
AW_CREAM = (238, 247, 246)
SPECTRUM = [(94, 200, 209), (116, 206, 150), (245, 205, 95), (242, 150, 110), (196, 130, 186)]

THEME = {
    "agent_broker_coach": dict(
        base=NAVY, base2=NAVY2, accent=GOLD, accent_text=NAVY, text=WHITE,
        cream=CREAM, cream_text=NAVY, soft=(220, 228, 240),
        name="Jody McNamer", role="Agent Broker Coach", badge="TOP COACH",
        tip="COACHING TIP", cta="LET'S TALK", duo_dark=(8, 22, 46), duo_light=(150, 180, 222),
        spectrum=False, icon="house"),
    "autismworks": dict(
        base=TEAL_D, base2=TEAL_D2, accent=TEAL, accent_text=(8, 32, 40), text=WHITE,
        cream=AW_CREAM, cream_text=TEAL_D, soft=(205, 232, 232),
        name="AutismWorks", role="Strengths-first employment", badge="STRENGTHS FIRST",
        tip="DID YOU KNOW", cta="LEARN MORE", duo_dark=(8, 34, 44), duo_light=(150, 214, 214),
        spectrum=True, icon="spark"),
}


# ----------------------------------------------------------------- helpers
def _fitw(d, text, max_w, max_h, start, floor, weight="extrabold", lhf=0.16):
    # Shrink the headline until the whole block fits inside (max_w x max_h).
    # Guaranteed fit: keeps stepping down (finer step, lower hard floor) so the
    # text can never overrun its zone and collide with the elements below it.
    hard_floor = max(20, int(floor * 0.66))
    size = start
    while size >= hard_floor:
        f = font(size, weight)
        lines = _wrap(d, text, f, max_w)
        lh = f.getbbox("Ag")[3] + int(size * lhf)
        if lh * len(lines) <= max_h:
            return f, lines, lh
        size -= 2
    # Last resort: floor font + tightened leading so it still fits the box.
    f = font(hard_floor, weight)
    lines = _wrap(d, text, f, max_w)
    lh = f.getbbox("Ag")[3] + int(hard_floor * lhf)
    if len(lines) > 1 and lh * len(lines) > max_h:
        lh = max(f.getbbox("Ag")[3], int(max_h / len(lines)))
    return f, lines, lh


def _tb(d, x, y, lines, f, lh, fill):
    for ln in (lines if isinstance(lines, list) else [lines]):
        d.text((x, y), ln, font=f, fill=fill); y += lh
    return y


def _grad(c1, c2):
    base = Image.new("RGB", (W, H), c1)
    d = ImageDraw.Draw(base)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    return base


def _cover_p(img):
    w, h = img.size
    s = max(W / w, H / h)
    img = img.resize((max(W, int(w * s) + 1), max(H, int(h * s) + 1)))
    w, h = img.size
    return img.crop(((w - W) // 2, int((h - H) * 0.18), (w - W) // 2 + W, int((h - H) * 0.18) + H))


_YUNET_PATH = os.path.join(os.path.dirname(__file__), "assets", "face_detection_yunet.onnx")
_yunet = None  # lazy-loaded detector


def _faces_yunet(rgb):
    """Modern, accurate face boxes via OpenCV YuNet (handles tilts/profiles).
    Returns a list of (x,y,w,h), [] if it ran but found none, or None if
    YuNet/the model isn't available (so the caller can fall back to Haar)."""
    global _yunet
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    if not hasattr(cv2, "FaceDetectorYN") or not os.path.exists(_YUNET_PATH):
        return None
    try:
        bgr = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
        h, w = bgr.shape[:2]
        if _yunet is None:
            _yunet = cv2.FaceDetectorYN.create(_YUNET_PATH, "", (w, h), 0.6, 0.3, 5000)
        _yunet.setInputSize((w, h))
        _, faces = _yunet.detect(bgr)
        if faces is None:
            return []
        return [(int(f[0]), int(f[1]), int(f[2]), int(f[3])) for f in faces]
    except Exception:
        return None


def _faces_haar(rgb):
    """Fallback face boxes via Haar cascades (used only if YuNet is missing)."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    try:
        gray = cv2.equalizeHist(cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2GRAY))
        cdir = cv2.data.haarcascades
        boxes = []
        mn = max(24, int(min(rgb.size) * 0.05))
        for name in ("haarcascade_frontalface_default.xml",
                     "haarcascade_frontalface_alt2.xml",
                     "haarcascade_frontalface_alt.xml"):
            clf = cv2.CascadeClassifier(cdir + name)
            if not clf.empty():
                for b in clf.detectMultiScale(gray, 1.1, 5, minSize=(mn, mn)):
                    boxes.append(tuple(int(v) for v in b))
        prof = cv2.CascadeClassifier(cdir + "haarcascade_profileface.xml")
        if not prof.empty():
            gw = gray.shape[1]
            for (x, y, w, h) in prof.detectMultiScale(gray, 1.1, 4, minSize=(mn, mn)):
                boxes.append((int(x), int(y), int(w), int(h)))
            for (x, y, w, h) in prof.detectMultiScale(cv2.flip(gray, 1), 1.1, 4, minSize=(mn, mn)):
                boxes.append((int(gw - x - w), int(y), int(w), int(h)))   # map back from mirror
        return boxes
    except Exception:
        return None


def _face_mask(img):
    """Feathered L-mode mask (white = face) for any faces in `img`, or None if
    no detector/faces. Used to keep the brand color overlay OFF people's faces."""
    rgb = img.convert("RGB")
    boxes = _faces_yunet(rgb)
    if boxes is None:                 # YuNet unavailable -> try Haar
        boxes = _faces_haar(rgb)
    if not boxes:
        return None
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    for (x, y, w, h) in boxes:
        ex, ey = int(w * 0.38), int(h * 0.55)   # cover hair/forehead/chin too
        md.ellipse([x - ex, y - ey, x + w + ex, y + h + ey], fill=255)
    return mask.filter(ImageFilter.GaussianBlur(int(min(img.size) * 0.03)))


def _duotone(img, dark, light, face_mask="auto"):
    # Photos now render CLEAR and natural (no navy/blue wash) — just a gentle polish
    # for a professional look. Brand color comes from the card framing (panels,
    # headline, gold accents), not from a tint over the photo. Name kept so the
    # recipes don't need to change.
    im = img.convert("RGB")
    im = ImageOps.autocontrast(im, cutoff=0.5)
    im = ImageEnhance.Color(im).enhance(1.08)      # a touch more vivid
    im = ImageEnhance.Contrast(im).enhance(1.04)
    im = ImageEnhance.Brightness(im).enhance(1.02)
    w, h = im.size
    # very light vignette for depth — the photo stays clearly visible
    vig = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vig).ellipse([-int(w * 0.22), -int(h * 0.18), int(w * 1.22), int(h * 1.18)], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(int(min(w, h) * 0.18)))
    darkened = Image.blend(im, Image.new("RGB", (w, h), (0, 0, 0)), 0.12)
    return Image.composite(im, darkened, vig)


def _scrim(base_rgba, color, start=0.45, alpha=240, face_mask=None):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    top = int(H * start)
    for y in range(top, H):
        t = (y - top) / max(1, (H - top))
        d.line([(0, y), (W, y)], fill=(color[0], color[1], color[2], int(alpha * t)))
    if face_mask is not None:
        from PIL import ImageChops
        a = ov.split()[3]
        fm = face_mask if face_mask.size == a.size else face_mask.resize(a.size)
        keep = ImageOps.invert(fm)                 # full scrim where there's NO face
        reduced = ImageChops.multiply(a, keep)     # ~no scrim over faces
        a2 = Image.blend(reduced, a, 0.30)         # leave ~30% so text still reads
        ov.putalpha(a2)
    return Image.alpha_composite(base_rgba, ov)


def _cut(path, target_h):
    im = Image.open(path).convert("RGBA")
    bb = im.split()[3].getbbox()
    if bb:
        im = im.crop(bb)
    return im.resize((int(target_h * im.width / im.height), target_h))


def _place_cutout(base, cut_im, foot_cx, glow=True):
    x = int(foot_cx - cut_im.width / 2); y = H - cut_im.height
    if glow:
        halo = Image.new("RGBA", (W, H), (0, 0, 0, 0)); hd = ImageDraw.Draw(halo)
        rx = int(cut_im.width * 0.62); ry = int(cut_im.height * 0.55); cy = int(H * 0.42)
        hd.ellipse([foot_cx - rx, cy - ry, foot_cx + rx, cy + ry], fill=(255, 255, 255, 26))
        base.alpha_composite(halo.filter(ImageFilter.GaussianBlur(90)))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
    sw = int(cut_im.width * 0.5)
    sd.ellipse([foot_cx - sw, H - int(H * 0.05), foot_cx + sw, H], fill=(0, 0, 0, 150))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(28)))
    fig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sil = Image.new("RGBA", cut_im.size, (0, 0, 0, 0)); sil.putalpha(cut_im.split()[3])
    fig.paste(Image.new("RGBA", cut_im.size, (0, 0, 0, 110)), (x + 14, y + 8), sil)
    base.alpha_composite(fig.filter(ImageFilter.GaussianBlur(18)))
    base.alpha_composite(cut_im, (x, y))


def _dotgrid(d, x, y, cols, rows, gap, r, c):
    for i in range(cols):
        for j in range(rows):
            d.ellipse([x + i * gap, y + j * gap, x + i * gap + r, y + j * gap + r], fill=c)


def _quote(d, x, y, s, c):
    for k in (0, int(s * 0.62)):
        d.ellipse([x + k, y, x + k + int(s * 0.42), y + int(s * 0.42)], fill=c)
        d.polygon([(x + k, y + int(s * 0.28)), (x + k + int(s * 0.30), y + int(s * 0.28)),
                   (x + k, y + int(s * 0.74))], fill=c)


def _stars(d, x, y, n, R, color):
    for s in range(n):
        cx = x + s * int(R * 2.4) + R; cy = y + R; pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rr = R if i % 2 == 0 else R * 0.42
            pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
        d.polygon(pts, fill=color)


def _spectrum_bar(d, x, y, w, h, rnd=True):
    n = len(SPECTRUM)
    for i in range(w):
        t = i / max(1, w - 1) * (n - 1); k = int(t); f = t - k
        a = SPECTRUM[k]; b = SPECTRUM[min(k + 1, n - 1)]
        d.line([(x + i, y), (x + i, y + h)], fill=tuple(int(a[j] + (b[j] - a[j]) * f) for j in range(3)))
    if rnd:
        d.ellipse([x - h // 2, y, x + h // 2, y + h], fill=SPECTRUM[0])
        d.ellipse([x + w - h // 2, y, x + w + h // 2, y + h], fill=SPECTRUM[-1])


def _icon(d, kind, cx, y, w, c, bg):
    if kind == "house":
        half = w / 2; roof = w * 0.45
        d.polygon([(cx - half, y + roof), (cx, y), (cx + half, y + roof)], fill=c)
        d.rectangle([cx - w * 0.33, y + roof, cx + w * 0.33, y + w], fill=c)
        d.rectangle([cx - w * 0.09, y + w * 0.6, cx + w * 0.09, y + w], fill=bg)
    else:  # spark / prism
        for a in range(0, 360, 45):
            r = math.radians(a)
            d.line([(cx, y + w / 2), (cx + w / 2 * math.cos(r), y + w / 2 + w / 2 * math.sin(r))], fill=c, width=5)
        d.ellipse([cx - w * 0.16, y + w * 0.34, cx + w * 0.16, y + w * 0.66], fill=c)


def _phone(d, x, y, s, c):
    d.ellipse([x, y + s * 0.55, x + s * 0.3, y + s * 0.85], fill=c)
    d.ellipse([x + s * 0.6, y, x + s * 0.9, y + s * 0.3], fill=c)
    d.line([(x + s * 0.2, y + s * 0.68), (x + s * 0.72, y + s * 0.16)], fill=c, width=max(2, int(s * 0.16)))


def _pill(d, x, y, label, fh, fg, bg):
    f = font(fh, "bold"); w = int(d.textlength(label, font=f))
    d.rounded_rectangle([x, y, x + w + int(W * 0.07), y + int(fh * 1.8)], int(fh * 0.9), fill=bg)
    d.text((x + int(W * 0.035), y + int(fh * 0.4)), label, font=f, fill=fg)
    return y + int(fh * 1.8)


def _btn(d, x, y, label, fh, fg, bg, w=None):
    f = font(fh, "bold"); tw = int(d.textlength(label, font=f))
    bw = w or tw + int(W * 0.08)
    d.rectangle([x, y, x + bw, y + int(fh * 1.9)], fill=bg)
    d.text((x + (bw - tw) // 2, y + int(fh * 0.42)), label, font=f, fill=fg)
    return y + int(fh * 1.9)


def _badge(d, x, y, label, fh, t):
    f = font(fh, "bold"); lw = d.textlength(label, font=f); R = int(fh * 0.34)
    tw = lw + 5 * int(R * 2.4) + W * 0.05
    d.rounded_rectangle([x, y, x + tw, y + int(fh * 1.9)], int(fh * 0.4), fill=t["accent"])
    d.text((x + int(W * 0.02), y + int(fh * 0.45)), label, font=f, fill=t["accent_text"])
    _stars(d, int(x + int(W * 0.02) + lw + int(W * 0.018)), int(y + fh * 0.62), 5, R, t["accent_text"])
    return y + int(fh * 1.9)


def _contact(d, x, y, web, phone, c, accent, fh=None):
    fh = fh or int(H * 0.022)
    if phone:
        _phone(d, x, y, int(fh * 1.3), accent)
        d.text((x + int(fh * 1.7), y), phone, font=font(fh, "semibold"), fill=c); y += int(fh * 1.9)
    d.text((x, y), web, font=font(int(fh * 0.92), "regular"), fill=c)


# ----------------------------------------------------------------- JODY (ABC only)
def jody_spotlight(t, cut, brand, head, web, out, name, role, phone):
    base = _grad(t["base"], t["base2"]).convert("RGBA")
    c = _cut(cut, int(H * 0.98)); _place_cutout(base, c, int(W * 0.74))
    d = ImageDraw.Draw(base); tx = int(W * 0.06); tw = int(W * 0.45)
    _dotgrid(d, tx, int(H * 0.05), 6, 3, int(W * 0.028), int(W * 0.011), t["accent"])
    _badge(d, tx, int(H * 0.135), t["badge"], int(H * 0.020), t)
    _quote(d, tx, int(H * 0.205), int(H * 0.06), t["accent"])
    f, ls, lh = _fitw(d, head, tw, H * 0.24, int(H * 0.046), int(H * 0.030))
    y = _tb(d, tx, int(H * 0.27), ls, f, lh, t["text"])
    d.line([(tx, y + 14), (tx + int(tw * 0.5), y + 14)], fill=t["accent"], width=4)
    _btn(d, tx, int(H * 0.62), "CALL ME NOW", int(H * 0.022), t["accent_text"], t["text"])
    nf, nl, nlh = _fitw(d, name.upper(), tw, H * 0.12, int(H * 0.044), int(H * 0.030), "black", 0.10)
    ny = _tb(d, tx, int(H * 0.72), nl, nf, nlh, t["text"])
    d.text((tx, ny + 4), role, font=font(int(H * 0.022), "medium"), fill=t["accent"])
    _contact(d, tx, ny + int(H * 0.05), web, phone, t["soft"], t["accent"])
    base.convert("RGB").save(out, "PNG"); return out


def jody_band(t, cut, brand, head, web, out, name, role, phone):
    base = _grad(t["base"], t["base2"]).convert("RGBA"); d = ImageDraw.Draw(base)
    d.polygon([(0, int(H * 0.18)), (int(W * 0.40), 0), (int(W * 0.52), 0), (int(W * 0.12), H), (0, H)], fill=t["accent"])
    c = _cut(cut, int(H * 0.94)); _place_cutout(base, c, int(W * 0.27), glow=False)
    d = ImageDraw.Draw(base); tx = int(W * 0.52); tw = W - tx - int(W * 0.06)
    _badge(d, tx, int(H * 0.07), t["badge"], int(H * 0.020), t)
    _quote(d, tx, int(H * 0.145), int(H * 0.06), t["accent"])
    f, ls, lh = _fitw(d, head, tw, H * 0.28, int(H * 0.046), int(H * 0.030))
    y = _tb(d, tx, int(H * 0.22), ls, f, lh, t["text"])
    d.line([(tx, y + 14), (tx + int(tw * 0.5), y + 14)], fill=t["accent"], width=4)
    d.text((tx, int(H * 0.64)), name, font=font(int(H * 0.040), "black"), fill=t["text"])
    d.text((tx, int(H * 0.685)), role, font=font(int(H * 0.022), "medium"), fill=t["accent"])
    _btn(d, tx, int(H * 0.74), "CALL NOW", int(H * 0.024), t["accent_text"], t["accent"])
    _contact(d, tx, int(H * 0.86), web, phone, t["soft"], t["accent"])
    base.convert("RGB").save(out, "PNG"); return out


def jody_badge(t, cut, brand, head, web, out, name, role, phone):
    base = _grad(t["base2"], t["base"]).convert("RGBA"); d = ImageDraw.Draw(base)
    _pill(d, int(W * 0.06), int(H * 0.06), brand.upper(), int(H * 0.020), t["accent_text"], t["accent"])
    f, ls, lh = _fitw(d, head, int(W * 0.88), H * 0.20, int(H * 0.050), int(H * 0.032))
    _tb(d, int(W * 0.06), int(H * 0.15), ls, f, lh, t["text"])
    c = _cut(cut, int(H * 0.64)); _place_cutout(base, c, W // 2)
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(band).rectangle([0, int(H * 0.88), W, H], fill=(t["base"][0], t["base"][1], t["base"][2], 225))
    base = Image.alpha_composite(base, band); d = ImageDraw.Draw(base)
    d.rectangle([0, int(H * 0.88), W, int(H * 0.882) + 5], fill=t["accent"])
    d.text((int(W * 0.06), int(H * 0.905)), name, font=font(int(H * 0.030), "black"), fill=t["text"])
    cy = int(H * 0.945)
    if phone:
        _phone(d, int(W * 0.06), cy, int(H * 0.028), t["accent"])
        d.text((int(W * 0.06) + int(H * 0.04), cy), phone, font=font(int(H * 0.024), "semibold"), fill=t["text"])
    d.text((W - int(W * 0.40), int(H * 0.93)), web, font=font(int(H * 0.020), "regular"), fill=t["soft"])
    base.convert("RGB").save(out, "PNG"); return out


def jody_diagonal(t, cut, brand, head, web, out, name, role, phone):
    base = _grad(t["base"], t["base2"]).convert("RGBA"); d = ImageDraw.Draw(base)
    d.polygon([(0, 0), (int(W * 0.46), 0), (int(W * 0.34), H), (0, H)], fill=t["accent"])
    c = _cut(cut, int(H * 0.92)); _place_cutout(base, c, int(W * 0.74), glow=False)
    d = ImageDraw.Draw(base); tx = int(W * 0.06); tw = int(W * 0.32)
    d.text((tx, int(H * 0.07)), brand.upper(), font=font(int(H * 0.022), "bold"), fill=t["accent_text"])
    _quote(d, tx, int(H * 0.13), int(H * 0.06), t["accent_text"])
    f, ls, lh = _fitw(d, head, tw, H * 0.30, int(H * 0.040), int(H * 0.028))
    _tb(d, tx, int(H * 0.22), ls, f, lh, t["accent_text"])
    d.text((tx, int(H * 0.62)), name, font=font(int(H * 0.034), "black"), fill=t["accent_text"])
    d.text((tx, int(H * 0.662)), role, font=font(int(H * 0.020), "semibold"), fill=(70, 55, 5))
    _btn(d, tx, int(H * 0.72), "CALL ME NOW", int(H * 0.020), t["text"], t["base"])
    cy = int(H * 0.82)
    if phone:
        _phone(d, tx, cy, int(H * 0.026), t["accent_text"])
        d.text((tx + int(H * 0.038), cy), phone, font=font(int(H * 0.022), "semibold"), fill=t["accent_text"]); cy += int(H * 0.045)
    d.text((tx, cy), web, font=font(int(H * 0.019), "regular"), fill=(70, 55, 5))
    base.convert("RGB").save(out, "PNG"); return out


def jody_coachcard(t, cut, brand, head, web, out, name, role, phone):
    base = _grad(t["base"], t["base2"]).convert("RGBA"); d = ImageDraw.Draw(base)
    d.rectangle([0, 0, int(W * 0.06), H], fill=t["accent"])
    c = _cut(cut, int(H * 0.92)); _place_cutout(base, c, int(W * 0.26))
    d = ImageDraw.Draw(base); tx = int(W * 0.50); tw = W - tx - int(W * 0.06)
    _badge(d, tx, int(H * 0.08), t["badge"], int(H * 0.020), t)
    _quote(d, tx, int(H * 0.155), int(H * 0.07), t["accent"])
    f, ls, lh = _fitw(d, head, tw, H * 0.30, int(H * 0.046), int(H * 0.030))
    y = _tb(d, tx, int(H * 0.235), ls, f, lh, t["text"])
    d.line([(tx, y + 14), (tx + int(tw * 0.55), y + 14)], fill=t["accent"], width=4)
    d.text((tx, int(H * 0.66)), name, font=font(int(H * 0.034), "black"), fill=t["text"])
    d.text((tx, int(H * 0.70)), role, font=font(int(H * 0.022), "medium"), fill=t["accent"])
    _pill(d, tx, int(H * 0.76), "BOOK A FREE CALL", int(H * 0.020), t["accent_text"], t["accent"])
    _contact(d, tx, int(H * 0.86), web, phone, t["soft"], t["accent"])
    base.convert("RGB").save(out, "PNG"); return out


# ----------------------------------------------------------------- SIMPLE (no photo)
def simple_editorial(t, _a, brand, head, web, out, name, role, phone):
    base = Image.new("RGB", (W, H), t["cream"]); d = ImageDraw.Draw(base)
    if t["spectrum"]:
        _spectrum_bar(d, int(W * 0.06), int(H * 0.05), int(W * 0.34), int(H * 0.014))
    else:
        d.rectangle([0, 0, W, int(H * 0.03)], fill=t["accent"])
    d.text((int(W * 0.06), int(H * 0.09)), brand.upper(), font=font(int(H * 0.024), "bold"), fill=t["cream_text"])
    _quote(d, int(W * 0.06), int(H * 0.18), int(H * 0.11), t["accent"])
    f, ls, lh = _fitw(d, head, int(W * 0.88), H * 0.42, int(H * 0.070), int(H * 0.040), "black", 0.14)
    y = _tb(d, int(W * 0.06), int(H * 0.34), ls, f, lh, t["cream_text"])
    d.line([(int(W * 0.06), y + 20), (int(W * 0.30), y + 20)], fill=t["accent"], width=6)
    d.text((int(W * 0.06), H - int(H * 0.10)), name + "  \u00b7  " + role, font=font(int(H * 0.024), "semibold"), fill=t["cream_text"])
    d.text((int(W * 0.06), H - int(H * 0.06)), web, font=font(int(H * 0.022), "regular"), fill=(120, 120, 120))
    base.save(out, "PNG"); return out


def simple_bold(t, _a, brand, head, web, out, name, role, phone):
    base = _grad(t["base"], t["base2"]); d = ImageDraw.Draw(base)
    _pill(d, int(W * 0.06), int(H * 0.08), t["tip"], int(H * 0.022), t["accent_text"], t["accent"])
    f, ls, lh = _fitw(d, head, int(W * 0.86), H * 0.46, int(H * 0.078), int(H * 0.044), "black", 0.14)
    total = lh * len(ls); y = (H - total) // 2
    for ln in ls:
        d.text(((W - d.textlength(ln, font=f)) / 2, y), ln, font=f, fill=t["text"]); y += lh
    if t["spectrum"]:
        _spectrum_bar(d, (W - int(W * 0.18)) // 2, y + 16, int(W * 0.18), int(H * 0.012))
    else:
        d.rectangle([(W - int(W * 0.16)) // 2, y + 18, (W + int(W * 0.16)) // 2, y + 26], fill=t["accent"])
    d.text((int(W * 0.06), H - int(H * 0.07)), brand.upper(), font=font(int(H * 0.022), "bold"), fill=t["accent"])
    wf = font(int(H * 0.022), "regular")
    d.text((W - int(W * 0.06) - d.textlength(web, font=wf), H - int(H * 0.07)), web, font=wf, fill=t["soft"])
    base.save(out, "PNG"); return out


def simple_split(t, _a, brand, head, web, out, name, role, phone):
    base = Image.new("RGB", (W, H), t["cream"]); d = ImageDraw.Draw(base)
    d.rectangle([0, 0, W, int(H * 0.60)], fill=t["base"])
    if t["spectrum"]:
        _spectrum_bar(d, int(W * 0.06), int(H * 0.06), int(W * 0.30), int(H * 0.012))
    d.text((int(W * 0.06), int(H * 0.085)), brand.upper(), font=font(int(H * 0.024), "bold"), fill=t["accent"])
    _quote(d, int(W * 0.06), int(H * 0.155), int(H * 0.07), t["accent"])
    f, ls, lh = _fitw(d, head, int(W * 0.88), H * 0.30, int(H * 0.058), int(H * 0.036))
    y = _tb(d, int(W * 0.06), int(H * 0.245), ls, f, lh, t["text"])
    d.line([(int(W * 0.06), y + 16), (int(W * 0.32), y + 16)], fill=t["accent"], width=5)
    _btn(d, int(W * 0.06), int(H * 0.72), t["cta"], int(H * 0.024), t["text"], t["base"])
    d.text((int(W * 0.06), H - int(H * 0.07)), web, font=font(int(H * 0.022), "regular"), fill=(120, 120, 120))
    base.save(out, "PNG"); return out


def simple_spectrum(t, _a, brand, head, web, out, name, role, phone):
    base = _grad(t["base"], t["base2"]); d = ImageDraw.Draw(base)
    _spectrum_bar(d, int(W * 0.06), int(H * 0.085), int(W * 0.5), int(H * 0.016))
    d.text((int(W * 0.06), int(H * 0.13)), brand.upper(), font=font(int(H * 0.024), "bold"), fill=t["accent"])
    _quote(d, int(W * 0.06), int(H * 0.20), int(H * 0.085), t["accent"])
    f, ls, lh = _fitw(d, head, int(W * 0.86), H * 0.40, int(H * 0.066), int(H * 0.040), "extrabold", 0.14)
    y = _tb(d, int(W * 0.06), int(H * 0.32), ls, f, lh, t["text"])
    _spectrum_bar(d, int(W * 0.06), y + 24, int(W * 0.24), int(H * 0.012))
    d.text((int(W * 0.06), H - int(H * 0.085)), role, font=font(int(H * 0.024), "semibold"), fill=t["accent"])
    d.text((int(W * 0.06), H - int(H * 0.05)), web, font=font(int(H * 0.022), "regular"), fill=t["soft"])
    base.save(out, "PNG"); return out


# ----------------------------------------------------------------- OTHER (duotone photo + graphics)
def other_hero(t, photo, brand, head, web, out, name, role, phone):
    src = _cover_p(Image.open(photo).convert("RGB"))
    fm = _face_mask(src)                                   # detect once, reuse below
    duo = _duotone(src, t["duo_dark"], t["duo_light"], face_mask=fm)
    base = _scrim(duo.convert("RGBA"), t["base"], start=0.46, alpha=222, face_mask=fm)
    d = ImageDraw.Draw(base)
    # top brand row + accent tab
    d.rectangle([int(W * 0.06), int(H * 0.06), int(W * 0.06) + int(W * 0.10), int(H * 0.06) + 8], fill=t["accent"])
    d.text((int(W * 0.06), int(H * 0.075)), brand.upper(), font=font(int(H * 0.024), "bold"), fill=t["text"])
    # gold corner graphic
    d.polygon([(W, 0), (W - int(W * 0.22), 0), (W, int(W * 0.22))], fill=t["accent"])
    if t["spectrum"]:
        _spectrum_bar(d, int(W * 0.06), int(H * 0.60), int(W * 0.30), int(H * 0.012))
    _quote(d, int(W * 0.06), int(H * 0.585), int(H * 0.065), t["accent"])
    f, ls, lh = _fitw(d, head, int(W * 0.88), H * 0.175, int(H * 0.054), int(H * 0.032))
    y = _tb(d, int(W * 0.06), int(H * 0.655), ls, f, lh, t["text"])
    uy = min(y + 16, H - int(H * 0.115))            # keep the rule above the contact line
    d.line([(int(W * 0.06), uy), (int(W * 0.34), uy)], fill=t["accent"], width=5)
    _contact(d, int(W * 0.06), max(uy + int(H * 0.03), H - int(H * 0.085)), web, phone, t["soft"], t["accent"])
    base.convert("RGB").save(out, "PNG"); return out


def other_property(t, photo, brand, head, web, out, name, role, phone):
    base = _grad(t["base"], t["base2"]).convert("RGBA"); d = ImageDraw.Draw(base)
    m = int(W * 0.06)
    d.rectangle([m, int(H * 0.06), m + int(W * 0.10), int(H * 0.06) + 8], fill=t["accent"])
    d.text((m, int(H * 0.075)), brand.upper(), font=font(int(H * 0.024), "bold"), fill=t["accent"])
    iw, ih = W - 2 * m, int(H * 0.46); iy = int(H * 0.115)
    duo = _duotone(_cover(Image.open(photo).convert("RGB"), iw, ih), t["duo_dark"], t["duo_light"])
    base.alpha_composite(_rounded(duo, int(W * 0.04)), (m, iy))
    d = ImageDraw.Draw(base)
    _icon(d, t["icon"], W - int(W * 0.16), int(H * 0.60), int(W * 0.07), t["accent"], t["base"])
    f, ls, lh = _fitw(d, head, int(W * 0.62), H * 0.20, int(H * 0.052), int(H * 0.034))
    y = _tb(d, m, int(H * 0.64), ls, f, lh, t["text"])
    d.line([(m, y + 16), (m + int(W * 0.30), y + 16)], fill=t["accent"], width=5)
    cy = int(H * 0.90)
    d.rounded_rectangle([m, cy, W - m, cy + int(H * 0.075)], int(H * 0.02), fill=t["accent"])
    contact = (phone + "    " if phone else "") + web
    d.text((m + int(W * 0.04), cy + int(H * 0.024)), contact, font=font(int(H * 0.026), "bold"), fill=t["accent_text"])
    base.convert("RGB").save(out, "PNG"); return out


def other_split(t, photo, brand, head, web, out, name, role, phone):
    base = _grad(t["base"], t["base2"]).convert("RGBA")
    # duotone photo on the right, diagonal cut
    duo = _duotone(_cover_p(Image.open(photo).convert("RGB")), t["duo_dark"], t["duo_light"]).convert("RGBA")
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(int(W * 0.42), 0), (W, 0), (W, H), (int(W * 0.30), H)], fill=255)
    base.paste(duo, (0, 0), mask)
    d = ImageDraw.Draw(base)
    d.line([(int(W * 0.42), 0), (int(W * 0.30), H)], fill=t["accent"], width=8)
    tx = int(W * 0.06); tw = int(W * 0.32)
    _badge(d, tx, int(H * 0.08), t["badge"], int(H * 0.020), t)
    _quote(d, tx, int(H * 0.16), int(H * 0.07), t["accent"])
    f, ls, lh = _fitw(d, head, tw, H * 0.34, int(H * 0.044), int(H * 0.030))
    y = _tb(d, tx, int(H * 0.25), ls, f, lh, t["text"])
    d.line([(tx, y + 14), (tx + int(tw * 0.6), y + 14)], fill=t["accent"], width=4)
    _contact(d, tx, H - int(H * 0.10), web, phone, t["soft"], t["accent"])
    base.convert("RGB").save(out, "PNG"); return out


def other_frame(t, photo, brand, head, web, out, name, role, phone):
    base = _grad(t["base"], t["base2"]).convert("RGBA"); d = ImageDraw.Draw(base)
    if t["spectrum"]:
        _spectrum_bar(d, int(W * 0.06), int(H * 0.07), int(W * 0.30), int(H * 0.014))
    _badge(d, W - int(W * 0.40), int(H * 0.06), t["badge"], int(H * 0.020), t)
    f, ls, lh = _fitw(d, head, int(W * 0.88), H * 0.16, int(H * 0.050), int(H * 0.032))
    y = _tb(d, int(W * 0.06), int(H * 0.115), ls, f, lh, t["text"])
    # framed duotone photo card
    iw, ih = int(W * 0.74), int(H * 0.44); ix = (W - iw) // 2; iy = int(H * 0.34)
    d.rounded_rectangle([ix - 10, iy - 10, ix + iw + 10, iy + ih + 10], int(W * 0.04), fill=t["accent"])
    duo = _duotone(_cover(Image.open(photo).convert("RGB"), iw, ih), t["duo_dark"], t["duo_light"])
    base.alpha_composite(_rounded(duo, int(W * 0.03)), (ix, iy))
    d = ImageDraw.Draw(base)
    _btn(d, (W - int(W * 0.40)) // 2, int(H * 0.84), t["cta"], int(H * 0.022), t["accent_text"], t["accent"], w=int(W * 0.40))
    wf = font(int(H * 0.022), "regular")
    d.text(((W - d.textlength(web, font=wf)) / 2, H - int(H * 0.055)), web, font=wf, fill=t["soft"])
    base.convert("RGB").save(out, "PNG"); return out


# ----------------------------------------------------------------- recipes
RECIPES = {
    "agent_broker_coach": [
        ("jody", jody_spotlight, None),
        ("simple", simple_editorial, None),
        ("other", other_hero, "real estate agent shaking hands with client"),
        ("jody", jody_band, None),
        ("other", other_property, "modern luxury house exterior"),
        ("simple", simple_bold, None),
        ("jody", jody_badge, None),
        ("other", other_split, "real estate agent showing home to buyers"),
        ("jody", jody_diagonal, None),
        ("simple", simple_split, None),
        ("other", other_frame, "bright modern living room interior"),
        ("jody", jody_coachcard, None),
    ],
    "autismworks": [
        ("simple", simple_spectrum, None),
        ("other", other_hero, "diverse team collaborating bright office"),
        ("simple", simple_bold, None),
        ("other", other_split, "young adult working laptop focused"),
        ("simple", simple_editorial, None),
        ("other", other_frame, "mentor helping young employee smiling"),
        ("simple", simple_spectrum, None),
        ("other", other_hero, "people working together workshop hands"),
        ("simple", simple_split, None),
        ("other", other_property, "modern bright office workspace plants"),
        ("simple", simple_bold, None),
        ("other", other_frame, "smiling young person working cafe"),
    ],
}


def cutout_pool():
    return sorted(glob.glob(os.path.join("assets", "cutouts", "*.png")))


def _img_head(headline):
    """Keep image headlines short and punchy so no layout can overflow.
    Full copy still lives in the caption; the image gets a tight line.
    Prefers the first sentence; caps length so narrow-column recipes stay legible."""
    h = " ".join((headline or "").split()).strip()
    if not h:
        return h
    # prefer the first sentence if the headline is long
    if len(h) > 60:
        import re as _re
        parts = _re.split(r"(?<=[.!?])\s+", h)
        if parts and len(parts[0]) >= 12:
            h = parts[0].strip()
    # hard word/char cap (keeps whole words)
    words = h.split()
    if len(words) > 11:
        h = " ".join(words[:11])
    if len(h) > 74:
        cut = h[:74].rsplit(" ", 1)[0]
        h = cut if len(cut) >= 40 else h[:74]
    h = h.rstrip(" ,;:-")
    # don't let a trimmed line end on a filler word
    _stop = {"the","a","an","and","or","of","to","for","in","on","is","are",
             "your","you","that","with","this","it","as","at","by","but"}
    parts = h.split()
    while len(parts) > 3 and parts[-1].lower() in _stop:
        parts.pop()
    return " ".join(parts)


def build(gidx, brand_key, headline, website, out_path, phone="", name=None, role=None, pexels=None, recipe_idx=None):
    t = THEME.get(brand_key, THEME["agent_broker_coach"])
    recipes = RECIPES.get(brand_key, RECIPES["agent_broker_coach"])
    # recipe (the visual STYLE) can be chosen independently from gidx (which drives
    # the PHOTO), so the caller can shuffle styles per day while photos keep changing.
    ridx = gidx if recipe_idx is None else recipe_idx
    kind, builder, query = recipes[ridx % len(recipes)]
    web = website.replace("https://", "").replace("http://", "")
    headline = _img_head(headline)
    nm = name or t["name"]; rl = role or t["role"]; brand = t["name"]
    if kind == "jody":
        pool = cutout_pool()
        if pool:
            return builder(t, pool[gidx % len(pool)], brand, headline, web, out_path, nm, rl, phone)
        kind, builder = "simple", simple_bold
    if kind == "simple":
        return builder(t, None, brand, headline, web, out_path, nm, rl, phone)
    raw = out_path.replace(".png", "_raw.jpg")
    fetch_photo(query, pexels, raw, variant=gidx)
    try:
        return builder(t, raw, brand, headline, web, out_path, nm, rl, phone)
    finally:
        try:
            os.remove(raw)
        except OSError:
            pass
