"""Branded image cards with multiple rotating designs (Pillow).

make_card(..., template=N) renders one of NUM_TEMPLATES distinct layouts, so the
publisher can rotate designs across sessions and days. AutismWorks gets a prism
spectrum accent (never puzzle imagery).
"""

import os
from PIL import Image, ImageDraw, ImageFont

NUM_TEMPLATES = 4

THEMES = {
    "agent_broker_coach": {
        "bg": (11, 37, 69), "band": (16, 52, 95), "accent": (242, 183, 5),
        "headline": (255, 255, 255), "meta": (183, 201, 226), "spectrum": False,
    },
    "autismworks": {
        "bg": (18, 46, 58), "band": (24, 60, 74), "accent": (94, 200, 209),
        "headline": (255, 255, 255), "meta": (190, 214, 220), "spectrum": True,
    },
}
DEFAULT = {"bg": (24, 24, 28), "band": (38, 38, 44), "accent": (200, 200, 200),
           "headline": (255, 255, 255), "meta": (180, 180, 180), "spectrum": False}

_BOLD = ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_REG = ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


_FONT_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")
_FONT_FILES = {
    "black":     ["Montserrat-ExtraBold.ttf", "Poppins-ExtraBold.ttf"],
    "extrabold": ["Montserrat-ExtraBold.ttf", "Poppins-ExtraBold.ttf"],
    "bold":      ["Montserrat-Bold.ttf", "Poppins-Bold.ttf"],
    "semibold":  ["Poppins-SemiBold.ttf", "Montserrat-Bold.ttf"],
    "medium":    ["Poppins-Medium.ttf", "Poppins-Regular.ttf"],
    "regular":   ["Poppins-Regular.ttf", "Montserrat-Bold.ttf"],
    "script":    ["Caveat-Bold.ttf", "PlayfairDisplay-Bold.otf"],
}
_SYS_BOLD = ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_SYS_REG = ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
_font_cache = {}


def font(size, weight="bold"):
    key = (size, weight)
    if key in _font_cache:
        return _font_cache[key]
    for fn in _FONT_FILES.get(weight, _FONT_FILES["bold"]):
        p = os.path.join(_FONT_DIR, fn)
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size); _font_cache[key] = f; return f
            except Exception:
                pass
    for p in (_SYS_BOLD if weight in ("bold", "extrabold", "black", "semibold") else _SYS_REG):
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size); _font_cache[key] = f; return f
            except Exception:
                pass
    return ImageFont.load_default()


def _font(size, bold=True):
    return font(size, "bold" if bold else "regular")


def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit(draw, text, max_w, max_h, start, floor):
    size = start
    while size > floor:
        f = _font(size, True)
        lines = _wrap(draw, text, f, max_w)
        lh = f.getbbox("Ag")[3] + int(size * 0.25)
        if lh * len(lines) <= max_h:
            return f, lines, lh
        size -= 6
    f = _font(floor, True)
    lines = _wrap(draw, text, f, max_w)
    return f, lines, f.getbbox("Ag")[3] + int(floor * 0.25)


def _spectrum(d, x, y, w):
    cols = [(228, 87, 86), (240, 165, 72), (245, 215, 90),
            (120, 200, 120), (90, 170, 225), (150, 120, 210)]
    sw = w / len(cols)
    for c in cols:
        d.rectangle([x, y, x + sw, y + 12], fill=c)
        x += sw


def make_card(brand_key, brand_name, headline, website, out_path, template=0, size=1080):
    th = THEMES.get(brand_key, DEFAULT)
    template %= NUM_TEMPLATES
    web = website.replace("https://", "").replace("http://", "")
    m = int(size * 0.09)
    img = Image.new("RGB", (size, size), th["bg"])
    d = ImageDraw.Draw(img)

    if template == 0:
        d.rectangle([m, m, m + int(size * 0.14), m + 10], fill=th["accent"])
        d.text((m, m + 28), brand_name.upper(), font=_font(int(size * 0.045)), fill=th["accent"])
        f, lines, lh = _fit(d, headline, size - 2 * m, size * 0.5, int(size * 0.085), int(size * 0.045))
        y = (size - lh * len(lines)) // 2
        for ln in lines:
            d.text((m, y), ln, font=f, fill=th["headline"]); y += lh
        sy = size - int(m * 1.7)
        (_spectrum(d, m, sy, size - 2 * m) if th["spectrum"]
         else d.rectangle([m, sy, m + int(size * 0.22), sy + 12], fill=th["accent"]))
        d.text((m, size - int(m * 1.25)), web, font=_font(int(size * 0.034), False), fill=th["meta"])

    elif template == 1:
        bh = int(size * 0.2)
        d.rectangle([0, 0, size, bh], fill=th["accent"])
        bn = _font(int(size * 0.05))
        d.text(((size - d.textlength(brand_name.upper(), font=bn)) / 2, bh / 2 - int(size * 0.03)),
               brand_name.upper(), font=bn, fill=th["bg"])
        f, lines, lh = _fit(d, headline, size - 2 * m, size * 0.45, int(size * 0.082), int(size * 0.045))
        y = bh + (size - bh - lh * len(lines)) // 2
        for ln in lines:
            d.text(((size - d.textlength(ln, font=f)) / 2, y), ln, font=f, fill=th["headline"]); y += lh
        if th["spectrum"]:
            _spectrum(d, m, size - int(m * 1.3), size - 2 * m)
        d.text(((size - d.textlength(web, font=_font(int(size * 0.032), False))) / 2,
                size - int(m * 0.85)), web, font=_font(int(size * 0.032), False), fill=th["meta"])

    elif template == 2:
        qm = _font(int(size * 0.26))
        d.text((m - int(size * 0.01), m - int(size * 0.04)), "\u201C", font=qm, fill=th["accent"])
        f, lines, lh = _fit(d, headline, size - 2 * m, size * 0.45, int(size * 0.08), int(size * 0.045))
        y = int(size * 0.34)
        for ln in lines:
            d.text((m, y), ln, font=f, fill=th["headline"]); y += lh
        sy = size - int(m * 1.7)
        (_spectrum(d, m, sy, int(size * 0.4)) if th["spectrum"]
         else d.rectangle([m, sy, m + int(size * 0.22), sy + 12], fill=th["accent"]))
        d.text((m, size - int(m * 1.25)), brand_name.upper() + "   |   " + web,
               font=_font(int(size * 0.032), False), fill=th["meta"])

    else:
        d.rectangle([m, m, m + int(size * 0.14), m + 10], fill=th["accent"])
        d.text((m, m + 28), brand_name.upper(), font=_font(int(size * 0.045)), fill=th["accent"])
        f, lines, lh = _fit(d, headline, size - 2 * m, size * 0.42, int(size * 0.085), int(size * 0.045))
        y = int(size * 0.26)
        for ln in lines:
            d.text((m, y), ln, font=f, fill=th["headline"]); y += lh
        bh = int(size * 0.16)
        d.rectangle([0, size - bh, size, size], fill=th["band"])
        if th["spectrum"]:
            _spectrum(d, m, size - bh + int(bh * 0.28), size - 2 * m)
        d.text((m, size - bh + int(bh * 0.55)), web,
               font=_font(int(size * 0.034), False), fill=th["meta"])

    img.save(out_path, "PNG")
    return out_path
