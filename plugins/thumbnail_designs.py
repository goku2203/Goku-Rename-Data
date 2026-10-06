import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Default Colors & Settings
GLASS_WHITE = 60               # Frosted glass white level (0-255). 40 = clear, 90 = very white
ACCENT = (36, 161, 222, 255)   # Telegram blue color

# Font search paths
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

def text_shadow(layer, xy, text, font, fill=(255, 255, 255, 255), shadow_color=(0, 0, 0, 140)):
    """Text with soft ambient shadow for maximum readability on bright backgrounds"""
    x, y = int(xy[0]), int(xy[1])
    size = getattr(font, "size", 30)
    blur = max(2, int(size * 0.08))
    off = max(1, int(size * 0.06))
    bb = _PROBE.textbbox((x, y), text, font=font)
    pad = blur * 3 + off
    bx, by = bb[0] - pad, bb[1] - pad
    w, h = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((x - bx, y - by + off), text, font=font, fill=shadow_color)
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
    """Reduces font size or wraps lines to fit within max_w and max_lines"""
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

def glass_panel(img, layer, box, radius, blur, white=None, border_color=(255, 255, 255, 140)):
    """FROSTED GLASS panel: background blur + light white tint + specular shine border"""
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
    region = Image.alpha_composite(region, Image.new("RGBA", region.size, (0, 0, 0, 30)))
    region = Image.alpha_composite(region, Image.new("RGBA", region.size, (255, 255, 255, white)))
    img.paste(region, (x0, y0), rounded_mask(w, h, radius))

    # Specular shine border
    S = 3
    bw = max(1, int(img.width / 1920 * 2.2))
    bl = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    ImageDraw.Draw(bl).rounded_rectangle(
        (0, 0, w * S - 1, h * S - 1), radius=radius * S,
        outline=border_color, width=bw * S
    )
    paste_rgba(layer, bl.resize((w, h), Image.LANCZOS), x0, y0)

def add_smooth_gradient_bottom(img, gh, max_alpha=230):
    """Smooth non-linear dark gradient for cinematic contrast"""
    gh = int(min(gh, img.height))
    grad = Image.linear_gradient("L").resize((img.width, gh))
    alpha = grad.point(lambda p: int((p / 255.0) ** 1.3 * max_alpha))
    dark = Image.new("RGBA", (img.width, gh), (0, 0, 0, 255))
    dark.putalpha(alpha)
    img.alpha_composite(dark, dest=(0, img.height - gh))

def add_angled_gradient_left(img, gw, max_alpha=225):
    """Smooth horizontal dark vignette on the left"""
    gw = int(min(gw, img.width))
    grad = Image.linear_gradient("L").transpose(Image.ROTATE_270).resize((gw, img.height))
    alpha = grad.point(lambda p: int((p / 255.0) ** 1.2 * max_alpha))
    dark = Image.new("RGBA", (gw, img.height), (0, 0, 0, 255))
    dark.putalpha(alpha)
    img.alpha_composite(dark, dest=(0, 0))

def draw_star(layer, cx, cy, r, fill=(255, 204, 0, 255)):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    ImageDraw.Draw(layer).polygon(pts, fill=fill)

def draw_pill_badge(layer, x, y, text, font, bg_color, border_color=None, text_color=(255, 255, 255, 255), pad_x=16, pad_y=6):
    """Draws a rounded capsule tag/badge and returns its (width, height)"""
    tw = text_w(text, font)
    th = text_h(font)
    w = int(tw + pad_x * 2)
    h = int(th + pad_y * 2)
    radius = h // 2
    ImageDraw.Draw(layer).rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=bg_color)
    if border_color:
        ImageDraw.Draw(layer).rounded_rectangle((x, y, x + w, y + h), radius=radius, outline=border_color, width=max(1, int(pad_y * 0.25)))
    bb = _PROBE.textbbox((0, 0), text, font=font)
    tx = x + pad_x - bb[0]
    ty = y + pad_y - bb[1]
    ImageDraw.Draw(layer).text((tx, ty), text, font=font, fill=text_color)
    return w, h

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


# ======================= 6 BRAND NEW THUMBNAIL DESIGNS =======================

def d_cyber_neon(img, layer, info, b):
    """1. 🌟 Cyber Glow: Tokyo Cyberpunk / Anime Neon with Cyan-Violet Aura"""
    W, H = img.size
    m = int(70 * b)
    add_smooth_gradient_bottom(img, H * 0.58, 230)
    
    tfont, lines = fit_lines(info["title"], 108 * b, 50 * b, W * 0.72, 2)
    sfont, gfont = load_font(26 * b), load_font(24 * b)
    
    badge_h = int(36 * b)
    bar_h, bar_w = max(3, int(5 * b)), int(160 * b)
    th_total = block_h(tfont, len(lines))
    meta_h = int(36 * b)
    
    total_h = badge_h + 16 * b + th_total + 16 * b + bar_h + 16 * b + meta_h
    y = H - m - total_h
    
    # Category tag
    cat_text = f"⚡ {info['type'].upper()}" if info.get("type") else "⚡ ANIME"
    w1, _ = draw_pill_badge(layer, m, y, cat_text, sfont, (0, 240, 255, 30), border_color=(0, 240, 255, 200), text_color=(0, 240, 255, 255), pad_x=16 * b, pad_y=6 * b)
    
    if info.get("year"):
        draw_pill_badge(layer, m + w1 + 12 * b, y, info["year"], sfont, (255, 255, 255, 25), border_color=(255, 255, 255, 80), text_color=(255, 255, 255, 230), pad_x=14 * b, pad_y=6 * b)
    
    y += badge_h + 16 * b
    # Title
    y += draw_lines(layer, lines, tfont, m, y) + 16 * b
    
    # Gradient accent bar (Cyan to Violet)
    for i in range(bar_w):
        t = i / bar_w
        r = int(0 * (1 - t) + 168 * t)
        g = int(240 * (1 - t) + 85 * t)
        bl_c = int(255 * (1 - t) + 247 * t)
        ImageDraw.Draw(layer).line([(m + i, y), (m + i, y + bar_h)], fill=(r, g, bl_c, 255))
    y += bar_h + 16 * b
    
    # Rating badge + Genres
    cur_x = m
    if info.get("rating"):
        rw, _ = draw_pill_badge(layer, cur_x, y, f"★ {info['rating']}", sfont, (255, 204, 0, 35), border_color=(255, 204, 0, 220), text_color=(255, 215, 0, 255), pad_x=16 * b, pad_y=6 * b)
        cur_x += rw + 14 * b
    
    for g in info.get("genres", [])[:3]:
        gw, _ = draw_pill_badge(layer, cur_x, y, g, gfont, (0, 240, 255, 20), border_color=(0, 240, 255, 100), text_color=(220, 245, 255, 220), pad_x=14 * b, pad_y=6 * b)
        cur_x += gw + 10 * b

def d_cinematic_prime(img, layer, info, b):
    """2. 🎬 Cinematic Prime: Netflix/IMAX Minimalist with Scarlet Accent Bar"""
    W, H = img.size
    m = int(75 * b)
    add_smooth_gradient_bottom(img, H * 0.60, 235)
    
    tfont, lines = fit_lines(info["title"], 115 * b, 54 * b, W * 0.70, 2)
    mfont = load_font(30 * b)
    
    bar_w = max(4, int(8 * b))
    th_total = block_h(tfont, len(lines))
    meta_h = text_h(mfont)
    
    total_h = th_total + 18 * b + meta_h
    y = H - m - total_h
    
    # Crimson accent bar
    ImageDraw.Draw(layer).rounded_rectangle((m, y, m + bar_w, y + th_total), radius=bar_w // 2, fill=(229, 9, 20, 255))
    
    # Title
    draw_lines(layer, lines, tfont, m + bar_w + int(24 * b), y)
    y += th_total + 18 * b
    
    # Metadata line
    parts = []
    if info.get("type"):
        parts.append(info["type"].upper())
    if info.get("year"):
        parts.append(info["year"])
    if info.get("rating"):
        parts.append(f"★ {info['rating']}")
    if info.get("genres"):
        parts.append(" • ".join(info["genres"]))
    
    meta_str = "   |   ".join(parts)
    draw_lines(layer, [meta_str], mfont, m + bar_w + int(24 * b), y, fill=(255, 255, 255, 220))

def d_vision_glass(img, layer, info, b):
    """3. 💎 Vision Glass: Modern Floating Frosted Glass Dock with Specular Shine"""
    W, H = img.size
    pad, m = int(45 * b), int(60 * b)
    tfont, lines = fit_lines(info["title"], 84 * b, 44 * b, W * 0.50, 2)
    sfont, gfont = load_font(28 * b), load_font(24 * b)
    
    cw = max([text_w(l, tfont) for l in lines] + [int(320 * b)])
    pw = int(cw + pad * 2)
    ph = int(pad + 36 * b + 16 * b + block_h(tfont, len(lines)) + 16 * b + 36 * b + pad)
    
    x0, y0 = m, H - m - ph
    glass_panel(img, layer, (x0, y0, x0 + pw, y0 + ph), 36 * b, 26 * b, white=55)
    
    # Top row inside card: Type + Year & Rating
    y = y0 + pad
    cur_x = x0 + pad
    if info.get("type"):
        tw, _ = draw_pill_badge(layer, cur_x, y, info["type"].upper(), sfont, (255, 255, 255, 35), border_color=(255, 255, 255, 90), text_color=(255, 255, 255, 240), pad_x=14 * b, pad_y=4 * b)
        cur_x += tw + 10 * b
    if info.get("year"):
        yw, _ = draw_pill_badge(layer, cur_x, y, info["year"], sfont, (255, 255, 255, 20), border_color=(255, 255, 255, 60), text_color=(255, 255, 255, 210), pad_x=12 * b, pad_y=4 * b)
        cur_x += yw + 10 * b
    
    if info.get("rating"):
        draw_pill_badge(layer, x0 + pw - pad - int(120 * b), y, f"★ {info['rating']}", sfont, (255, 204, 0, 40), border_color=(255, 204, 0, 200), text_color=(255, 215, 0, 255), pad_x=14 * b, pad_y=4 * b)
    
    y += 36 * b + 16 * b
    # Title
    y += draw_lines(layer, lines, tfont, x0 + pad, y) + 16 * b
    
    # Genre capsules
    cur_x = x0 + pad
    for g in info.get("genres", [])[:3]:
        gw, _ = draw_pill_badge(layer, cur_x, y, g, gfont, (255, 255, 255, 20), border_color=(255, 255, 255, 60), text_color=(240, 240, 245, 215), pad_x=14 * b, pad_y=4 * b)
        cur_x += gw + 10 * b

def d_tokyo_action(img, layer, info, b):
    """4. 🎌 Tokyo Action: Dynamic Shonen Anime Cover with Fiery Slash"""
    W, H = img.size
    m = int(75 * b)
    add_angled_gradient_left(img, W * 0.60, 230)
    
    tfont, lines = fit_lines(info["title"], 104 * b, 50 * b, W * 0.44, 3)
    sfont, gfont = load_font(28 * b), load_font(24 * b)
    
    bar_h, bar_w = max(3, int(6 * b)), int(140 * b)
    th_total = block_h(tfont, len(lines))
    
    total_h = 36 * b + 16 * b + th_total + 16 * b + bar_h + 16 * b + 36 * b
    y = (H - total_h) / 2 + int(40 * b)
    
    # Action Badge
    tag = f"🔥 {info['type'].upper()}" if info.get("type") else "🔥 ANIME"
    w1, _ = draw_pill_badge(layer, m, y, tag, sfont, (255, 107, 0, 210), border_color=(255, 170, 0, 255), text_color=(255, 255, 255, 255), pad_x=16 * b, pad_y=5 * b)
    
    if info.get("rating"):
        draw_pill_badge(layer, m + w1 + 12 * b, y, f"★ {info['rating']}", sfont, (20, 20, 25, 200), border_color=(255, 204, 0, 220), text_color=(255, 215, 0, 255), pad_x=14 * b, pad_y=5 * b)
    
    y += 36 * b + 16 * b
    y += draw_lines(layer, lines, tfont, m, y) + 16 * b
    
    # Orange horizontal strike bar
    ImageDraw.Draw(layer).rounded_rectangle((m, y, m + bar_w, y + bar_h), radius=bar_h // 2, fill=(255, 107, 0, 255))
    y += bar_h + 16 * b
    
    # Meta / genres
    parts = []
    if info.get("year"):
        parts.append(info["year"])
    if info.get("genres"):
        parts.extend(info["genres"][:3])
    draw_lines(layer, [" ・ ".join(parts)], gfont, m, y, fill=(255, 235, 220, 220))

def d_aurora_horizon(img, layer, info, b):
    """5. 🌌 Aurora Horizon: Full-Width Frosted Dock with Glowing Top Hairline"""
    W, H = img.size
    m, pad = int(50 * b), int(30 * b)
    bw = W - 2 * m
    right_w = int(240 * b) if info.get("rating") else 0
    
    tfont, lines = fit_lines(info["title"], 72 * b, 40 * b, bw - 2 * pad - right_w, 1)
    mfont = load_font(26 * b)
    ph = int(pad * 2 + text_h(tfont) + 10 * b + text_h(mfont))
    x0, y0 = m, H - m - ph
    
    glass_panel(img, layer, (x0, y0, x0 + bw, y0 + ph), 28 * b, 24 * b, white=55)
    
    # Aurora top border line (Cyan -> Magenta -> Gold)
    for i in range(bw):
        t = i / bw
        if t < 0.5:
            f = t / 0.5
            r = int(0 * (1 - f) + 255 * f)
            g = int(229 * (1 - f) + 42 * f)
            bl_c = int(255 * (1 - f) + 133 * f)
        else:
            f = (t - 0.5) / 0.5
            r = 255
            g = int(42 * (1 - f) + 184 * f)
            bl_c = int(133 * (1 - f) + 0 * f)
        ImageDraw.Draw(layer).line([(x0 + i, y0), (x0 + i, y0 + max(2, int(3 * b)))], fill=(r, g, bl_c, 240))
        
    # Title
    draw_lines(layer, lines, tfont, x0 + pad, y0 + pad)
    
    # Subtitle
    parts = []
    if info.get("type"):
        parts.append(info["type"])
    if info.get("year"):
        parts.append(info["year"])
    if info.get("genres"):
        parts.append(" / ".join(info["genres"]))
    draw_lines(layer, ["  •  ".join(parts)], mfont, x0 + pad, y0 + pad + text_h(tfont) + 10 * b, fill=(240, 245, 255, 215))
    
    # Right rating pill
    if info.get("rating"):
        rx = x0 + bw - pad - int(180 * b)
        ry = y0 + (ph - int(44 * b)) // 2
        draw_pill_badge(layer, rx, ry, f"★ {info['rating']}", load_font(32 * b), (255, 204, 0, 35), border_color=(255, 204, 0, 220), text_color=(255, 215, 0, 255), pad_x=16 * b, pad_y=6 * b)

def d_royale_gold(img, layer, info, b):
    """6. 🏆 Royale Gold: Luxury Premiere with Metallic Gold Framing & Crown Badge"""
    W, H = img.size
    m = int(75 * b)
    add_smooth_gradient_bottom(img, H * 0.56, 230)
    
    tfont, lines = fit_lines(info["title"], 106 * b, 50 * b, W * 0.72, 2)
    sfont, mfont = load_font(26 * b), load_font(28 * b)
    
    badge_h = int(36 * b)
    bar_h, bar_w = max(2, int(4 * b)), int(180 * b)
    th_total = block_h(tfont, len(lines))
    meta_h = text_h(mfont)
    
    total_h = badge_h + 16 * b + th_total + 14 * b + bar_h + 16 * b + meta_h
    y = H - m - total_h
    
    # Gold Prestige Badge
    badge_txt = f"👑 PREMIERE • {info['rating']} ★" if info.get("rating") else "👑 OFFICIAL PREMIERE"
    draw_pill_badge(layer, m, y, badge_txt, sfont, (245, 158, 11, 40), border_color=(245, 158, 11, 230), text_color=(255, 215, 0, 255), pad_x=18 * b, pad_y=6 * b)
    y += badge_h + 16 * b
    
    # Title
    y += draw_lines(layer, lines, tfont, m, y) + 14 * b
    
    # Gold Hairline Bar
    ImageDraw.Draw(layer).rounded_rectangle((m, y, m + bar_w, y + bar_h), radius=bar_h // 2, fill=(245, 158, 11, 230))
    y += bar_h + 16 * b
    
    # Meta
    parts = []
    if info.get("type"):
        parts.append(info["type"].upper())
    if info.get("year"):
        parts.append(info["year"])
    if info.get("genres"):
        parts.extend([g.upper() for g in info["genres"][:3]])
    draw_lines(layer, ["   //   ".join(parts)], mfont, m, y, fill=(255, 240, 220, 215))

# ======================= DESIGNS REGISTRY =======================

DESIGNS = {
    1: ("🌟 Cyber Glow", d_cyber_neon),
    2: ("🎬 Cinematic Prime", d_cinematic_prime),
    3: ("💎 Vision Glass", d_vision_glass),
    4: ("🎌 Tokyo Action", d_tokyo_action),
    5: ("🌌 Aurora Horizon", d_aurora_horizon),
    6: ("🏆 Royale Gold", d_royale_gold),
}

def design_name(st):
    return DESIGNS[st][0] if st in DESIGNS else "Plain (Watermark only)"
