"""Real-photo posts: pull a relevant stock photo from Pexels and lay a modern
gradient + bold headline over it. Much richer than a flat banner.

Needs a free PEXELS_API_KEY (instant signup at pexels.com/api). If the key or a
photo is missing, the caller falls back to a branded card automatically.
Credit appreciated by Pexels: "Photos provided by Pexels".
"""

import requests
from PIL import Image, ImageDraw
from images import _font, _fit, THEMES, DEFAULT

PEXELS_SEARCH = "https://api.pexels.com/v1/search"

# --- Photo safety: keep stock results strictly on-topic (real estate) ----------
# Words that pull romance/holiday/lifestyle imagery instead of real estate.
_BAN = {"couple", "couples", "kiss", "kissing", "romance", "romantic", "wedding",
        "bride", "groom", "love", "lover", "date", "dating", "valentine", "hug",
        "embrace", "christmas", "xmas", "santa", "holiday", "beach", "party",
        "bikini", "swimsuit", "model", "girlfriend", "boyfriend"}
# At least one of these must be present so the search stays about real estate.
_ANCHORS = ("real estate", "realtor", "real-estate", "agent", "broker", "house",
            "home", "property", "listing", "apartment", "interior", "kitchen",
            "living room", "bedroom", "key", "for sale", "mortgage", "office", "desk")


def _safe_query(q):
    """Drop off-topic/romance words and guarantee a real-estate anchor."""
    words = [w for w in (q or "").split() if w.lower().strip(",.") not in _BAN]
    q2 = " ".join(words).strip() or "real estate house exterior"
    if not any(a in q2.lower() for a in _ANCHORS):
        q2 = q2 + " real estate"
    return q2


def fetch_photo(query, api_key, out_path, variant=0):
    query = _safe_query(query)
    r = requests.get(
        PEXELS_SEARCH,
        headers={"Authorization": api_key},
        params={"query": query, "orientation": "square", "per_page": 80, "size": "medium"},
        timeout=30,
    )
    r.raise_for_status()
    photos = r.json().get("photos", [])
    if not photos:
        raise RuntimeError(f"no Pexels results for '{query}'")
    photo = photos[variant % len(photos)]
    url = photo["src"].get("large2x") or photo["src"].get("large") or photo["src"]["original"]
    data = requests.get(url, timeout=60).content
    with open(out_path, "wb") as f:
        f.write(data)
    return out_path


def _cover_square(img, size, vbias=0.5):
    w, h = img.size
    scale = size / min(w, h)
    img = img.resize((max(size, int(w * scale) + 1), max(size, int(h * scale) + 1)))
    w, h = img.size
    left = (w - size) // 2
    top = int((h - size) * vbias)
    return img.crop((left, top, left + size, top + size))


def _cover(img, tw, th):
    """Cover-crop an image to fill a tw x th box."""
    w, h = img.size
    scale = max(tw / w, th / h)
    img = img.resize((max(tw, int(w * scale) + 1), max(th, int(h * scale) + 1)))
    w, h = img.size
    left, top = (w - tw) // 2, (h - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _rounded(img, radius):
    """Round the corners of an RGBA image."""
    from PIL import ImageDraw as _D
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    _D.Draw(mask).rounded_rectangle([0, 0, img.size[0], img.size[1]], radius, fill=255)
    img.putalpha(mask)
    return img


def _face_pool():
    """List of Jody photos to rotate through (assets/jody/*)."""
    import glob, os
    return sorted(glob.glob(os.path.join("assets", "jody", "*.jpg")) +
                  glob.glob(os.path.join("assets", "jody", "*.png")))


def brand_face_pool():
    return _face_pool()


def _vbias_for(img):
    """Keep the head: top-anchor portraits, centre landscapes."""
    w, h = img.size
    return 0.06 if h >= w else 0.30


def compose_bottomplate(photo_path, brand_key, brand_name, headline, website, out_path,
                        person_name="Jody McNamer", phone="", size=1080):
    th = THEMES.get(brand_key, DEFAULT); accent = th["accent"]; bg = th["bg"]
    web = website.replace("https://", "").replace("http://", "")
    img = Image.open(photo_path).convert("RGB")
    base = _cover_square(img, size, _vbias_for(img)).convert("RGBA")

    by = int(size * 0.60)
    plate = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pdz = ImageDraw.Draw(plate)
    lead = int(size * 0.07)
    for i in range(lead):
        a = int(255 * (i / lead))
        pdz.rectangle([0, by - lead + i, size, by - lead + i + 1], fill=(bg[0], bg[1], bg[2], a))
    pdz.rectangle([0, by, size, size], fill=(bg[0], bg[1], bg[2], 255))
    base = Image.alpha_composite(base, plate)
    d = ImageDraw.Draw(base)

    d.rectangle([0, by, size, by + 6], fill=accent)
    m = int(size * 0.06)
    d.text((m, by + int(size * 0.03)), brand_name.upper(),
           font=_font(int(size * 0.026)), fill=accent)
    f, lines, lh = _fit(d, headline, size - 2 * m, size * 0.20, int(size * 0.052), int(size * 0.034))
    y = by + int(size * 0.08)
    for ln in lines:
        d.text((m, y), ln, font=f, fill=(255, 255, 255)); y += lh
    contact = person_name + ((" · " + phone) if phone else "") + "   " + web
    csz = int(size * 0.024)
    while csz > int(size * 0.018) and d.textlength(contact, font=_font(csz, False)) > size - 2 * m:
        csz -= 2
    d.text((m, size - int(size * 0.06)), contact, font=_font(csz, False), fill=(210, 222, 240))
    base.convert("RGB").save(out_path, "PNG"); return out_path


def compose_lifestyle(photo_path, brand_key, brand_name, headline, website, out_path,
                      phone="", size=1080):
    th = THEMES.get(brand_key, DEFAULT); accent = th["accent"]; bg = th["bg"]
    web = website.replace("https://", "").replace("http://", "")
    img = Image.open(photo_path).convert("RGB")
    base = _cover_square(img, size, _vbias_for(img)).convert("RGBA")

    ov = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    h = int(size * 0.62)
    for i in range(h):
        a = int(250 * (i / h) ** 1.2)
        od.rectangle([0, size - 1 - i, size, size - i], fill=(bg[0], bg[1], bg[2], a))
    base = Image.alpha_composite(base, ov)
    d = ImageDraw.Draw(base)

    m = int(size * 0.06)
    d.rectangle([m, int(size * 0.44), m + int(size * 0.07), int(size * 0.44) + 7], fill=accent)
    d.text((m, int(size * 0.46)), brand_name.upper(), font=_font(int(size * 0.026)), fill=accent)
    f, lines, lh = _fit(d, headline, size - 2 * m, size * 0.26, int(size * 0.066), int(size * 0.04))
    total = lh * len(lines)
    y = size - int(size * 0.20) - total
    for ln in lines:
        d.text((m, y), ln, font=f, fill=(255, 255, 255)); y += lh
    d.rectangle([m, y + 10, m + int(size * 0.13), y + 22], fill=accent)
    contact = (phone + "    " if phone else "") + web
    d.text((m, size - int(size * 0.075)), contact, font=_font(int(size * 0.025), False),
           fill=(225, 232, 244))
    base.convert("RGB").save(out_path, "PNG"); return out_path


def brand_face_path():
    """Return the brand headshot (e.g. Jody) if the user dropped one in assets/."""
    import os
    for name in ("jody.jpg", "jody.jpeg", "jody.png", "headshot.jpg", "headshot.png"):
        p = os.path.join("assets", name)
        if os.path.exists(p):
            return p
    return None


def brand_cutout_path():
    """Transparent cut-out headshot (Jody on no background) if present."""
    import os
    for name in ("jody-cutout.png", "cutout.png"):
        p = os.path.join("assets", name)
        if os.path.exists(p):
            return p
    return None


def compose_cutout(cutout_path, brand_key, brand_name, headline, website, out_path,
                   side="right", mode="spotlight", person_name="Jody McNamer",
                   role="Agent Broker Coach", phone="", size=1080):
    """Place a transparent person cut-out on a branded background with text on
    the opposite side. mode: 'spotlight' (name banner) or 'coach' (CTA pill)."""
    th = THEMES.get(brand_key, DEFAULT); accent = th["accent"]; bg = th["bg"]
    web = website.replace("https://", "").replace("http://", "")
    base = Image.new("RGBA", (size, size), (bg[0], bg[1], bg[2], 255))
    d = ImageDraw.Draw(base)

    # subtle lighter band on the person's side + warm accent circle for depth
    band = th.get("band", bg)
    if side == "right":
        d.rectangle([int(size * 0.52), 0, size, size], fill=(band[0], band[1], band[2], 255))
    else:
        d.rectangle([0, 0, int(size * 0.48), size], fill=(band[0], band[1], band[2], 255))
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gx = int(size * 0.74) if side == "right" else int(size * 0.26)
    ImageDraw.Draw(glow).ellipse([gx - int(size * 0.26), int(size * 0.10),
                                  gx + int(size * 0.26), int(size * 0.62)],
                                 fill=(accent[0], accent[1], accent[2], 38))
    base = Image.alpha_composite(base, glow)

    # the cut-out (cropped tight, bottom-aligned)
    cut = Image.open(cutout_path).convert("RGBA")
    bbox = cut.split()[3].getbbox()
    if bbox:
        cut = cut.crop(bbox)
    H = int(size * 0.92); W = int(H * cut.width / cut.height)
    cut = cut.resize((W, H))
    cx = (size - W + int(size * 0.02)) if side == "right" else (-int(size * 0.02))
    base.alpha_composite(cut, (cx, size - H))
    d = ImageDraw.Draw(base)

    # text column on the opposite side
    m = int(size * 0.055)
    if side == "right":
        tx = m; tw = size - W - m - int(size * 0.02)
    else:
        tx = W + int(size * 0.03); tw = size - tx - m

    d.rectangle([tx, int(size * 0.10), tx + int(size * 0.075), int(size * 0.10) + 8], fill=accent)
    d.text((tx, int(size * 0.125)), brand_name.upper(), font=_font(int(size * 0.027)), fill=accent)

    f, lines, lh = _fit(d, headline, tw, size * 0.42, int(size * 0.060), int(size * 0.034))
    y = int(size * 0.22)
    for ln in lines:
        d.text((tx, y), ln, font=f, fill=(255, 255, 255)); y += lh
    d.rectangle([tx, y + 10, tx + int(size * 0.12), y + 22], fill=accent)

    if mode == "coach":
        cy = int(size * 0.76)
        cta = "Book a free coaching call"
        cf = _font(int(size * 0.024))
        pill_w = int(d.textlength(cta, font=cf)) + int(size * 0.06)
        d.rounded_rectangle([tx, cy, tx + min(pill_w, tw), cy + int(size * 0.07)],
                            int(size * 0.035), fill=accent)
        d.text((tx + int(size * 0.03), cy + int(size * 0.021)), cta, font=cf, fill=(bg[0], bg[1], bg[2]))
    else:
        by = int(size * 0.76)
        d.rectangle([tx, by, tx + tw, by + int(size * 0.078)], fill=accent)
        d.text((tx + int(size * 0.02), by + int(size * 0.017)), person_name,
               font=_font(int(size * 0.032)), fill=(bg[0], bg[1], bg[2]))

    contact = (phone + "    " if phone else "") + web
    csz = int(size * 0.025)
    while csz > int(size * 0.018) and d.textlength(contact, font=_font(csz, False)) > tw:
        csz -= 2
    d.text((tx, size - int(size * 0.07)), contact, font=_font(csz, False),
           fill=(225, 232, 244))
    base.convert("RGB").save(out_path, "PNG"); return out_path


def _house_icon(d, cx, y, w, color):
    """Simple clean house icon centered on cx."""
    half = w / 2
    roof_h = w * 0.42
    d.polygon([(cx - half, y + roof_h), (cx, y), (cx + half, y + roof_h)], fill=color)
    bw = w * 0.62
    d.rectangle([cx - bw / 2, y + roof_h, cx + bw / 2, y + w * 0.92], fill=color)
    # door knockout
    dw = w * 0.16
    d.rectangle([cx - dw / 2, y + w * 0.55, cx + dw / 2, y + w * 0.92], fill=(11, 37, 69))


# ---------------------------------------------------------------- ABC layouts
def compose_spotlight(photo_path, brand_key, brand_name, headline, website, out_path,
                      person_name="JODY McNAMER", role="Agent Broker Coach", phone="", size=1080):
    th = THEMES.get(brand_key, DEFAULT); accent = th["accent"]; bg = th["bg"]
    web = website.replace("https://", "").replace("http://", "")
    base = _cover_square(Image.open(photo_path).convert("RGB"), size).convert("RGBA")

    # navy diagonal panel on the right
    panel = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    sx = int(size * 0.52)
    pd.polygon([(sx + int(size * 0.05), 0), (size, 0), (size, size), (sx, size)],
               fill=(bg[0], bg[1], bg[2], 255))
    base = Image.alpha_composite(base, panel)
    d = ImageDraw.Draw(base)

    m = int(size * 0.045)
    px = int(size * 0.59)                 # left edge of right-panel text (inside panel)
    tw = size - px - m
    d.rectangle([px, int(size * 0.075), px + int(size * 0.07), int(size * 0.075) + 7], fill=accent)
    d.text((px, int(size * 0.095)), brand_name.upper(), font=_font(int(size * 0.027)), fill=accent)

    f, lines, lh = _fit(d, headline, tw, size * 0.40, int(size * 0.058), int(size * 0.034))
    y = int(size * 0.18)
    for ln in lines:
        d.text((px, y), ln, font=f, fill=(255, 255, 255)); y += lh
    d.rectangle([px, y + 10, px + int(size * 0.12), y + 22], fill=accent)

    # gold banner with name/role
    by = int(size * 0.74)
    d.rectangle([px - int(size * 0.02), by, size, by + int(size * 0.085)], fill=accent)
    d.text((px, by + int(size * 0.018)), person_name, font=_font(int(size * 0.034)),
           fill=(bg[0], bg[1], bg[2]))
    contact = phone or web
    d.text((px, size - int(size * 0.07)), contact, font=_font(int(size * 0.026), False),
           fill=(235, 240, 248))
    base.convert("RGB").save(out_path, "PNG"); return out_path


def compose_coachcard(photo_path, brand_key, brand_name, headline, website, out_path,
                      person_name="Jody McNamer", role="Agent Broker Coach", phone="", size=1080):
    th = THEMES.get(brand_key, DEFAULT); accent = th["accent"]; bg = th["bg"]
    web = website.replace("https://", "").replace("http://", "")
    base = Image.new("RGBA", (size, size), (bg[0], bg[1], bg[2], 255))
    d = ImageDraw.Draw(base)

    # headshot as a rounded inset on the right
    iw, ih = int(size * 0.42), int(size * 0.74)
    ix, iy = size - iw - int(size * 0.05), int(size * 0.13)
    shot = _rounded(_cover(Image.open(photo_path).convert("RGB"), iw, ih), int(size * 0.04))
    d.rectangle([ix - 10, iy - 10, ix - 10 + 14, iy - 10 + 14], fill=accent)   # corner tick
    base.alpha_composite(shot, (ix, iy))
    d = ImageDraw.Draw(base)

    m = int(size * 0.06); tw = ix - m - int(size * 0.03)
    d.rectangle([m, int(size * 0.14), m + int(size * 0.07), int(size * 0.14) + 7], fill=accent)
    d.text((m, int(size * 0.16)), brand_name.upper(), font=_font(int(size * 0.026)), fill=accent)

    f, lines, lh = _fit(d, headline, tw, size * 0.40, int(size * 0.060), int(size * 0.034))
    y = int(size * 0.26)
    for ln in lines:
        d.text((m, y), ln, font=f, fill=(255, 255, 255)); y += lh
    d.rectangle([m, y + 10, m + int(size * 0.12), y + 22], fill=accent)

    # gold CTA pill
    cy = int(size * 0.74)
    cta = "Book a free coaching call"
    cf = _font(int(size * 0.025))
    pill_w = int(d.textlength(cta, font=cf)) + int(size * 0.07)
    d.rounded_rectangle([m, cy, m + pill_w, cy + int(size * 0.072)],
                        int(size * 0.036), fill=accent)
    d.text((m + int(size * 0.035), cy + int(size * 0.022)), cta, font=cf, fill=(bg[0], bg[1], bg[2]))
    contact = (phone + "   " if phone else "") + web
    d.text((m, size - int(size * 0.075)), contact, font=_font(int(size * 0.025), False),
           fill=(200, 214, 234))
    base.convert("RGB").save(out_path, "PNG"); return out_path


def compose_property(photo_path, brand_key, brand_name, headline, website, out_path,
                     subline="Real estate coaching that actually closes", phone="", size=1080):
    th = THEMES.get(brand_key, DEFAULT); accent = th["accent"]; bg = th["bg"]
    web = website.replace("https://", "").replace("http://", "")
    base = _cover_square(Image.open(photo_path).convert("RGB"), size).convert("RGBA")
    dark = Image.new("RGBA", (size, size), (bg[0], bg[1], bg[2], 90))
    base = Image.alpha_composite(base, dark)

    # centered translucent panel
    pm = int(size * 0.10)
    panel = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rectangle([pm, pm, size - pm, size - pm],
                                    fill=(bg[0], bg[1], bg[2], 205))
    base = Image.alpha_composite(base, panel)
    d = ImageDraw.Draw(base)

    cx = size // 2
    _house_icon(d, cx, int(size * 0.155), int(size * 0.085), accent)
    nm = brand_name.upper()
    d.text((cx - d.textlength(nm, font=_font(int(size * 0.03))) / 2, int(size * 0.275)),
           nm, font=_font(int(size * 0.03)), fill=accent)

    f, lines, lh = _fit(d, headline, size - 2 * pm - int(size * 0.06), size * 0.30,
                        int(size * 0.062), int(size * 0.038))
    y = int(size * 0.36)
    for ln in lines:
        d.text((cx - d.textlength(ln, font=f) / 2, y), ln, font=f, fill=(255, 255, 255)); y += lh
    d.rectangle([cx - int(size * 0.09), y + 14, cx + int(size * 0.09), y + 18], fill=accent)

    sf = _font(int(size * 0.028), False)
    d.text((cx - d.textlength(subline, font=sf) / 2, y + int(size * 0.045)), subline,
           font=sf, fill=(205, 218, 236))
    contact = (phone + "    " if phone else "") + web
    cf = _font(int(size * 0.027), False)
    d.text((cx - d.textlength(contact, font=cf) / 2, size - int(size * 0.165)), contact,
           font=cf, fill=(235, 240, 248))
    base.convert("RGB").save(out_path, "PNG"); return out_path


def compose_abc(layout, photo_path, brand_key, brand_name, headline, website, out_path,
                phone="", cutout=None):
    if layout in (0, 1) and cutout:
        side = "right" if layout == 0 else "left"
        mode = "spotlight" if layout == 0 else "coach"
        return compose_cutout(cutout, brand_key, brand_name, headline, website, out_path,
                              side=side, mode=mode, phone=phone)
    if layout == 1:
        return compose_coachcard(photo_path, brand_key, brand_name, headline, website,
                                 out_path, phone=phone)
    if layout == 2:
        return compose_property(photo_path, brand_key, brand_name, headline, website,
                                out_path, phone=phone)
    return compose_spotlight(photo_path, brand_key, brand_name, headline, website,
                             out_path, phone=phone)


def compose(photo_path, brand_key, brand_name, headline, website, out_path, style=0, size=1080):
    th = THEMES.get(brand_key, DEFAULT)
    accent = th["accent"]
    bg = th["bg"]
    web = website.replace("https://", "").replace("http://", "")

    # Full photo, then a SOLID brand panel on the left for the text — so the
    # photo (and any faces) stays clean on the right.
    base = _cover_square(Image.open(photo_path).convert("RGB"), size).convert("RGBA")
    panel_w = int(size * 0.48)
    seam = int(size * 0.10)

    panel = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rectangle([0, 0, panel_w, size], fill=(bg[0], bg[1], bg[2], 255))
    for i in range(seam):                       # soft fade into the photo
        a = int(255 * (1 - i / seam))
        pd.line([(panel_w + i, 0), (panel_w + i, size)], fill=(bg[0], bg[1], bg[2], a))
    base = Image.alpha_composite(base, panel)
    d = ImageDraw.Draw(base)

    m = int(size * 0.065)
    tw = panel_w - int(size * 0.115)

    # brand label, top of panel
    d.rectangle([m, m + int(size * 0.015), m + int(size * 0.10), m + int(size * 0.015) + 8], fill=accent)
    d.text((m, m + int(size * 0.04)), brand_name.upper(),
           font=_font(int(size * 0.032)), fill=accent)

    # headline, bold, vertically centred in the panel
    f, lines, lh = _fit(d, headline, tw, size * 0.52, int(size * 0.072), int(size * 0.040))
    total = lh * len(lines)
    y = (size - total) // 2
    for ln in lines:
        d.text((m, y), ln, font=f, fill=(255, 255, 255))
        y += lh
    d.rectangle([m, y + int(size * 0.015), m + int(size * 0.14), y + int(size * 0.028)], fill=accent)

    # website, bottom of panel
    d.text((m, size - int(size * 0.075)), web,
           font=_font(int(size * 0.025), False), fill=(225, 232, 240))

    base.convert("RGB").save(out_path, "PNG")
    return out_path


# ================================================================ PORTRAIT (4:5) agent templates
def _phone_icon(d, x, y, s, c):
    d.ellipse([x, y + s * 0.55, x + s * 0.30, y + s * 0.85], fill=c)
    d.ellipse([x + s * 0.6, y, x + s * 0.90, y + s * 0.30], fill=c)
    d.line([(x + s * 0.2, y + s * 0.68), (x + s * 0.72, y + s * 0.16)], fill=c, width=max(2, int(s * 0.16)))


def _dotgrid(d, x, y, cols, rows, gap, r, c):
    for i in range(cols):
        for j in range(rows):
            cxp = x + i * gap; cyp = y + j * gap
            d.ellipse([cxp, cyp, cxp + r, cyp + r], fill=c)


def _logo_house(d, cx, y, w, c):
    half = w / 2
    roof = w * 0.45
    d.polygon([(cx - half, y + roof), (cx, y), (cx + half, y + roof)], fill=c)
    bw = w * 0.66
    d.rectangle([cx - bw / 2, y + roof, cx + bw / 2, y + w], fill=c)
    dw = w * 0.18
    d.rectangle([cx - dw / 2, y + w * 0.62, cx + dw / 2, y + w], fill=(11, 37, 69))


def _quote(d, x, y, s, c):
    for k in (0, int(s * 0.60)):
        d.ellipse([x + k, y, x + k + int(s * 0.40), y + int(s * 0.40)], fill=c)
        d.polygon([(x + k, y + int(s * 0.26)), (x + k + int(s * 0.30), y + int(s * 0.26)),
                   (x + k, y + int(s * 0.72))], fill=c)


def compose_portrait_spotlight(photo_path, brand_key, brand_name, headline, website, out_path,
                               person_name="JODY McNAMER", role="Agent Broker Coach", phone="",
                               W=1080, H=1350):
    th = THEMES.get(brand_key, DEFAULT); accent = th["accent"]; bg = th["bg"]; band = th.get("band", bg)
    web = website.replace("https://", "").replace("http://", "")
    base = Image.new("RGBA", (W, H), (bg[0], bg[1], bg[2], 255))
    # photo fills the left ~54%
    pw = int(W * 0.54)
    img = Image.open(photo_path).convert("RGB")
    photo = _cover(img, pw, H)
    base.paste(photo, (0, 0))
    d = ImageDraw.Draw(base)
    # navy panel right with a slight diagonal seam
    seam = int(W * 0.05)
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(panel).polygon([(pw, 0), (W, 0), (W, H), (pw - seam, H)],
                                  fill=(bg[0], bg[1], bg[2], 255))
    base = Image.alpha_composite(base, panel)
    d = ImageDraw.Draw(base)

    px = pw + int(W * 0.03); rt = W - int(W * 0.05); tw = rt - px
    _dotgrid(d, px, int(H * 0.05), 6, 5, int(W * 0.028), int(W * 0.012), (accent[0], accent[1], accent[2]))
    _quote(d, px, int(H * 0.155), int(H * 0.075), accent)
    f, lines, lh = _fit(d, headline, tw, H * 0.20, int(H * 0.040), int(H * 0.026))
    y = int(H * 0.26)
    for ln in lines:
        d.text((px, y), ln, font=f, fill=(255, 255, 255)); y += lh
    d.line([(px, y + 16), (rt, y + 16)], fill=accent, width=3)
    # CALL ME NOW button
    by = int(H * 0.58)
    d.rectangle([px, by, px + int(tw * 0.78), by + int(H * 0.052)], fill=(255, 255, 255))
    d.text((px + int(W * 0.03), by + int(H * 0.014)), "CALL ME NOW",
           font=_font(int(H * 0.024)), fill=(bg[0], bg[1], bg[2]))
    # name + role
    ny = int(H * 0.70)
    nf, nlines, nlh = _fit(d, person_name.upper(), tw, H * 0.12, int(H * 0.050), int(H * 0.034))
    for ln in nlines:
        d.text((px, ny), ln, font=nf, fill=(255, 255, 255)); ny += nlh
    d.text((px, ny + 6), role, font=_font(int(H * 0.024), False), fill=accent)
    # phone + email
    cy = ny + int(H * 0.06)
    if phone:
        _phone_icon(d, px, cy, int(H * 0.03), accent)
        d.text((px + int(H * 0.045), cy), phone, font=_font(int(H * 0.026)), fill=(255, 255, 255))
        cy += int(H * 0.05)
    d.text((px, cy), web, font=_font(int(H * 0.022), False), fill=(210, 222, 240))
    _logo_house(d, rt - int(W * 0.04), int(H * 0.90), int(W * 0.07), accent)
    base.convert("RGB").save(out_path, "PNG"); return out_path


def compose_portrait_quote(photo_path, brand_key, brand_name, headline, website, out_path,
                           person_name="Jody McNamer", phone="", W=1080, H=1350):
    th = THEMES.get(brand_key, DEFAULT); accent = th["accent"]; bg = th["bg"]; band = th.get("band", bg)
    web = website.replace("https://", "").replace("http://", "")
    base = Image.new("RGBA", (W, H), (bg[0], bg[1], bg[2], 255))
    d = ImageDraw.Draw(base)
    # @handle top-left
    d.line([(int(W * 0.05), int(H * 0.06)), (int(W * 0.14), int(H * 0.06))], fill=(255, 255, 255), width=3)
    d.text((int(W * 0.16), int(H * 0.05)), "@agentbrokercoach",
           font=_font(int(H * 0.022), False), fill=(235, 240, 248))
    # photo inset mid-left (framed)
    iw, ih = int(W * 0.40), int(H * 0.34)
    ix, iy = int(W * 0.05), int(H * 0.34)
    inset = _cover(Image.open(photo_path).convert("RGB"), iw, ih)
    d.rectangle([ix - 5, iy - 5, ix + iw + 5, iy + ih + 5], fill=accent)
    base.paste(inset, (ix, iy))
    d = ImageDraw.Draw(base)
    # big quote right
    qx = int(W * 0.50); qw = int(W * 0.45)
    f, lines, lh = _fit(d, headline, qw, H * 0.30, int(H * 0.048), int(H * 0.030))
    y = int(H * 0.20)
    for ln in lines:
        d.text((qx, y), ln, font=f, fill=(255, 255, 255)); y += lh
    d.rectangle([qx, y + 18, qx + int(W * 0.14), y + 24], fill=accent)
    d.text((qx, y + int(H * 0.05)), person_name, font=_font(int(H * 0.030)), fill=(255, 255, 255))
    cy = y + int(H * 0.10)
    if phone:
        _phone_icon(d, qx, cy, int(H * 0.03), accent)
        d.text((qx + int(H * 0.045), cy), phone, font=_font(int(H * 0.028)), fill=(255, 255, 255))
    # CALL NOW button (gold)
    by = cy + int(H * 0.06)
    d.rectangle([qx, by, qx + int(qw * 0.85), by + int(H * 0.05)], fill=accent)
    d.text((qx + int(W * 0.06), by + int(H * 0.013)), "CALL NOW",
           font=_font(int(H * 0.026)), fill=(bg[0], bg[1], bg[2]))
    _logo_house(d, int(W * 0.85), int(H * 0.88), int(W * 0.10), (255, 255, 255))
    d.text((qx, H - int(H * 0.05)), web, font=_font(int(H * 0.020), False), fill=(200, 214, 234))
    base.convert("RGB").save(out_path, "PNG"); return out_path


def compose_portrait_property(photo_path, brand_key, brand_name, headline, website, out_path,
                              subline="Real estate coaching that closes", phone="", W=1080, H=1350):
    th = THEMES.get(brand_key, DEFAULT); accent = th["accent"]; bg = th["bg"]
    web = website.replace("https://", "").replace("http://", "")
    base = Image.new("RGBA", (W, H), (bg[0], bg[1], bg[2], 255))
    d = ImageDraw.Draw(base)
    # title block top
    m = int(W * 0.06)
    d.rectangle([m, int(H * 0.05), m + int(W * 0.08), int(H * 0.05) + 8], fill=accent)
    d.text((m, int(H * 0.065)), brand_name.upper(), font=_font(int(H * 0.024)), fill=accent)
    f, lines, lh = _fit(d, headline, W - 2 * m, H * 0.16, int(H * 0.052), int(H * 0.034))
    y = int(H * 0.10)
    for ln in lines:
        d.text((m, y), ln, font=f, fill=(255, 255, 255)); y += lh
    # big rounded photo
    iw, ih = W - 2 * m, int(H * 0.52)
    iy = int(H * 0.30)
    photo = _rounded(_cover(Image.open(photo_path).convert("RGB"), iw, ih), int(W * 0.04))
    base.alpha_composite(photo, (m, iy))
    d = ImageDraw.Draw(base)
    # contact bar bottom
    cy = int(H * 0.88)
    d.rounded_rectangle([m, cy, W - m, cy + int(H * 0.07)], int(H * 0.02), outline=accent, width=3)
    cf = _font(int(H * 0.024), False)
    contact = (phone + "    " if phone else "") + web
    d.text((m + int(W * 0.04), cy + int(H * 0.022)), contact, font=cf, fill=(235, 240, 248))
    base.convert("RGB").save(out_path, "PNG"); return out_path


def compose_abc_portrait(layout, photo_path, brand_key, brand_name, headline, website, out_path, phone=""):
    if layout == 0:
        return compose_portrait_spotlight(photo_path, brand_key, brand_name, headline, website, out_path, phone=phone)
    if layout == 1:
        return compose_portrait_quote(photo_path, brand_key, brand_name, headline, website, out_path, phone=phone)
    return compose_portrait_property(photo_path, brand_key, brand_name, headline, website, out_path, phone=phone)
