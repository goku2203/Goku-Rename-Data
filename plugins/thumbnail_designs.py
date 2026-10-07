import io
import math
import random
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


# ======================= 12 ORIGINAL THUMBNAIL DESIGNS =======================

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

def d_cyber_logo(img, layer, info, b):
    """7. 🔥 Cyber Logo: Tokyo Cyberpunk with Official TMDB Title Logo (Fallback to styled text)"""
    W, H = img.size
    m = int(70 * b)
    add_smooth_gradient_bottom(img, H * 0.58, 230)
    
    sfont, gfont = load_font(26 * b), load_font(24 * b)
    badge_h = int(36 * b)
    bar_h, bar_w = max(3, int(5 * b)), int(160 * b)
    meta_h = int(36 * b)
    
    logo_img = None
    if info.get("logo_bytes"):
        try:
            raw_logo = Image.open(io.BytesIO(info["logo_bytes"])).convert("RGBA")
            max_lw = int(W * 0.46)
            max_lh = int(140 * b)
            scale_ratio = min(max_lw / raw_logo.width, max_lh / raw_logo.height, 1.0)
            lw = max(10, int(raw_logo.width * scale_ratio))
            lh = max(10, int(raw_logo.height * scale_ratio))
            logo_img = raw_logo.resize((lw, lh), Image.LANCZOS)
        except Exception:
            logo_img = None

    if logo_img:
        logo_h = logo_img.height
        total_h = badge_h + 16 * b + logo_h + 16 * b + bar_h + 16 * b + meta_h
        y = H - m - total_h
        
        # Category tag
        cat_text = f"⚡ {info['type'].upper()}" if info.get("type") else "⚡ ANIME"
        w1, _ = draw_pill_badge(layer, m, y, cat_text, sfont, (0, 240, 255, 30), border_color=(0, 240, 255, 200), text_color=(0, 240, 255, 255), pad_x=16 * b, pad_y=6 * b)
        if info.get("year"):
            draw_pill_badge(layer, m + w1 + 12 * b, y, info["year"], sfont, (255, 255, 255, 25), border_color=(255, 255, 255, 80), text_color=(255, 255, 255, 230), pad_x=14 * b, pad_y=6 * b)
        
        y += badge_h + 16 * b
        
        # Soft cyan neon aura glow behind logo
        sh_blur = max(2, int(6 * b))
        sh_mask = Image.new("RGBA", (logo_img.width + sh_blur * 4, logo_img.height + sh_blur * 4), (0, 0, 0, 0))
        sh_mask.paste((0, 240, 255, 120), (sh_blur * 2, sh_blur * 2), logo_img.split()[3])
        sh_mask = sh_mask.filter(ImageFilter.GaussianBlur(sh_blur))
        paste_rgba(layer, sh_mask, m - sh_blur * 2, int(y) - sh_blur * 2)
        paste_rgba(layer, logo_img, m, int(y))
        y += logo_h + 16 * b
    else:
        # Fallback to Cyber Glow styled text title if no logo
        tfont, lines = fit_lines(info["title"], 108 * b, 50 * b, W * 0.72, 2)
        th_total = block_h(tfont, len(lines))
        total_h = badge_h + 16 * b + th_total + 16 * b + bar_h + 16 * b + meta_h
        y = H - m - total_h
        
        cat_text = f"⚡ {info['type'].upper()}" if info.get("type") else "⚡ ANIME"
        w1, _ = draw_pill_badge(layer, m, y, cat_text, sfont, (0, 240, 255, 30), border_color=(0, 240, 255, 200), text_color=(0, 240, 255, 255), pad_x=16 * b, pad_y=6 * b)
        if info.get("year"):
            draw_pill_badge(layer, m + w1 + 12 * b, y, info["year"], sfont, (255, 255, 255, 25), border_color=(255, 255, 255, 80), text_color=(255, 255, 255, 230), pad_x=14 * b, pad_y=6 * b)
        y += badge_h + 16 * b
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

def d_crimson_phantom(img, layer, info, b):
    """8. 🩸 Crimson Phantom: Dark Manga / Bloodline Cyberpunk with Angled Slash"""
    W, H = img.size
    m = int(72 * b)
    add_smooth_gradient_bottom(img, H * 0.60, 235)
    
    tfont, lines = fit_lines(info["title"], 112 * b, 52 * b, W * 0.70, 2)
    sfont, gfont = load_font(26 * b), load_font(24 * b)
    
    badge_h = int(36 * b)
    bar_h, bar_w = max(3, int(6 * b)), int(170 * b)
    th_total = block_h(tfont, len(lines))
    meta_h = int(36 * b)
    
    total_h = badge_h + 16 * b + th_total + 16 * b + bar_h + 16 * b + meta_h
    y = H - m - total_h
    
    # Bloodline tag
    tag = f"🩸 {info['type'].upper()}" if info.get("type") else "🩸 ANIME"
    w1, _ = draw_pill_badge(layer, m, y, tag, sfont, (220, 20, 60, 45), border_color=(255, 45, 85, 230), text_color=(255, 210, 220, 255), pad_x=16 * b, pad_y=6 * b)
    if info.get("year"):
        draw_pill_badge(layer, m + w1 + 12 * b, y, info["year"], sfont, (20, 20, 25, 180), border_color=(255, 45, 85, 100), text_color=(255, 230, 235, 230), pad_x=14 * b, pad_y=6 * b)
        
    y += badge_h + 16 * b
    y += draw_lines(layer, lines, tfont, m, y) + 16 * b
    
    # Crimson neon gradient bar
    for i in range(bar_w):
        t = i / bar_w
        r = int(255 * (1 - t) + 180 * t)
        g = int(20 * (1 - t) + 0 * t)
        bl_c = int(60 * (1 - t) + 120 * t)
        ImageDraw.Draw(layer).line([(m + i, y), (m + i, y + bar_h)], fill=(r, g, bl_c, 255))
    y += bar_h + 16 * b
    
    cur_x = m
    if info.get("rating"):
        rw, _ = draw_pill_badge(layer, cur_x, y, f"★ {info['rating']}", sfont, (255, 190, 0, 40), border_color=(255, 200, 0, 230), text_color=(255, 215, 0, 255), pad_x=16 * b, pad_y=6 * b)
        cur_x += rw + 14 * b
    for g in info.get("genres", [])[:3]:
        gw, _ = draw_pill_badge(layer, cur_x, y, g, gfont, (255, 40, 80, 25), border_color=(255, 50, 90, 110), text_color=(255, 225, 230, 225), pad_x=14 * b, pad_y=6 * b)
        cur_x += gw + 10 * b

def d_synthwave_neon(img, layer, info, b):
    """9. 🌸 Synthwave Neon: 80s Retro Synth Aura (Hot Pink to Electric Cyan)"""
    W, H = img.size
    m = int(70 * b)
    add_smooth_gradient_bottom(img, H * 0.58, 230)
    
    tfont, lines = fit_lines(info["title"], 106 * b, 48 * b, W * 0.72, 2)
    sfont, gfont = load_font(26 * b), load_font(24 * b)
    
    badge_h = int(36 * b)
    bar_h, bar_w = max(3, int(6 * b)), int(180 * b)
    th_total = block_h(tfont, len(lines))
    meta_h = int(36 * b)
    
    total_h = badge_h + 16 * b + th_total + 16 * b + bar_h + 16 * b + meta_h
    y = H - m - total_h
    
    # Retro Synth Badge
    tag = f"🌸 {info['type'].upper()}" if info.get("type") else "🌸 RETROWAVE"
    w1, _ = draw_pill_badge(layer, m, y, tag, sfont, (255, 0, 128, 45), border_color=(255, 0, 160, 230), text_color=(255, 200, 240, 255), pad_x=16 * b, pad_y=6 * b)
    if info.get("year"):
        draw_pill_badge(layer, m + w1 + 12 * b, y, info["year"], sfont, (30, 15, 45, 180), border_color=(0, 240, 255, 120), text_color=(200, 245, 255, 230), pad_x=14 * b, pad_y=6 * b)
        
    y += badge_h + 16 * b
    y += draw_lines(layer, lines, tfont, m, y) + 16 * b
    
    # Hot Pink -> Cyan Gradient Bar
    for i in range(bar_w):
        t = i / bar_w
        r = int(255 * (1 - t) + 0 * t)
        g = int(0 * (1 - t) + 240 * t)
        bl_c = int(128 * (1 - t) + 255 * t)
        ImageDraw.Draw(layer).line([(m + i, y), (m + i, y + bar_h)], fill=(r, g, bl_c, 255))
    y += bar_h + 16 * b
    
    cur_x = m
    if info.get("rating"):
        rw, _ = draw_pill_badge(layer, cur_x, y, f"★ {info['rating']}", sfont, (255, 204, 0, 40), border_color=(255, 215, 0, 230), text_color=(255, 215, 0, 255), pad_x=16 * b, pad_y=6 * b)
        cur_x += rw + 14 * b
    for g in info.get("genres", [])[:3]:
        gw, _ = draw_pill_badge(layer, cur_x, y, g, gfont, (0, 240, 255, 25), border_color=(0, 240, 255, 110), text_color=(220, 245, 255, 220), pad_x=14 * b, pad_y=6 * b)
        cur_x += gw + 10 * b

def d_glacial_frost(img, layer, info, b):
    """10. ❄️ Glacial Frost: Ice Crystalline Glass Dock with Metallic Silver Accents"""
    W, H = img.size
    pad, m = int(45 * b), int(60 * b)
    tfont, lines = fit_lines(info["title"], 86 * b, 46 * b, W * 0.54, 2)
    sfont, gfont = load_font(28 * b), load_font(24 * b)
    
    cw = max([text_w(l, tfont) for l in lines] + [int(320 * b)])
    pw = int(cw + pad * 2)
    ph = int(pad + 36 * b + 16 * b + block_h(tfont, len(lines)) + 16 * b + 36 * b + pad)
    
    x0, y0 = m, H - m - ph
    glass_panel(img, layer, (x0, y0, x0 + pw, y0 + ph), 34 * b, 28 * b, white=45, border_color=(180, 225, 255, 180))
    
    # Inside Ice Card
    y = y0 + pad
    cur_x = x0 + pad
    tag = f"❄️ {info['type'].upper()}" if info.get("type") else "❄️ CINEMA"
    tw, _ = draw_pill_badge(layer, cur_x, y, tag, sfont, (180, 225, 255, 35), border_color=(180, 225, 255, 140), text_color=(220, 245, 255, 240), pad_x=14 * b, pad_y=5 * b)
    cur_x += tw + 10 * b
    if info.get("year"):
        yw, _ = draw_pill_badge(layer, cur_x, y, info["year"], sfont, (10, 25, 40, 160), border_color=(180, 225, 255, 80), text_color=(200, 235, 255, 210), pad_x=12 * b, pad_y=5 * b)
        cur_x += yw + 10 * b
    if info.get("rating"):
        draw_pill_badge(layer, x0 + pw - pad - int(120 * b), y, f"★ {info['rating']}", sfont, (255, 204, 0, 40), border_color=(255, 204, 0, 210), text_color=(255, 215, 0, 255), pad_x=14 * b, pad_y=5 * b)
        
    y += 36 * b + 16 * b
    y += draw_lines(layer, lines, tfont, x0 + pad, y) + 16 * b
    
    cur_x = x0 + pad
    for g in info.get("genres", [])[:3]:
        gw, _ = draw_pill_badge(layer, cur_x, y, g, gfont, (180, 225, 255, 20), border_color=(180, 225, 255, 80), text_color=(215, 240, 255, 220), pad_x=14 * b, pad_y=5 * b)
        cur_x += gw + 10 * b

def d_comic_pop(img, layer, info, b):
    """11. ⚡ Comic Pop: Anime Manga Cover with Bold Yellow Halftone Contrast"""
    W, H = img.size
    m = int(75 * b)
    add_smooth_gradient_bottom(img, H * 0.58, 235)
    
    tfont, lines = fit_lines(info["title"], 110 * b, 52 * b, W * 0.70, 2)
    sfont, gfont = load_font(28 * b), load_font(24 * b)
    
    badge_h = int(38 * b)
    bar_h, bar_w = max(3, int(6 * b)), int(160 * b)
    th_total = block_h(tfont, len(lines))
    meta_h = int(36 * b)
    
    total_h = badge_h + 16 * b + th_total + 16 * b + bar_h + 16 * b + meta_h
    y = H - m - total_h
    
    # Bold Action Hit Badge (Yellow + Black)
    tag = f"💥 {info['type'].upper()}" if info.get("type") else "💥 TOP HIT"
    w1, _ = draw_pill_badge(layer, m, y, tag, sfont, (255, 220, 0, 240), border_color=(255, 255, 255, 255), text_color=(10, 10, 10, 255), pad_x=18 * b, pad_y=6 * b)
    if info.get("rating"):
        rw, _ = draw_pill_badge(layer, m + w1 + 12 * b, y, f"★ {info['rating']}", sfont, (20, 20, 20, 200), border_color=(255, 220, 0, 220), text_color=(255, 220, 0, 255), pad_x=14 * b, pad_y=6 * b)
        
    y += badge_h + 16 * b
    y += draw_lines(layer, lines, tfont, m, y) + 16 * b
    
    # Solid bright yellow bar
    ImageDraw.Draw(layer).rounded_rectangle((m, y, m + bar_w, y + bar_h), radius=bar_h // 2, fill=(255, 220, 0, 255))
    y += bar_h + 16 * b
    
    cur_x = m
    if info.get("year"):
        yw, _ = draw_pill_badge(layer, cur_x, y, info["year"], gfont, (255, 255, 255, 30), border_color=(255, 255, 255, 90), text_color=(255, 255, 255, 230), pad_x=14 * b, pad_y=6 * b)
        cur_x += yw + 10 * b
    for g in info.get("genres", [])[:3]:
        gw, _ = draw_pill_badge(layer, cur_x, y, g, gfont, (255, 220, 0, 25), border_color=(255, 220, 0, 120), text_color=(255, 240, 200, 225), pad_x=14 * b, pad_y=6 * b)
        cur_x += gw + 10 * b

def d_inferno_blaze(img, layer, info, b):
    """12. 🌋 Inferno Blaze: Molten Lava / Fiery Cinematic Blockbuster"""
    W, H = img.size
    m = int(72 * b)
    add_smooth_gradient_bottom(img, H * 0.60, 235)
    
    tfont, lines = fit_lines(info["title"], 112 * b, 50 * b, W * 0.70, 2)
    sfont, gfont = load_font(26 * b), load_font(24 * b)
    
    badge_h = int(36 * b)
    bar_h, bar_w = max(3, int(6 * b)), int(180 * b)
    th_total = block_h(tfont, len(lines))
    meta_h = int(36 * b)
    
    total_h = badge_h + 16 * b + th_total + 16 * b + bar_h + 16 * b + meta_h
    y = H - m - total_h
    
    # Molten Fire Badge
    tag = f"🔥 {info['type'].upper()}" if info.get("type") else "🔥 BLOCKBUSTER"
    w1, _ = draw_pill_badge(layer, m, y, tag, sfont, (255, 80, 0, 45), border_color=(255, 100, 0, 240), text_color=(255, 220, 180, 255), pad_x=16 * b, pad_y=6 * b)
    if info.get("year"):
        draw_pill_badge(layer, m + w1 + 12 * b, y, info["year"], sfont, (30, 20, 15, 180), border_color=(255, 140, 0, 100), text_color=(255, 220, 190, 230), pad_x=14 * b, pad_y=6 * b)
        
    y += badge_h + 16 * b
    y += draw_lines(layer, lines, tfont, m, y) + 16 * b
    
    # Molten Lava Gradient Bar (Flame Red-Orange -> Gold)
    for i in range(bar_w):
        t = i / bar_w
        r = 255
        g = int(60 * (1 - t) + 200 * t)
        bl_c = int(0 * (1 - t) + 10 * t)
        ImageDraw.Draw(layer).line([(m + i, y), (m + i, y + bar_h)], fill=(r, g, bl_c, 255))
    y += bar_h + 16 * b
    
    cur_x = m
    if info.get("rating"):
        rw, _ = draw_pill_badge(layer, cur_x, y, f"★ {info['rating']}", sfont, (255, 170, 0, 40), border_color=(255, 180, 0, 230), text_color=(255, 215, 0, 255), pad_x=16 * b, pad_y=6 * b)
        cur_x += rw + 14 * b
    for g in info.get("genres", [])[:3]:
        gw, _ = draw_pill_badge(layer, cur_x, y, g, gfont, (255, 80, 0, 25), border_color=(255, 90, 0, 110), text_color=(255, 220, 190, 220), pad_x=14 * b, pad_y=6 * b)
        cur_x += gw + 10 * b


# ---------------- extra helpers for designs 13-18 ----------------

def pill_row_center(layer, W, y, items, font, pad_x, pad_y, gap):
    """items = [(text, bg, border, text_color)]  -> centered row of pills"""
    if not items:
        return
    widths = [int(text_w(t, font) + pad_x * 2) for t, _, _, _ in items]
    x = (W - (sum(widths) + gap * (len(items) - 1))) / 2
    for (t, bg, bd, tc), w in zip(items, widths):
        draw_pill_badge(layer, x, y, t, font, bg, bd, tc, pad_x, pad_y)
        x += w + gap

def draw_petal(layer, cx, cy, r, angle, color):
    tile = Image.new("RGBA", (int(r * 4), int(r * 4)), (0, 0, 0, 0))
    ImageDraw.Draw(tile).ellipse((r, r * 1.4, r * 3, r * 2.6), fill=color)
    tile = tile.rotate(angle, expand=True, resample=Image.BICUBIC)
    paste_rgba(layer, tile, cx - tile.width / 2, cy - tile.height / 2)

def corner_bracket(d, x, y, size, width, dx, dy, color):
    d.line([(x, y), (x + dx * size, y)], fill=color, width=width)
    d.line([(x, y), (x, y + dy * size)], fill=color, width=width)


# ======================= 6 NEW DESIGNS =======================

def d_sakura_dream(img, layer, info, b):
    """13. 🌸 Sakura Dream: Romantic anime, falling cherry petals, centered pink title"""
    W, H = img.size
    m = int(60 * b)
    add_smooth_gradient_bottom(img, H * 0.58, 225)

    rnd = random.Random(sum(map(ord, info["title"])))
    for _ in range(28):
        draw_petal(layer, rnd.randint(0, W), rnd.randint(0, int(H * 0.92)),
                   rnd.randint(int(6 * b), int(15 * b)), rnd.randint(0, 359),
                   (255, rnd.randint(165, 205), rnd.randint(200, 225), rnd.randint(110, 190)))

    tfont, lines = fit_lines(info["title"], 104 * b, 50 * b, W * 0.74, 2)
    sfont, gfont = load_font(26 * b), load_font(24 * b)
    th = block_h(tfont, len(lines))
    pill_h = int(text_h(sfont) + 12 * b)
    total = pill_h + 16 * b + th + 30 * b + pill_h
    y = H - m - total

    tags = []
    if info.get("type"):
        tags.append((info["type"].upper(), (255, 150, 190, 60), (255, 170, 205, 230), (255, 225, 238, 255)))
    if info.get("year"):
        tags.append((info["year"], (255, 255, 255, 30), (255, 255, 255, 110), (255, 255, 255, 235)))
    if info.get("rating"):
        tags.append((f"★ {info['rating']}", (255, 204, 0, 40), (255, 204, 0, 220), (255, 215, 0, 255)))
    pill_row_center(layer, W, y, tags, sfont, 16 * b, 6 * b, 12 * b)
    y += pill_h + 16 * b

    y += draw_lines(layer, lines, tfont, 0, y, align="center", box_w=W) + 30 * b
    gen = [(g, (255, 150, 190, 28), (255, 170, 205, 120), (255, 235, 242, 230)) for g in info.get("genres", [])[:3]]
    pill_row_center(layer, W, y, gen, gfont, 14 * b, 6 * b, 10 * b)


def d_shonen_burst(img, layer, info, b):
    """14. 💥 Shonen Burst: Slanted yellow-black power banner + speed lines (Naruto/DBZ vibe)"""
    W, H = img.size
    m = int(70 * b)
    add_smooth_gradient_bottom(img, H * 0.50, 200)

    d = ImageDraw.Draw(layer)
    rnd = random.Random(sum(map(ord, info["title"])))
    for _ in range(22):  # speed lines
        x = rnd.randint(int(W * 0.35), W)
        d.line([(x, 0), (x - rnd.randint(int(120 * b), int(380 * b)), H)],
               fill=(255, 255, 255, rnd.randint(14, 36)), width=max(1, int(rnd.randint(1, 3) * b)))

    tfont, lines = fit_lines(info["title"], 112 * b, 52 * b, W * 0.62, 2)
    mfont = load_font(28 * b)
    th = block_h(tfont, len(lines))
    skew = int(70 * b)
    by1 = H - int(55 * b)
    by0 = by1 - int(th + 30 * b + text_h(mfont) + 40 * b)
    bw = int(W * 0.72)
    # dark slanted banner + yellow edge
    d.polygon([(0, by0), (bw, by0), (bw - skew, by1), (0, by1)], fill=(10, 10, 12, 215))
    d.polygon([(bw, by0), (bw + int(14 * b), by0), (bw + int(14 * b) - skew, by1), (bw - skew, by1)], fill=(255, 214, 0, 255))

    y = by0 + int(20 * b)
    y += draw_lines(layer, lines, tfont, m, y) + 10 * b
    parts = []
    if info.get("type"):
        parts.append(info["type"].upper())
    if info.get("year"):
        parts.append(info["year"])
    if info.get("rating"):
        parts.append(f"★ {info['rating']}")
    parts.extend(info.get("genres", [])[:2])
    draw_lines(layer, ["  //  ".join(parts)], mfont, m, y, fill=(255, 214, 0, 255))


def d_midnight_moon(img, layer, info, b):
    """15. 🌙 Midnight Moon: Dark fantasy, glowing moon halo, silver-violet centered title"""
    W, H = img.size
    m = int(65 * b)
    add_smooth_gradient_bottom(img, H * 0.62, 235)

    # moon glow
    R = int(H * 0.11)
    cx, cy = W // 2, int(H * 0.2)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((cx - R * 2, cy - R * 2, cx + R * 2, cy + R * 2), fill=(150, 120, 255, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(int(40 * b)))
    layer.alpha_composite(glow)
    d = ImageDraw.Draw(layer)
    d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(235, 232, 255, 235))
    d.ellipse((cx - R + int(R * 0.35), cy - R - int(R * 0.1), cx + R + int(R * 0.35), cy + R - int(R * 0.1)),
              fill=(40, 25, 90, 225))  # crescent cut

    tfont, lines = fit_lines(info["title"], 100 * b, 48 * b, W * 0.74, 2)
    sfont, gfont = load_font(26 * b), load_font(24 * b)
    th = block_h(tfont, len(lines))
    total = text_h(sfont) + 14 * b + th + 16 * b + text_h(gfont)
    y = H - m - total

    # flanked label:  ───  ANIME • 2024  ───
    label = " • ".join([p for p in [(info.get("type") or "ANIME").upper(), info.get("year")] if p])
    lw = text_w(label, sfont)
    ly = y + text_h(sfont) / 2
    lx0 = (W - lw) / 2
    d.line([(lx0 - 190 * b, ly), (lx0 - 20 * b, ly)], fill=(190, 170, 255, 200), width=max(2, int(2 * b)))
    d.line([(lx0 + lw + 20 * b, ly), (lx0 + lw + 190 * b, ly)], fill=(190, 170, 255, 200), width=max(2, int(2 * b)))
    draw_lines(layer, [label], sfont, 0, y, fill=(205, 190, 255, 255), align="center", box_w=W)
    y += text_h(sfont) + 14 * b

    y += draw_lines(layer, lines, tfont, 0, y, align="center", box_w=W) + 16 * b
    meta = []
    if info.get("rating"):
        meta.append(f"★ {info['rating']}")
    meta.extend(info.get("genres", [])[:3])
    draw_lines(layer, ["   ·   ".join(meta)], gfont, 0, y, fill=(225, 215, 255, 225), align="center", box_w=W)


def d_mecha_hud(img, layer, info, b):
    """16. 🤖 Mecha HUD: Sci-fi targeting HUD, corner brackets, orange-cyan data panel"""
    W, H = img.size
    m = int(55 * b)
    add_smooth_gradient_bottom(img, H * 0.45, 190)
    d = ImageDraw.Draw(layer)
    cyan, orange = (0, 235, 255, 230), (255, 140, 0, 255)

    bw = max(2, int(4 * b))
    sz = int(70 * b)
    inset = int(28 * b)
    corner_bracket(d, inset, inset, sz, bw, 1, 1, cyan)
    corner_bracket(d, W - inset, inset, sz, bw, -1, 1, cyan)
    corner_bracket(d, inset, H - inset, sz, bw, 1, -1, cyan)
    corner_bracket(d, W - inset, H - inset, sz, bw, -1, -1, cyan)

    # small target reticle top-right
    rr = int(34 * b)
    rx, ry = W - int(120 * b), int(120 * b)
    d.ellipse((rx - rr, ry - rr, rx + rr, ry + rr), outline=orange, width=max(2, int(3 * b)))
    d.line([(rx - rr * 1.6, ry), (rx + rr * 1.6, ry)], fill=orange, width=max(1, int(2 * b)))
    d.line([(rx, ry - rr * 1.6), (rx, ry + rr * 1.6)], fill=orange, width=max(1, int(2 * b)))

    tfont, lines = fit_lines(info["title"], 88 * b, 44 * b, W * 0.52, 2)
    sfont, mfont = load_font(22 * b), load_font(26 * b)
    pad = int(30 * b)
    cw = max([text_w(l, tfont) for l in lines] + [int(380 * b)])
    pw = int(cw + pad * 2 + 14 * b)
    ph = int(pad + text_h(sfont) + 12 * b + block_h(tfont, len(lines)) + 14 * b + text_h(mfont) + pad)
    x0, y0 = m, H - m - ph
    d.rectangle((x0, y0, x0 + pw, y0 + ph), fill=(5, 12, 22, 190))
    d.rectangle((x0, y0, x0 + int(10 * b), y0 + ph), fill=orange)
    d.rectangle((x0, y0, x0 + pw, y0 + max(2, int(3 * b))), fill=cyan)

    tx = x0 + int(10 * b) + pad
    y = y0 + pad
    draw_lines(layer, ["// TARGET LOCKED"], sfont, tx, y, fill=cyan)
    y += text_h(sfont) + 12 * b
    y += draw_lines(layer, lines, tfont, tx, y) + 14 * b
    parts = []
    if info.get("type"):
        parts.append(info["type"].upper())
    if info.get("year"):
        parts.append(info["year"])
    if info.get("rating"):
        parts.append(f"RATING {info['rating']}")
    draw_lines(layer, ["  |  ".join(parts)], mfont, tx, y, fill=(255, 190, 110, 240))


def d_manga_panel(img, layer, info, b):
    """17. 📖 Manga Panel: White comic frame + solid white title box with hard black shadow"""
    W, H = img.size
    d = ImageDraw.Draw(layer)
    fi = int(22 * b)
    d.rectangle((fi, fi, W - fi, H - fi), outline=(255, 255, 255, 255), width=max(4, int(10 * b)))

    tfont, lines = fit_lines(info["title"], 100 * b, 48 * b, W * 0.58, 2)
    sfont, mfont = load_font(26 * b), load_font(26 * b)
    padx, pady = int(34 * b), int(24 * b)
    cw = max([text_w(l, tfont) for l in lines] + [int(300 * b)])
    bw = int(cw + padx * 2)
    bh = int(pady * 2 + block_h(tfont, len(lines)) + 12 * b + text_h(mfont))
    x0 = int(70 * b)
    y0 = H - int(80 * b) - bh
    off = int(12 * b)

    d.rectangle((x0 + off, y0 + off, x0 + bw + off, y0 + bh + off), fill=(0, 0, 0, 255))   # hard shadow
    d.rectangle((x0, y0, x0 + bw, y0 + bh), fill=(255, 255, 255, 255))
    d.rectangle((x0, y0, x0 + bw, y0 + bh), outline=(0, 0, 0, 255), width=max(3, int(5 * b)))

    # red tag
    tag = (info.get("type") or "NEW SERIES").upper()
    tgw = int(text_w(tag, sfont) + 30 * b)
    tgh = int(text_h(sfont) + 14 * b)
    d.rectangle((x0, y0 - tgh, x0 + tgw, y0), fill=(220, 20, 30, 255))
    d.text((x0 + 15 * b, y0 - tgh + 7 * b), tag, font=sfont, fill=(255, 255, 255, 255))

    y = y0 + pady
    step = text_h(tfont) * 1.12
    for i, ln in enumerate(lines):
        d.text((x0 + padx, y + i * step), ln, font=tfont, fill=(12, 12, 14, 255))
    y += block_h(tfont, len(lines)) + 12 * b
    parts = [p for p in [info.get("year"), f"★ {info['rating']}" if info.get("rating") else None] + info.get("genres", [])[:2] if p]
    d.text((x0 + padx, y), "  /  ".join(parts), font=mfont, fill=(70, 70, 78, 255))


def d_spirit_breeze(img, layer, info, b):
    """18. 🍃 Spirit Breeze: Soft Ghibli-style mint glass card, bottom-right, dreamy glow"""
    W, H = img.size
    pad, m = int(42 * b), int(60 * b)

    # soft mint haze from bottom
    haze = Image.new("RGBA", (W, int(H * 0.5)), (120, 235, 200, 0))
    haze.putalpha(Image.linear_gradient("L").resize((W, int(H * 0.5))).point(lambda p: int((p / 255.0) ** 1.6 * 90)))
    img.alpha_composite(haze, dest=(0, H - haze.height))
    add_smooth_gradient_bottom(img, H * 0.40, 120)

    tfont, lines = fit_lines(info["title"], 80 * b, 42 * b, W * 0.46, 2)
    sfont, gfont = load_font(26 * b), load_font(23 * b)
    cw = max([text_w(l, tfont) for l in lines] + [int(330 * b)])
    pw = int(cw + pad * 2)
    ph = int(pad + 34 * b + 14 * b + block_h(tfont, len(lines)) + 16 * b + 34 * b + pad)
    x0, y0 = W - m - pw, H - m - ph
    glass_panel(img, layer, (x0, y0, x0 + pw, y0 + ph), 40 * b, 24 * b, white=75, border_color=(200, 255, 235, 200))

    y = y0 + pad
    cur = x0 + pad
    tag = (info.get("type") or "ANIME").upper()
    tw, _ = draw_pill_badge(layer, cur, y, tag, sfont, (110, 230, 190, 70), (170, 255, 225, 230), (235, 255, 248, 255), 14 * b, 4 * b)
    cur += tw + 10 * b
    if info.get("year"):
        draw_pill_badge(layer, cur, y, info["year"], sfont, (255, 255, 255, 30), (255, 255, 255, 110), (255, 255, 255, 235), 12 * b, 4 * b)
    if info.get("rating"):
        draw_pill_badge(layer, x0 + pw - pad - int(115 * b), y, f"★ {info['rating']}", sfont, (255, 204, 0, 40), (255, 204, 0, 210), (255, 215, 0, 255), 14 * b, 4 * b)
    y += 34 * b + 14 * b
    y += draw_lines(layer, lines, tfont, x0 + pad, y) + 16 * b
    cur = x0 + pad
    for g in info.get("genres", [])[:3]:
        gw, _ = draw_pill_badge(layer, cur, y, g, gfont, (110, 230, 190, 30), (170, 255, 225, 120), (232, 255, 246, 225), 13 * b, 4 * b)
        cur += gw + 10 * b


# ======================= UPDATED DESIGNS REGISTRY =======================

DESIGNS = {
    1: ("🌟 Cyber Glow", d_cyber_neon),
    2: ("🎬 Cinematic Prime", d_cinematic_prime),
    3: ("💎 Vision Glass", d_vision_glass),
    4: ("🎌 Tokyo Action", d_tokyo_action),
    5: ("🌌 Aurora Horizon", d_aurora_horizon),
    6: ("🏆 Royale Gold", d_royale_gold),
    7: ("🔥 Cyber Logo", d_cyber_logo),
    8: ("🩸 Crimson Phantom", d_crimson_phantom),
    9: ("🌸 Synthwave Neon", d_synthwave_neon),
    10: ("❄️ Glacial Frost", d_glacial_frost),
    11: ("⚡ Comic Pop", d_comic_pop),
    12: ("🌋 Inferno Blaze", d_inferno_blaze),
    13: ("🌸 Sakura Dream", d_sakura_dream),
    14: ("💥 Shonen Burst", d_shonen_burst),
    15: ("🌙 Midnight Moon", d_midnight_moon),
    16: ("🤖 Mecha HUD", d_mecha_hud),
    17: ("📖 Manga Panel", d_manga_panel),
    18: ("🍃 Spirit Breeze", d_spirit_breeze),
}

def design_name(st):
    return DESIGNS[st][0] if st in DESIGNS else "Plain (Watermark only)"
