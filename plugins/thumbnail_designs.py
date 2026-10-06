import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Default Colors & Settings
GLASS_WHITE = 60               # Frosted glass white level (0-255). 40 = clear, 90 = very white
ACCENT = (36, 161, 222, 255)   # Telegram blue color

# Add a font file named "font.ttf" in the bot folder for bold text
FONT_PATHS = [
    "font.ttf",
    "Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "arialbd.ttf",
]

_PROBE = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

# ======================= BASIC HELPERS =======================

def load_font(size):
    size = max(8, int(size))
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()

# ======================= DRAWING HELPERS =======================

def paste_rgba(dst, src, x, y):
    """alpha_composite - prevents crash even if position is negative"""
    x, y = int(x), int(y)
    if x < 0:
        src = src.crop((-x, 0, src.width, src.height))
        x = 0
    if y < 0:
        src = src.crop((0, -y, src.width, src.height))
        y = 0
    if x >= dst.width or y >= dst.height or src.width <= 0 or src.height <= 0:
        return
    dst.alpha_composite(src, dest=(x, y))

def text_h(font):
    return _PROBE.textbbox((0, 0), "Ag", font=font)[3]

def text_w(text, font):
    return _PROBE.textlength(text, font=font)

def block_h(font, n):
    return int(text_h(font) * 1.12 * (n - 1) + text_h(font))

def text_shadow(layer, xy, text, font, fill=(255, 255, 255, 255)):
    """Text with soft shadow - visible clearly even on bright backgrounds"""
    x, y = int(xy[0]), int(xy[1])
    size = getattr(font, "size", 30)
    blur = max(2, int(size * 0.07))
    off = max(1, int(size * 0.05))
    bb = _PROBE.textbbox((x, y), text, font=font)
    pad = blur * 3 + off
    bx, by = bb[0] - pad, bb[1] - pad
    w, h = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((x - bx, y - by + off), text, font=font, fill=(0, 0, 0, 125))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    paste_rgba(layer, sh, bx, by)
    ImageDraw.Draw(layer).text((x, y), text, font=font, fill=fill)

def draw_lines(layer, lines, font, x, y, fill=(255, 255, 255, 255), align="left", box_w=0):
    """Draws lines and returns total height used"""
    lh = text_h(font)
    step = lh * 1.12
    for i, line in enumerate(lines):
        tw = text_w(line, font)
        if align == "center":
            lx = x + (box_w - tw) / 2
        elif align == "right":
            lx = x + box_w - tw
        else:
            lx = x
        text_shadow(layer, (lx, y + i * step), line, font, fill)
    return block_h(font, len(lines))

def fit_lines(text, start, minimum, max_w, max_lines):
    """Reduces font size or wraps to 2 lines if title is too long"""
    size = int(start)
    while True:
        font = load_font(size)
        lines, cur = [], ""
        for word in text.split():
            trial = (cur + " " + word).strip()
            if not cur or text_w(trial, font) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        ok = len(lines) <= max_lines and all(text_w(l, font) <= max_w for l in lines)
        if ok:
            return font, lines
        if size <= minimum:
            lines = lines[:max_lines] or [text]
            last = lines[-1]
            while last and text_w(last + "...", font) > max_w:
                last = last[:-1]
            lines[-1] = last.rstrip() + "..."
            return font, lines
        size = max(int(minimum), int(size * 0.92))

def rounded_mask(w, h, radius):
    S = 3
    m = Image.new("L", (w * S, h * S), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=radius * S, fill=255)
    return m.resize((w, h), Image.LANCZOS)

def glass_panel(img, layer, box, radius, blur, white=None):
    """FROSTED GLASS panel: background blur + light white tint + shine border"""
    white = GLASS_WHITE if white is None else white
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.width, x1), min(img.height, y1)
    w, h = x1 - x0, y1 - y0
    if w <= 4 or h <= 4:
        return
    radius = max(0, min(int(radius), h // 2, w // 2))

    pad = int(blur * 2)
    bx0, by0 = max(0, x0 - pad), max(0, y0 - pad)
    bx1, by1 = min(img.width, x1 + pad), min(img.height, y1 + pad)
    region = img.crop((bx0, by0, bx1, by1)).filter(ImageFilter.GaussianBlur(blur))
    region = region.crop((x0 - bx0, y0 - by0, x0 - bx0 + w, y0 - by0 + h))
    region = Image.alpha_composite(region, Image.new("RGBA", region.size, (0, 0, 0, 22)))
    region = Image.alpha_composite(region, Image.new("RGBA", region.size, (255, 255, 255, white)))
    img.paste(region, (x0, y0), rounded_mask(w, h, radius))

    # Shine border
    S = 3
    bw = max(1, int(img.width / 1920 * 2.5))
    bl = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    ImageDraw.Draw(bl).rounded_rectangle(
        (0, 0, w * S - 1, h * S - 1), radius=radius * S,
        outline=(255, 255, 255, 140), width=bw * S
    )
    paste_rgba(layer, bl.resize((w, h), Image.LANCZOS), x0, y0)

def add_gradient_bottom(img, gh, max_alpha):
    gh = int(min(gh, img.height))
    grad = Image.linear_gradient("L").resize((img.width, gh))
    alpha = grad.point(lambda p: int(p * max_alpha / 255))
    dark = Image.new("RGBA", (img.width, gh), (0, 0, 0, 255))
    dark.putalpha(alpha)
    img.alpha_composite(dark, dest=(0, img.height - gh))

def draw_star(layer, cx, cy, r, fill):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    ImageDraw.Draw(layer).polygon(pts, fill=fill)

def telegram_icon(d):
    """Telegram blue circle + white paper plane"""
    S = 4
    big = d * S
    icon = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    dr = ImageDraw.Draw(icon)
    dr.ellipse([0, 0, big - 1, big - 1], fill=ACCENT)
    k = big / 100
    plane = [(22, 48), (77, 26), (66, 74), (50, 62), (43, 71), (40, 57)]
    dr.polygon([(x * k, y * k) for x, y in plane], fill=(255, 255, 255, 255))
    dr.line([(40 * k, 57 * k), (64 * k, 38 * k)], fill=ACCENT, width=max(1, int(2 * k)))
    return icon.resize((d, d), Image.LANCZOS)

def meta_text(info):
    parts = [info["type"]]
    if info["year"]:
        parts.append(info["year"])
    if info["rating"]:
        parts.append(f'{info["rating"]}/10')
    return "  •  ".join(p for p in parts if p)

# ======================= 6 THUMBNAIL DESIGNS =======================

def d_glass_card(img, layer, info, b):
    """1. FULL GLASS - bottom left frosted glass card"""
    W, H = img.size
    pad, m = int(40 * b), int(60 * b)
    tfont, lines = fit_lines(info["title"], 78 * b, 40 * b, W * 0.46, 2)
    mfont, gfont = load_font(30 * b), load_font(26 * b)
    meta = meta_text(info)
    genres = " / ".join(info["genres"])

    cw = max([text_w(l, tfont) for l in lines] + [text_w(meta, mfont), text_w(genres, gfont) if genres else 0])
    pw = int(cw + pad * 2)
    ph = int(pad + block_h(tfont, len(lines)) + 16 * b + text_h(mfont)
             + ((10 * b + text_h(gfont)) if genres else 0) + pad)
    x0, y0 = m, H - m - ph
    glass_panel(img, layer, (x0, y0, x0 + pw, y0 + ph), 36 * b, 22 * b)

    y = y0 + pad
    y += draw_lines(layer, lines, tfont, x0 + pad, y) + 16 * b
    y += draw_lines(layer, [meta], mfont, x0 + pad, y, fill=(255, 255, 255, 225))
    if genres:
        draw_lines(layer, [genres], gfont, x0 + pad, y + 10 * b, fill=(255, 255, 255, 190))

def d_cinematic(img, layer, info, b):
    """2. Cinematic - dark bottom gradient, big title, blue accent bar"""
    W, H = img.size
    m = int(70 * b)
    add_gradient_bottom(img, H * 0.55, 225)
    tfont, lines = fit_lines(info["title"], 120 * b, 56 * b, W * 0.7, 2)
    mfont = load_font(32 * b)
    bar_h, bar_w = max(3, int(7 * b)), int(130 * b)
    total = bar_h + 22 * b + block_h(tfont, len(lines)) + 14 * b + text_h(mfont)
    y = H - m - total
    ImageDraw.Draw(layer).rounded_rectangle((m, y, m + bar_w, y + bar_h), radius=bar_h // 2, fill=ACCENT)
    y += bar_h + 22 * b
    y += draw_lines(layer, lines, tfont, m, y) + 14 * b
    draw_lines(layer, [meta_text(info)], mfont, m, y, fill=(255, 255, 255, 215))

def d_glass_bar(img, layer, info, b):
    """3. FULL GLASS - bottom full width glass bar + rating star"""
    W, H = img.size
    m, pad = int(60 * b), int(34 * b)
    bw = W - 2 * m
    right_w = int(230 * b) if info["rating"] else 0
    tfont, lines = fit_lines(info["title"], 70 * b, 38 * b, bw - 2 * pad - right_w, 1)
    mfont = load_font(28 * b)
    ph = int(pad * 2 + text_h(tfont) + 10 * b + text_h(mfont))
    x0, y0 = m, H - m - ph
    glass_panel(img, layer, (x0, y0, x0 + bw, y0 + ph), 40 * b, 26 * b)

    draw_lines(layer, lines, tfont, x0 + pad, y0 + pad)
    parts = [info["type"], info["year"]]
    draw_lines(layer, ["  •  ".join(p for p in parts if p)], mfont,
               x0 + pad, y0 + pad + text_h(tfont) + 10 * b, fill=(255, 255, 255, 215))

    if info["rating"]:
        rf = load_font(54 * b)
        rt = info["rating"]
        r = 26 * b
        total = 2 * r + 14 * b + text_w(rt, rf)
        sx = x0 + bw - pad - total
        cy = y0 + ph / 2
        draw_star(layer, sx + r, cy, r, (255, 200, 0, 255))
        bb = _PROBE.textbbox((0, 0), rt, font=rf)
        text_shadow(layer, (sx + 2 * r + 14 * b, cy - (bb[1] + bb[3]) / 2), rt, rf)

def d_center(img, layer, info, b):
    """4. Center Title - bottom center big title, light gradient"""
    W, H = img.size
    m = int(70 * b)
    add_gradient_bottom(img, H * 0.42, 190)
    box_w = int(W * 0.8)
    x = (W - box_w) // 2
    tfont, lines = fit_lines(info["title"], 104 * b, 50 * b, box_w, 2)
    mfont = load_font(30 * b)
    total = block_h(tfont, len(lines)) + 18 * b + max(3, int(4 * b)) + 14 * b + text_h(mfont)
    y = H - m - total
    y += draw_lines(layer, lines, tfont, x, y, align="center", box_w=box_w) + 18 * b
    lw, lh = int(90 * b), max(3, int(4 * b))
    ImageDraw.Draw(layer).rounded_rectangle(
        (W / 2 - lw / 2, y, W / 2 + lw / 2, y + lh), radius=lh // 2, fill=ACCENT)
    y += lh + 14 * b
    draw_lines(layer, [meta_text(info)], mfont, x, y, fill=(255, 255, 255, 210), align="center", box_w=box_w)

def d_glass_center(img, layer, info, b):
    """5. FULL GLASS - big frosted glass panel in the center"""
    W, H = img.size
    pad = int(56 * b)
    tfont, lines = fit_lines(info["title"], 96 * b, 48 * b, W * 0.56, 3)
    mfont, gfont = load_font(32 * b), load_font(26 * b)
    meta = meta_text(info)
    genres = " / ".join(info["genres"])

    cw = max([text_w(l, tfont) for l in lines] + [text_w(meta, mfont), text_w(genres, gfont) if genres else 0])
    pw = int(cw + pad * 2)
    ph = int(pad + block_h(tfont, len(lines)) + 22 * b + text_h(mfont)
             + ((12 * b + text_h(gfont)) if genres else 0) + pad)
    x0, y0 = (W - pw) // 2, (H - ph) // 2
    glass_panel(img, layer, (x0, y0, x0 + pw, y0 + ph), 48 * b, 30 * b, white=GLASS_WHITE + 10)

    y = y0 + pad
    y += draw_lines(layer, lines, tfont, x0, y, align="center", box_w=pw) + 22 * b
    y += draw_lines(layer, [meta], mfont, x0, y, fill=(255, 255, 255, 225), align="center", box_w=pw)
    if genres:
        draw_lines(layer, [genres], gfont, x0, y + 12 * b, fill=(255, 255, 255, 190), align="center", box_w=pw)

def d_side(img, layer, info, b):
    """6. Side Banner - left side dark gradient, title stacked + rating"""
    W, H = img.size
    gw = int(W * 0.55)
    grad = Image.linear_gradient("L").transpose(Image.ROTATE_270).resize((gw, H))  
    alpha = grad.point(lambda p: int(p * 0.9))
    dark = Image.new("RGBA", (gw, H), (0, 0, 0, 255))
    dark.putalpha(alpha)
    img.alpha_composite(dark, dest=(0, 0))

    m = int(80 * b)
    tfont, lines = fit_lines(info["title"], 96 * b, 50 * b, W * 0.36, 4)
    mfont, gfont = load_font(32 * b), load_font(26 * b)
    genres = " / ".join(info["genres"])
    bar_h, bar_w = max(3, int(7 * b)), int(130 * b)
    total = (bar_h + 24 * b + block_h(tfont, len(lines)) + 18 * b + text_h(mfont)
             + ((10 * b + text_h(gfont)) if genres else 0))
    y = (H - total) / 2
    ImageDraw.Draw(layer).rounded_rectangle((m, y, m + bar_w, y + bar_h), radius=bar_h // 2, fill=ACCENT)
    y += bar_h + 24 * b
    y += draw_lines(layer, lines, tfont, m, y) + 18 * b
    y += draw_lines(layer, [meta_text(info)], mfont, m, y, fill=(255, 255, 255, 225))
    if genres:
        draw_lines(layer, [genres], gfont, m, y + 10 * b, fill=(255, 255, 255, 190))

# Dictionary for mapping designs
DESIGNS = {
    1: ("🪟 Glass Card", d_glass_card),
    2: ("🎬 Cinematic", d_cinematic),
    3: ("🌫 Glass Bar", d_glass_bar),
    4: ("✨ Center Title", d_center),
    5: ("💎 Glass Center", d_glass_center),
    6: ("📰 Side Banner", d_side),
}

def design_name(st):
    return DESIGNS[st][0] if st in DESIGNS else "Plain (Watermark only)"
