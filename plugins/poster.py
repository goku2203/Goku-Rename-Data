import asyncio
import aiohttp
import io
import math
import os
import time
from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, InputMediaPhoto
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from helper.database import digital_botz

# Inga unga TMDB API Key a podunga
TMDB_API_KEY = "f0ed821364e340369110e83b814899ed"

DEFAULT_WM = "@Techgokul"      # user set pannala na idhu varum
SCALE_MIN = 0.4
SCALE_MAX = 3.0
SCALE_STEP = 0.2
AUTO_DELETE_SECONDS = 120      # poster auto delete time
GLASS_WHITE = 60               # frosted glass white level (0-255). 40 = clear, 90 = romba white
ACCENT = (36, 161, 222, 255)   # Telegram blue

WAITING = {}          # user_id -> watermark name ku wait panra state
IMG_CACHE = {}        # image bytes cache (fast aaga)
BACKDROP_CACHE = {}   # tmdb backdrops list cache
INFO_CACHE = {}       # title / year / rating cache

# Bold font venumna bot folder la "font.ttf" nu oru font file podunga (Poppins-Bold etc.)
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


async def get_json(url, params=None):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            return await resp.json()


async def get_bytes(url):
    if url in IMG_CACHE:
        return IMG_CACHE[url]
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()
    if len(IMG_CACHE) >= 10:
        IMG_CACHE.pop(next(iter(IMG_CACHE)))
    IMG_CACHE[url] = data
    return data


async def get_backdrops(media_type, tmdb_id):
    key = f"{media_type}_{tmdb_id}"
    if key not in BACKDROP_CACHE:
        data = await get_json(
            f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/images",
            params={"api_key": TMDB_API_KEY},
        )
        paths = [b["file_path"] for b in data.get("backdrops", [])]
        if len(BACKDROP_CACHE) >= 30:
            BACKDROP_CACHE.pop(next(iter(BACKDROP_CACHE)))
        BACKDROP_CACHE[key] = paths
    return BACKDROP_CACHE[key]


async def get_info(media_type, tmdb_id):
    """Title, year, rating, genres - designs ku venum"""
    key = f"{media_type}_{tmdb_id}"
    if key in INFO_CACHE:
        return INFO_CACHE[key]
    try:
        data = await get_json(
            f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}",
            params={"api_key": TMDB_API_KEY, "language": "en-US"},
        )
        is_tv = media_type == "tv"
        title = (data.get("name") if is_tv else data.get("title")) or ""
        date = (data.get("first_air_date") if is_tv else data.get("release_date")) or ""
        rating = data.get("vote_average") or 0
        info = {
            "title": title,
            "year": date[:4],
            "rating": f"{rating:.1f}" if rating else "",
            "genres": [g["name"] for g in data.get("genres", [])][:3],
            "type": "TV Series" if is_tv else "Movie",
        }
    except Exception:
        info = {"title": "", "year": "", "rating": "", "genres": [], "type": ""}
    if len(INFO_CACHE) >= 50:
        INFO_CACHE.pop(next(iter(INFO_CACHE)))
    INFO_CACHE[key] = info
    return info


async def get_scale(user_id):
    try:
        s = await digital_botz.get_wm_scale(user_id)
        s = float(s) if s else 1.0
    except Exception:
        s = 1.0
    return min(SCALE_MAX, max(SCALE_MIN, s))


async def get_wm_text(user_id):
    try:
        t = await digital_botz.get_watermark(user_id)
    except Exception:
        t = None
    return t or DEFAULT_WM


# ======================= DRAWING HELPERS =======================

def paste_rgba(dst, src, x, y):
    """alpha_composite - negative position irundhalum crash aagaadhu"""
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
    """Soft shadow oda text - bright background la kooda clear aa theriyum"""
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
    """Lines a draw panni, mothama evlo height eduthuchu nu return pannum"""
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
    """Title romba neelama irundha font size kuraichi / 2 line ah wrap pannum"""
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

    # shine border
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
# Each design: (img, layer, info, b)   b = image width / 1920

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
    grad = Image.linear_gradient("L").transpose(Image.ROTATE_270).resize((gw, H))  # left dark -> right clear
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


# style number -> (button name, function, full glass?)
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


# ======================= WATERMARK =======================

def draw_watermark(img, layer, text, scale):
    """Top right frosted glass pill + Telegram logo + white text"""
    b = img.width / 1920            # image size ku yetha maathiri auto adjust
    unit = b * scale                # user set pannina size
    margin = int(40 * b)

    font = load_font(34 * unit)
    bbox = _PROBE.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    h = max(24, int(64 * unit))
    icon_d = int(h * 0.62)
    pad_l = (h - icon_d) // 2
    gap = int(14 * unit)
    pad_r = int(h * 0.45)
    w = int(pad_l + icon_d + gap + tw + pad_r)

    x0 = max(0, img.width - w - margin)
    y0 = margin

    glass_panel(img, layer, (x0, y0, x0 + w, y0 + h), h // 2, 18 * unit)
    paste_rgba(layer, telegram_icon(icon_d), x0 + pad_l, y0 + (h - icon_d) // 2)

    tx = x0 + pad_l + icon_d + gap - bbox[0]
    ty = y0 + (h - th) // 2 - bbox[1]
    text_shadow(layer, (tx, ty), text, font)


def build_poster(img_bytes, text, scale, out_path, style=0, info=None):
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    b = img.width / 1920
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))

    if style in DESIGNS and info and info.get("title"):
        DESIGNS[style][1](img, layer, info, b)

    draw_watermark(img, layer, text, scale)

    final = Image.alpha_composite(img, layer).convert("RGB")
    final.save(out_path, format="JPEG", quality=90)


async def render(user_id, tmdb_id, media_type, idx, st=0):
    backdrops = await get_backdrops(media_type, tmdb_id)
    if not backdrops:
        return None
    idx = idx % len(backdrops)  # Next/Back loop aagum
    img_bytes = await get_bytes(f"https://image.tmdb.org/t/p/original{backdrops[idx]}")
    text = await get_wm_text(user_id)
    scale = await get_scale(user_id)
    info = await get_info(media_type, tmdb_id) if st in DESIGNS else None
    out_path = f"poster_{user_id}_{int(time.time() * 1000)}.jpg"
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, build_poster, img_bytes, text, scale, out_path, st, info)
    return out_path, idx, len(backdrops), text, scale


# ======================= BUTTONS / CAPTIONS =======================

def main_markup(tmdb_id, mt, idx, total, st):
    rows = []
    if total > 1:
        rows.append([
            InlineKeyboardButton("⬅️ Back", callback_data=f"show_img|{tmdb_id}|{mt}|{idx - 1}|{st}"),
            InlineKeyboardButton(f"{idx + 1}/{total}", callback_data="ignore"),
            InlineKeyboardButton("Next ➡️", callback_data=f"show_img|{tmdb_id}|{mt}|{idx + 1}|{st}"),
        ])
    rows.append([InlineKeyboardButton("🎨 Custom Style", callback_data=f"cstyle|{tmdb_id}|{mt}|{idx}|{st}")])
    rows.append([InlineKeyboardButton("🗑 Delete Now", callback_data="delete_auto")])
    return InlineKeyboardMarkup(rows)


def style_markup(tmdb_id, mt, idx, st):
    def dbtn(n):
        name = DESIGNS[n][0]
        return InlineKeyboardButton(f"✅ {name}" if st == n else name,
                                    callback_data=f"dsgn|{tmdb_id}|{mt}|{idx}|{n}")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Set My Watermark", callback_data=f"wmset|{tmdb_id}|{mt}|{idx}|{st}")],
        [
            InlineKeyboardButton("➖ Size", callback_data=f"wmsize|{tmdb_id}|{mt}|{idx}|{st}|m"),
            InlineKeyboardButton("➕ Size", callback_data=f"wmsize|{tmdb_id}|{mt}|{idx}|{st}|p"),
        ],
        [dbtn(1), dbtn(2)],
        [dbtn(3), dbtn(4)],
        [dbtn(5), dbtn(6)],
        [
            InlineKeyboardButton("🚫 Plain" if st else "✅ Plain", callback_data=f"dsgn|{tmdb_id}|{mt}|{idx}|0"),
            InlineKeyboardButton("⬅️ Back to Poster", callback_data=f"show_img|{tmdb_id}|{mt}|{idx}|{st}"),
        ],
        [InlineKeyboardButton("🗑 Delete Now", callback_data="delete_auto")],
    ])


def main_caption(idx, st):
    tag = f" • {design_name(st)}" if st else ""
    return (f"Landscape Image {idx + 1} 🌅{tag}\n\n"
            f"*(This message will auto-delete in {AUTO_DELETE_SECONDS // 60} minutes)*")


def style_caption(text, scale, st):
    return (f"**🎨 CUSTOM STYLE**\n"
            f"__Design pick pannunga. Watermark & size permanent a save aagum__\n\n"
            f"🖼 **Design:** `{design_name(st)}`\n"
            f"🏷 **Watermark:** `{text}`\n"
            f"📏 **Size:** `{scale}x`")


async def auto_delete(msg):
    await asyncio.sleep(AUTO_DELETE_SECONDS)
    try:
        await msg.delete()
    except Exception:
        pass


async def deliver(client, query, path, caption, markup):
    """Photo irundha fast a edit, illa na text msg delete panni photo anuppum"""
    try:
        if query.message.photo:
            try:
                await query.message.edit_media(
                    media=InputMediaPhoto(path, caption=caption),
                    reply_markup=markup
                )
            except MessageNotModified:
                pass
        else:
            await query.message.delete()
            sent = await client.send_photo(
                chat_id=query.message.chat.id,
                photo=path,
                caption=caption,
                reply_markup=markup
            )
            asyncio.create_task(auto_delete(sent))  # first time mattum start aagum
    finally:
        if os.path.exists(path):
            os.remove(path)


def parse_st(parts, pos):
    try:
        st = int(parts[pos])
    except Exception:
        st = 0
    return st if st in DESIGNS else 0


# ======================= COMMANDS =======================

@Client.on_message(filters.private & filters.command(['set_watermark']))
async def set_watermark_cmd(client, message):
    if len(message.command) == 1:
        return await message.reply_text("**__Custom Name kudu bro__\n\nEx :- `/set_watermark @Techgokul`**")

    watermark_name = message.text.split(" ", 1)[1]
    await digital_botz.set_watermark(message.from_user.id, watermark_name)
    await message.reply_text(f"**Watermark Name saved successfully:** `{watermark_name}`")


# --- Step 1: Search Anime and Show List ---
@Client.on_message(filters.private & filters.command(['poster', 'p']))
async def poster_cmd(client, message):
    if len(message.command) == 1:
        return await message.reply_text("**__Anime Name kudu bro__\n\nEx :- `/p Naruto`**")

    query = message.text.split(" ", 1)[1]
    process_msg = await message.reply_text("`Searching...`")

    try:
        data = await get_json(
            "https://api.themoviedb.org/3/search/multi",
            params={"api_key": TMDB_API_KEY, "query": query},
        )
        results = data.get("results", [])

        buttons = []
        for res in results:
            media_type = res.get("media_type")
            if media_type not in ["tv", "movie"]:
                continue
            title = res.get("name") if media_type == "tv" else res.get("title")
            date = (res.get("first_air_date") if media_type == "tv" else res.get("release_date")) or ""
            btn_text = f"{title} ({date[:4]})" if date else f"{title}"
            buttons.append([InlineKeyboardButton(
                btn_text, callback_data=f"show_img|{res.get('id')}|{media_type}|0|0"
            )])
            if len(buttons) == 5:   # Top 5 mattum
                break

        if not buttons:
            return await process_msg.edit("**Anime kidaikkala bro! Spelling check pannunga.**")

        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="close_search")])
        await process_msg.edit(
            f"**Search Results for:** `{query}`\n\nKela irukkura list la onna select pannunga:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await process_msg.edit(f"**Error:** `{e}`")


@Client.on_callback_query(filters.regex(r"^close_search$"), group=1)
async def close_search_cb(client, query: CallbackQuery):
    await query.answer()
    try:
        await query.message.delete()
        if query.message.reply_to_message:
            await query.message.reply_to_message.delete()
    except Exception:
        pass


# ======================= POSTER VIEW (Next / Back) =======================

@Client.on_callback_query(filters.regex(r"^show_img\|"), group=1)
async def show_image_cb(client, query: CallbackQuery):
    try:
        await query.answer()
    except Exception:
        pass

    parts = query.data.split("|")
    tmdb_id, media_type, idx, st = parts[1], parts[2], int(parts[3]), parse_st(parts, 4)
    user_id = query.from_user.id

    if not query.message.photo:
        await query.message.edit_text("`Processing Glass Watermark...`")

    try:
        res = await render(user_id, tmdb_id, media_type, idx, st)
        if not res:
            return await query.message.edit("**Intha anime kku landscape image kidaikkala bro!**")
        path, idx, total, _, _ = res
        await deliver(client, query, path, main_caption(idx, st), main_markup(tmdb_id, media_type, idx, total, st))
    except Exception as e:
        try:
            await query.message.edit(f"**Error:** `{e}`")
        except Exception:
            pass


# ======================= CUSTOM STYLE PANEL =======================

async def show_panel(client, query, user_id, tmdb_id, media_type, idx, st):
    res = await render(user_id, tmdb_id, media_type, idx, st)
    if not res:
        return
    path, idx, total, text, scale = res
    await deliver(client, query, path, style_caption(text, scale, st), style_markup(tmdb_id, media_type, idx, st))


@Client.on_callback_query(filters.regex(r"^cstyle\|"), group=1)
async def custom_style_cb(client, query: CallbackQuery):
    try:
        await query.answer()
    except Exception:
        pass

    parts = query.data.split("|")
    tmdb_id, media_type, idx, st = parts[1], parts[2], int(parts[3]), parse_st(parts, 4)
    try:
        await show_panel(client, query, query.from_user.id, tmdb_id, media_type, idx, st)
    except Exception as e:
        try:
            await query.message.edit_caption(f"**Error:** `{e}`")
        except Exception:
            pass


# --- 6 Design buttons ---
@Client.on_callback_query(filters.regex(r"^dsgn\|"), group=1)
async def design_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx, st = parts[1], parts[2], int(parts[3]), parse_st(parts, 4)
    try:
        await query.answer(f"{design_name(st)} ✅")
    except Exception:
        pass
    try:
        await show_panel(client, query, query.from_user.id, tmdb_id, media_type, idx, st)
    except Exception as e:
        try:
            await query.message.edit_caption(f"**Error:** `{e}`")
        except Exception:
            pass


# --- Size + / - (ore thadava set pannina permanent) ---
@Client.on_callback_query(filters.regex(r"^wmsize\|"), group=1)
async def wm_size_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx, st, op = parts[1], parts[2], int(parts[3]), parse_st(parts, 4), parts[5]
    user_id = query.from_user.id

    scale = await get_scale(user_id)
    new_scale = round(scale + SCALE_STEP, 1) if op == "p" else round(scale - SCALE_STEP, 1)
    new_scale = min(SCALE_MAX, max(SCALE_MIN, new_scale))

    if new_scale == scale:
        return await query.answer("Idhukku mela/keela pogaadhu bro!", show_alert=True)

    await query.answer(f"Size: {new_scale}x ✅")
    await digital_botz.set_wm_scale(user_id, new_scale)   # DB la permanent save

    try:
        await show_panel(client, query, user_id, tmdb_id, media_type, idx, st)
    except Exception as e:
        try:
            await query.message.edit_caption(f"**Error:** `{e}`")
        except Exception:
            pass


# --- Set My Watermark button ---
@Client.on_callback_query(filters.regex(r"^wmset\|"), group=1)
async def wm_set_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx, st = parts[1], parts[2], int(parts[3]), parse_st(parts, 4)
    user_id = query.from_user.id
    await query.answer()

    prompt = await client.send_message(
        query.message.chat.id,
        "**✏️ Unga Watermark Name anuppunga**\n\nEx :- `@Techgokul`\n\n__(60 seconds kulla anuppunga)__",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="wmcancel")]])
    )
    WAITING[user_id] = {
        "chat_id": query.message.chat.id,
        "photo_id": query.message.id,
        "prompt_id": prompt.id,
        "tmdb_id": tmdb_id,
        "media_type": media_type,
        "idx": idx,
        "st": st,
    }

    async def timeout():
        await asyncio.sleep(60)
        state = WAITING.get(user_id)
        if state and state["prompt_id"] == prompt.id:
            WAITING.pop(user_id, None)
            try:
                await prompt.delete()
            except Exception:
                pass
    asyncio.create_task(timeout())


@Client.on_callback_query(filters.regex(r"^wmcancel$"), group=1)
async def wm_cancel_cb(client, query: CallbackQuery):
    WAITING.pop(query.from_user.id, None)
    await query.answer("Cancelled")
    try:
        await query.message.delete()
    except Exception:
        pass


async def _waiting_filter(_, __, message):
    return bool(
        message.from_user
        and message.from_user.id in WAITING
        and message.text
        and not message.text.startswith("/")
    )

waiting_input = filters.create(_waiting_filter)


@Client.on_message(filters.private & waiting_input, group=-1)
async def receive_watermark(client, message):
    user_id = message.from_user.id
    st = WAITING.pop(user_id, None)
    if st:
        name = message.text.strip()[:30]
        await digital_botz.set_watermark(user_id, name)

        for chat_id, msg_id in ((message.chat.id, message.id), (st["chat_id"], st["prompt_id"])):
            try:
                await client.delete_messages(chat_id, msg_id)
            except Exception:
                pass

        # Poster a new watermark oda refresh pannum
        try:
            res = await render(user_id, st["tmdb_id"], st["media_type"], st["idx"], st["st"])
            if res:
                path, idx, total, text, scale = res
                try:
                    await client.edit_message_media(
                        chat_id=st["chat_id"],
                        message_id=st["photo_id"],
                        media=InputMediaPhoto(path, caption=style_caption(text, scale, st["st"])),
                        reply_markup=style_markup(st["tmdb_id"], st["media_type"], idx, st["st"])
                    )
                except Exception:
                    await client.send_message(st["chat_id"], f"**Watermark saved:** `{name}` ✅")
                finally:
                    if os.path.exists(path):
                        os.remove(path)
        except Exception:
            await client.send_message(st["chat_id"], f"**Watermark saved:** `{name}` ✅")
    message.stop_propagation()   # vera handler ku (auto rename etc) pogaama thadukkum


# ======================= MISC =======================

@Client.on_callback_query(filters.regex(r"^delete_auto$"), group=1)
async def manual_delete_cb(client, query: CallbackQuery):
    await query.answer("Deleted!")
    try:
        await query.message.delete()
        if query.message.reply_to_message:
            await query.message.reply_to_message.delete()
    except Exception:
        pass


@Client.on_callback_query(filters.regex(r"^ignore$"), group=1)
async def ignore_cb(client, query: CallbackQuery):
    await query.answer()
