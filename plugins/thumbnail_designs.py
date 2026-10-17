import io
import math
import os
import random
import threading
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

# Default Colors & Settings
GLASS_WHITE = 60               # Frosted glass white level (0-255). 40 = clear, 90 = very white
ACCENT = (36, 161, 222, 255)   # Telegram blue color

# ======================= FONTS =======================
# Ella font-um repo-la "fonts/" folder-la irukku (Render-la system font illa, adhanala bundle panni irukkom).
# Idhula irundhu thaan designs load pannum. Font file illana DejaVu-ku fallback aagum.

_HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIRS = [
    os.path.join(_HERE, "fonts"),
    os.path.join(os.path.dirname(_HERE), "fonts"),
    os.path.join(os.getcwd(), "fonts"),
    _HERE,
    os.getcwd(),
]

# key -> (file name, variable-font weight or None)
FONT_FILES = {
    "poppins-lt": ("Poppins-Light.ttf", None),
    "poppins-md": ("Poppins-Medium.ttf", None),
    "poppins-sb": ("Poppins-SemiBold.ttf", None),
    "poppins-b": ("Poppins-Bold.ttf", None),
    "poppins-xb": ("Poppins-ExtraBold.ttf", None),
    "poppins-blk": ("Poppins-Black.ttf", None),
    "bebas": ("BebasNeue-Regular.ttf", None),
    "anton": ("Anton-Regular.ttf", None),
    "rajdhani-sb": ("Rajdhani-SemiBold.ttf", None),
    "rajdhani-b": ("Rajdhani-Bold.ttf", None),
    "bangers": ("Bangers-Regular.ttf", None),
    "righteous": ("Righteous-Regular.ttf", None),
    "russo": ("RussoOne-Regular.ttf", None),
    "audiowide": ("Audiowide-Regular.ttf", None),
    "orbitron": ("Orbitron-Variable.ttf", 800),
    "cinzel": ("Cinzel-Variable.ttf", 700),
    "luckiest": ("LuckiestGuy-Regular.ttf", None),
    "lilita": ("LilitaOne-Regular.ttf", None),
    "chakra-b": ("ChakraPetch-Bold.ttf", None),
    "chakra-sb": ("ChakraPetch-SemiBold.ttf", None),
    "chakra-md": ("ChakraPetch-Medium.ttf", None),
    "titan": ("TitanOne-Regular.ttf", None),
    "zenmaru-b": ("ZenMaruGothic-Bold.ttf", None),
    "zenmaru-md": ("ZenMaruGothic-Medium.ttf", None),
    "bungee": ("Bungee-Regular.ttf", None),
    "dela": ("DelaGothicOne-Regular.ttf", None),
    "montserrat-md": ("Montserrat-Variable.ttf", 500),
    "montserrat-sb": ("Montserrat-Variable.ttf", 600),
    "montserrat-b": ("Montserrat-Variable.ttf", 700),
}

# ---------------------------------------------------------------------------
# FONT MAATHA - ippadi pannunga:
# Oru design-oda font-a maathanum-na keezha DESIGN_FONTS-la oru line add pannunga:
#     "d_sticker_pop": ("bangers", "poppins-xb"),      # (TITLE font, SMALL-text font)
# Function name = design function (e.g. d_neon_tokyo, d_clean_minimal, d_comic_pop ...)
# Use panna koodiya font keys (fonts/ folder-la irukku):
#   poppins-lt poppins-md poppins-sb poppins-b poppins-xb poppins-blk
#   bebas anton rajdhani-sb rajdhani-b bangers righteous russo audiowide
#   orbitron cinzel luckiest lilita chakra-b chakra-sb chakra-md titan
#   zenmaru-b zenmaru-md bungee dela montserrat-md montserrat-sb montserrat-b
# ---------------------------------------------------------------------------
DESIGN_FONTS = {
}

FALLBACK_PATHS = [
    "font.ttf",
    "Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "arialbd.ttf",
]

_PROBE = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
_tls = threading.local()   # thread-safe font cache + current design fonts (executor threads)


def _cur():
    c = getattr(_tls, "cur", None)
    if c is None:
        c = _tls.cur = {"title": "poppins-xb", "ui": "poppins-b"}
    return c


def _open_font(key, size):
    spec = FONT_FILES.get(key)
    if spec:
        fname, wght = spec
        for d in FONT_DIRS:
            p = os.path.join(d, fname)
            if os.path.isfile(p):
                try:
                    f = ImageFont.truetype(p, size)
                    if wght:
                        try:
                            f.set_variation_by_axes([wght])
                        except Exception:
                            pass
                    return f
                except Exception:
                    continue
    for p in FALLBACK_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def load_font(size, role="ui", family=None):
    """role = 'title' / 'ui' (current design's fonts) or family = exact key from FONT_FILES"""
    size = max(8, int(size))
    key = family or _cur().get(role, "poppins-b")
    cache = getattr(_tls, "fonts", None)
    if cache is None:
        cache = _tls.fonts = {}
    f = cache.get((key, size))
    if f is None:
        f = cache[(key, size)] = _open_font(key, size)
    return f


def fonts(title, ui, upper=False):
    """Decorator: design-ku thaniya title/ui font set pannum. upper=True -> title CAPS."""
    def deco(fn):
        def wrap(img, layer, info, b):
            c = _cur()
            old = dict(c)
            c["title"], c["ui"] = DESIGN_FONTS.get(fn.__name__, (title, ui))
            try:
                if upper and info.get("title"):
                    info = dict(info, title=info["title"].upper())
                return fn(img, layer, info, b)
            finally:
                c.clear()
                c.update(old)
        wrap.__name__ = fn.__name__
        wrap.__doc__ = fn.__doc__
        return wrap
    return deco


# ======================= TEXT METRICS (cap-height based = exact centering) =======================

def cap_h(font):
    """Height of capital letters - ellaa alignment-um idha vachu thaan"""
    bb = _PROBE.textbbox((0, 0), "H", font=font, anchor="ls")
    return max(1, -bb[1])


def text_h(font):
    """Cap height + descender allowance"""
    return int(cap_h(font) + getattr(font, "size", 30) * 0.24)


def line_step(font):
    return int(cap_h(font) * 1.62)


def block_h(font, n):
    return int(line_step(font) * (n - 1) + text_h(font))


# ======================= ICONS (emoji font illama vector-la varaiyurom) =======================

ICON_CHARS = {
    "★": "star", "⭐": "star", "⚡": "bolt", "🔥": "flame", "🌋": "flame",
    "👑": "crown", "💥": "burst", "🩸": "drop", "🌸": "flower", "✦": "sparkle", "✨": "sparkle",
}
ICON_COLORS = {
    "star": (255, 204, 0, 255), "flame": (255, 140, 20, 255), "crown": (255, 205, 60, 255),
    "drop": (225, 25, 60, 255), "burst": (255, 226, 0, 255), "flower": (255, 170, 205, 255),
}


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


def draw_icon(layer, name, cx, cy, size, color):
    S = 4
    N = int(size) + 4
    n = N * S
    k = size * S / 100.0
    o = (n - size * S) / 2.0
    tile = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)

    def P(pts):
        return [(o + x * k, o + y * k) for x, y in pts]

    if name == "star":
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            r = 50 if i % 2 == 0 else 21
            pts.append((50 + r * math.cos(a), 54 + r * math.sin(a)))
        d.polygon(P(pts), fill=color)
    elif name == "bolt":
        d.polygon(P([(64, 0), (14, 56), (44, 56), (30, 100), (88, 38), (56, 38), (74, 0)]), fill=color)
    elif name in ("flame", "drop"):
        d.ellipse([o + 17 * k, o + 36 * k, o + 83 * k, o + 100 * k], fill=color)
        d.polygon(P([(50, 0), (80, 56), (20, 56)]), fill=color)
        if name == "flame":
            d.ellipse([o + 36 * k, o + 60 * k, o + 64 * k, o + 98 * k], fill=(255, 235, 150, 255))
    elif name == "sparkle":
        d.polygon(P([(50, 0), (61, 39), (100, 50), (61, 61), (50, 100), (39, 61), (0, 50), (39, 39)]), fill=color)
    elif name == "crown":
        d.polygon(P([(4, 88), (4, 28), (28, 52), (50, 10), (72, 52), (96, 28), (96, 88)]), fill=color)
    elif name == "burst":
        pts = []
        for i in range(24):
            a = -math.pi / 2 + i * math.pi / 12
            r = 50 if i % 2 == 0 else 32
            pts.append((50 + r * math.cos(a), 50 + r * math.sin(a)))
        d.polygon(P(pts), fill=color)
    elif name == "flower":
        for i in range(5):
            a = -math.pi / 2 + i * 2 * math.pi / 5
            px, py = 50 + 27 * math.cos(a), 50 + 27 * math.sin(a)
            d.ellipse([o + (px - 23) * k, o + (py - 23) * k, o + (px + 23) * k, o + (py + 23) * k], fill=color)
        d.ellipse([o + 36 * k, o + 36 * k, o + 64 * k, o + 64 * k], fill=(255, 245, 190, 255))
    tile = tile.resize((N, N), Image.LANCZOS)
    paste_rgba(layer, tile, cx - N / 2, cy - N / 2)


# ======================= RICH TEXT (text + vector icons, no tofu boxes) =======================

def _tok(text):
    out, run = [], ""
    for ch in text:
        if ch in ("\ufe0f", "\u200d"):
            continue
        if ch in ICON_CHARS:
            if run:
                out.append(["t", run])
                run = ""
            out.append(["i", ICON_CHARS[ch]])
            continue
        if ch == "・":
            ch = "•"
        o = ord(ch)
        if o >= 0x1F000 or 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF:
            continue          # unsupported emoji -> drop (tofu box varaadhu)
        run += ch
    if run:
        out.append(["t", run])
    for k, t in enumerate(out):
        if t[0] == "t":
            if k > 0 and out[k - 1][0] == "i":
                t[1] = t[1].lstrip()
            if k + 1 < len(out) and out[k + 1][0] == "i":
                t[1] = t[1].rstrip()
    return [(a, b) for a, b in out if not (a == "t" and b == "")]


def _layout(text, font):
    cap = cap_h(font)
    isz = int(cap * 1.08)
    gap = max(3, int(cap * 0.34))
    toks = _tok(text)
    items, x = [], 0.0
    for k, (kind, val) in enumerate(toks):
        if k > 0 and (kind == "i" or toks[k - 1][0] == "i"):
            x += gap
        if kind == "i":
            items.append((x, "i", val, isz))
            x += isz
        else:
            w = _PROBE.textlength(val, font=font)
            items.append((x, "t", val, w))
            x += w
    return items, x, cap, isz


def text_w(text, font):
    return _layout(text, font)[1]


def text_shadow(layer, xy, text, font, fill=(255, 255, 255, 255), shadow_color=(0, 0, 0, 140), anchor="la"):
    """Text with soft ambient shadow for maximum readability on bright backgrounds"""
    x, y = int(xy[0]), int(xy[1])
    size = getattr(font, "size", 30)
    blur = max(2, int(size * 0.08))
    off = max(1, int(size * 0.06))
    bb = _PROBE.textbbox((x, y), text, font=font, anchor=anchor)
    pad = blur * 3 + off
    bx, by = bb[0] - pad, bb[1] - pad
    w, h = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((x - bx, y - by + off), text, font=font, fill=shadow_color, anchor=anchor)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    paste_rgba(layer, sh, bx, by)
    ImageDraw.Draw(layer).text((x, y), text, font=font, fill=fill, anchor=anchor)


def draw_rich(layer, x, y, text, font, fill=(255, 255, 255, 255), shadow=True, icon_color=None):
    """y = TOP of capital letters. Returns width. Supports ★ ⚡ 🔥 👑 💥 🩸 🌸 as vector icons."""
    items, total, cap, isz = _layout(text, font)
    base = int(round(y + cap))
    for ix, kind, val, w in items:
        px = int(round(x + ix))
        if kind == "t":
            if shadow:
                text_shadow(layer, (px, base), val, font, fill, anchor="ls")
            else:
                ImageDraw.Draw(layer).text((px, base), val, font=font, fill=fill, anchor="ls")
        else:
            col = ICON_COLORS.get(val) or icon_color or fill
            if val == "star":
                col = ICON_COLORS["star"]
            draw_icon(layer, val, px + w / 2.0, base - cap / 2.0, w, col)
    return total


def draw_lines(layer, lines, font, x, y, fill=(255, 255, 255, 255), align="left", box_w=0):
    """Draws lines (y = top of caps) and returns total height used"""
    step = line_step(font)
    for i, line in enumerate(lines):
        tw = text_w(line, font)
        if align == "center":
            lx = x + (box_w - tw) / 2
        elif align == "right":
            lx = x + box_w - tw
        else:
            lx = x
        draw_rich(layer, lx, y + i * step, line, font, fill)
    return block_h(font, len(lines))


def fit_lines(text, start, minimum, max_w, max_lines):
    """Reduces font size or wraps lines to fit within max_w and max_lines (uses current design TITLE font)"""
    size = int(start)
    while True:
        font = load_font(size, role="title")
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


# ======================= SHAPES / PANELS =======================

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


def add_smooth_gradient_bottom(img, gh, max_alpha=230, color=(0, 0, 0)):
    """Smooth non-linear dark gradient for cinematic contrast"""
    gh = int(min(gh, img.height))
    grad = Image.linear_gradient("L").resize((img.width, gh))
    alpha = grad.point(lambda p: int((p / 255.0) ** 1.3 * max_alpha))
    dark = Image.new("RGBA", (img.width, gh), tuple(color) + (255,))
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
    draw_icon(layer, "star", cx, cy, r * 2, fill)


# ======================= PILL BADGE (FIXED: perfectly centered text inside the curve) =======================

def pill_size(text, font, pad_x=16, pad_y=6):
    """(width, height) of a pill - height font size-la irundhu thaan, so all pills same height"""
    return int(text_w(text, font) + pad_x * 2), int(getattr(font, "size", 26) * 0.95 + pad_y * 2)


def draw_pill_badge(layer, x, y, text, font, bg_color, border_color=None, text_color=(255, 255, 255, 255), pad_x=16, pad_y=6):
    """Smooth anti-aliased capsule. Text cap-height-a vachu EXACT center-la varum (munnadi mela poi irundhuchu)."""
    x, y = int(x), int(y)
    w, h = pill_size(text, font, pad_x, pad_y)
    S = 4
    tile = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    td.rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=h * S // 2, fill=bg_color)
    if border_color:
        bw = max(1, int(round(h * 0.045)))
        td.rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=h * S // 2, outline=border_color, width=bw * S)
    paste_rgba(layer, tile.resize((w, h), Image.LANCZOS), x, y)
    cap = cap_h(font)
    draw_rich(layer, x + pad_x, y + (h - cap) / 2.0, text, font, text_color, shadow=False, icon_color=text_color)
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


# ---------------- extra helpers ----------------

def pill_row_center(layer, W, y, items, font, pad_x, pad_y, gap):
    """items = [(text, bg, border, text_color)]  -> centered row of pills"""
    if not items:
        return
    widths = [pill_size(t, font, pad_x, pad_y)[0] for t, _, _, _ in items]
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


def lerp_color(c0, c1, t):
    return tuple(int(c0[i] * (1 - t) + c1[i] * t) for i in range(len(c0)))


def multi_lerp(stops, t):
    """stops = [(pos, (r,g,b[,a])), ...] ascending"""
    if t <= stops[0][0]:
        return tuple(stops[0][1])
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if t <= p1:
            return lerp_color(c0, c1, (t - p0) / max(1e-6, p1 - p0))
    return tuple(stops[-1][1])


def gradient_text(layer, x, baseline, text, font, stops, stroke=0, stroke_fill=(0, 0, 0, 255), shadow=True):
    """Vertical-gradient filled text (cap-height span) + optional outline + soft shadow. x = left, baseline = y of baseline."""
    cap = cap_h(font)
    size = getattr(font, "size", 40)
    bb = _PROBE.textbbox((0, 0), text, font=font, anchor="ls", stroke_width=stroke)
    pad = stroke + int(size * 0.3) + 4
    w, h = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
    ox, oy = pad - bb[0], pad - bb[1]
    fill_m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(fill_m).text((ox, oy), text, font=font, fill=255, anchor="ls")
    full_m = fill_m
    if stroke:
        full_m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(full_m).text((ox, oy), text, font=font, fill=255, anchor="ls", stroke_width=stroke)
    tile = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if shadow:
        off = max(2, int(size * 0.05))
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sh.paste((0, 0, 0, 170), (0, off), full_m)
        tile.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(2, int(size * 0.06)))))
    if stroke:
        st = Image.new("RGBA", (w, h), stroke_fill)
        st.putalpha(full_m)
        tile.alpha_composite(st)
    col = Image.new("RGBA", (1, h))
    for yy in range(h):
        t = min(1.0, max(0.0, (yy - (oy - cap)) / float(cap)))
        c = multi_lerp(stops, t)
        col.putpixel((0, yy), tuple(c) + ((255,) if len(c) == 3 else ()))
    grad = col.resize((w, h))
    grad.putalpha(fill_m)
    tile.alpha_composite(grad)
    paste_rgba(layer, tile, x - ox, baseline - oy)
    return _PROBE.textlength(text, font=font)


def neon_text(layer, x, baseline, text, font, color, core=(255, 245, 252, 255)):
    """Neon-tube text: colored outline + white-hot core + 2-level glow"""
    size = getattr(font, "size", 40)
    sw = max(2, int(size * 0.035))
    bb = _PROBE.textbbox((0, 0), text, font=font, anchor="ls", stroke_width=sw)
    pad = int(size * 0.75)
    w, h = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
    ox, oy = pad - bb[0], pad - bb[1]
    stroke_m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(stroke_m).text((ox, oy), text, font=font, fill=255, anchor="ls", stroke_width=sw)
    fill_m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(fill_m).text((ox, oy), text, font=font, fill=255, anchor="ls")
    tile = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    big = Image.new("RGBA", (w, h), tuple(color[:3]) + (255,))
    big.putalpha(stroke_m.filter(ImageFilter.GaussianBlur(size * 0.20)))
    tile.alpha_composite(big)
    tile.alpha_composite(big)
    mid = Image.new("RGBA", (w, h), tuple(color[:3]) + (255,))
    mid.putalpha(stroke_m.filter(ImageFilter.GaussianBlur(size * 0.06)))
    tile.alpha_composite(mid)
    tube = Image.new("RGBA", (w, h), tuple(color[:3]) + (255,))
    tube.putalpha(stroke_m)
    tile.alpha_composite(tube)
    core_i = Image.new("RGBA", (w, h), core)
    core_i.putalpha(fill_m)
    tile.alpha_composite(core_i)
    paste_rgba(layer, tile, x - ox, baseline - oy)
    return _PROBE.textlength(text, font=font)


def spaced_width(text, font, spacing):
    return sum(_PROBE.textlength(c, font=font) for c in text) + spacing * max(0, len(text) - 1)


def draw_spaced(layer, x, y, text, font, spacing, fill):
    """Letter-spaced text (y = top of caps). Returns width."""
    cap = cap_h(font)
    base = int(round(y + cap))
    d = ImageDraw.Draw(layer)
    cx = x
    for c in text:
        d.text((int(round(cx)), base), c, font=font, fill=fill, anchor="ls")
        cx += _PROBE.textlength(c, font=font) + spacing
    return cx - x - spacing


def meta_join(items, sep="  •  "):
    return sep.join([i for i in items if i])


# ---------------- round-2 helpers ----------------

def flow_rows(items, font, max_w, pad_x, pad_y, gap):
    """items = [(text, bg, border, text_color)] -> rows that fit max_w (wrap pannum, box-ku veliya varaadhu)"""
    rows, cur, cw = [], [], 0
    for it in items:
        w = pill_size(it[0], font, pad_x, pad_y)[0]
        if cur and cw + gap + w > max_w:
            rows.append(cur)
            cur, cw = [], 0
        cur.append((it, w))
        cw += (gap if len(cur) > 1 else 0) + w
    if cur:
        rows.append(cur)
    return rows, pill_size("X", font, pad_x, pad_y)[1]


def flow_height(items, font, max_w, pad_x, pad_y, gap, row_gap):
    if not items:
        return 0
    rows, h = flow_rows(items, font, max_w, pad_x, pad_y, gap)
    return int(len(rows) * h + (len(rows) - 1) * row_gap)


def draw_flow(layer, x, y, items, font, max_w, pad_x, pad_y, gap, row_gap):
    """Draws pill rows with wrapping, returns total height"""
    if not items:
        return 0
    rows, h = flow_rows(items, font, max_w, pad_x, pad_y, gap)
    cy = y
    for row in rows:
        cx = x
        for (t, bg, bd, tc), w in row:
            draw_pill_badge(layer, cx, cy, t, font, bg, bd, tc, pad_x, pad_y)
            cx += w + gap
        cy += h + row_gap
    return int(len(rows) * h + (len(rows) - 1) * row_gap)


def fit_meta(make_text, genres, font, max_w):
    """Genres-a oru oru-vaa kuraichu text max_w-kulla fit aagura varaikkum"""
    gs = list(genres)
    while True:
        txt = make_text(gs)
        if text_w(txt, font) <= max_w or not gs:
            return txt
        gs = gs[:-1]


def prep_logo(raw_bytes, max_w, max_h, max_up=2.6):
    """TMDB logo -> crop transparent edges, scale BIG (upscale allowed), dark logo-na white-a maathum"""
    try:
        raw = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
    except Exception:
        return None
    box = raw.getchannel("A").getbbox()
    if box:
        raw = raw.crop(box)
    r = min(max_w / raw.width, max_h / raw.height, max_up)
    logo = raw.resize((max(10, int(raw.width * r)), max(10, int(raw.height * r))), Image.LANCZOS)
    try:
        from PIL import ImageStat
        a = logo.getchannel("A")
        stat = ImageStat.Stat(logo.convert("L"), mask=a.point(lambda p: 255 if p > 128 else 0))
        if stat.mean[0] < 85:                       # black/dark logo -> dark gradient-la theriyaadhu
            white = Image.new("RGBA", logo.size, (255, 255, 255, 255))
            white.putalpha(a)
            logo = white
    except Exception:
        pass
    return logo


def glow_text(layer, x, baseline, text, font, fill, glow, radius, strength=2):
    """Soft glowing text (golden hour / dreamy look)"""
    size = getattr(font, "size", 40)
    pad = int(radius * 3) + 4
    bb = _PROBE.textbbox((0, 0), text, font=font, anchor="ls")
    w, h = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
    ox, oy = pad - bb[0], pad - bb[1]
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).text((ox, oy), text, font=font, fill=255, anchor="ls")
    tile = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g = Image.new("RGBA", (w, h), tuple(glow[:3]) + (255,))
    g.putalpha(m.filter(ImageFilter.GaussianBlur(radius)).point(lambda p: min(255, int(p * 1.6))))
    for _ in range(strength):
        tile.alpha_composite(g)
    off = max(2, int(size * 0.04))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh.paste((0, 0, 0, 120), (0, off), m)
    tile.alpha_composite(sh.filter(ImageFilter.GaussianBlur(off)))
    t = Image.new("RGBA", (w, h), tuple(fill))
    t.putalpha(m)
    tile.alpha_composite(t)
    paste_rgba(layer, tile, x - ox, baseline - oy)


def para(layer, x, y, w, h, skew, fill, outline=None, ow=3):
    """Slanted parallelogram label (anime tag style)"""
    S = 3
    W_, H_ = int((w + skew + 8) * S), int((h + 8) * S)
    tile = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    pts = [(4 * S + skew * S, 4 * S), (4 * S + (w + skew) * S, 4 * S), (4 * S + w * S, 4 * S + h * S), (4 * S, 4 * S + h * S)]
    d.polygon(pts, fill=fill)
    if outline:
        d.line(pts + [pts[0]], fill=outline, width=max(1, int(ow * S)), joint="curve")
    paste_rgba(layer, tile.resize((W_ // S, H_ // S), Image.LANCZOS), x - 4, y - 4)


def burst(layer, cx, cy, R, fill, outline=None, spikes=22, inner=0.78, ow=5):
    """Comic/anime starburst badge"""
    S = 3
    N = int(2 * R + ow * 2 + 8)
    tile = Image.new("RGBA", (N * S, N * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    c = N * S / 2.0

    def pts(rad):
        out = []
        for i in range(spikes * 2):
            a = -math.pi / 2 + i * math.pi / spikes
            r = rad * S * (1 if i % 2 == 0 else inner)
            out.append((c + r * math.cos(a), c + r * math.sin(a)))
        return out
    if outline:
        d.polygon(pts(R), fill=outline)
        d.polygon(pts(R - ow), fill=fill)
    else:
        d.polygon(pts(R), fill=fill)
    paste_rgba(layer, tile.resize((N, N), Image.LANCZOS), cx - N / 2.0, cy - N / 2.0)


def brush_stroke(layer, x, y, w, h, color, seed=1):
    """Rough japanese brush stroke bar (tapered, slightly uneven)"""
    rnd = random.Random(seed)
    S = 3
    tw, th_ = int((w + 20) * S), int((h + 20) * S)
    tile = Image.new("RGBA", (tw, th_), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    n = 40
    top, bot = [], []
    for i in range(n + 1):
        t = i / float(n)
        px = 10 * S + t * w * S
        taper = min(1.0, t / 0.05, (1 - t) / 0.2) ** 0.6
        hh = h * S * (0.5 + 0.5 * taper)
        top.append((px, 10 * S + (h * S - hh) / 2 + rnd.uniform(-0.10, 0.10) * h * S))
        bot.append((px, 10 * S + (h * S + hh) / 2 + rnd.uniform(-0.10, 0.10) * h * S))
    d.polygon(top + bot[::-1], fill=color)
    paste_rgba(layer, tile.resize((tw // S, th_ // S), Image.LANCZOS), x - 10, y - 10)


# ======================= 18 THUMBNAIL DESIGNS =======================

@fonts("chakra-b", "chakra-sb")
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


@fonts("bebas", "poppins-md", upper=True)
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


@fonts("anton", "rajdhani-b", upper=True)
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


@fonts("poppins-xb", "poppins-md")
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


@fonts("titan", "poppins-b", upper=True)
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


@fonts("zenmaru-b", "zenmaru-md")
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
    total = pill_h + 16 * b + th + 18 * b + pill_h
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

    y += draw_lines(layer, lines, tfont, 0, y, align="center", box_w=W) + 18 * b
    gen = [(g, (255, 150, 190, 28), (255, 170, 205, 120), (255, 235, 242, 230)) for g in info.get("genres", [])[:3]]
    pill_row_center(layer, W, y, gen, gfont, 14 * b, 6 * b, 10 * b)


# ======================= 8 NEW DESIGNS (slots 8, 9, 10, 12, 14, 15, 16, 18) =======================

@fonts("poppins-xb", "poppins-sb")
def d_liquid_glass(img, layer, info, b):
    """10. 🫧 Liquid Glass: centered glass card with glossy sheen + circular rating ring"""
    W, H = img.size
    m, pad = int(64 * b), int(50 * b)
    try:
        rating = float(info.get("rating") or 0)
    except Exception:
        rating = 0.0
    ring_r = int(80 * b) if rating else 0
    ring_gap = int(46 * b) if rating else 0

    tfont, lines = fit_lines(info["title"], 112 * b, 52 * b, W * 0.52, 2)
    sfont, gfont = load_font(29 * b), load_font(30 * b)
    ph_ = pill_size("X", sfont, 16 * b, 5 * b)[1]
    th = block_h(tfont, len(lines))
    gtxt = "  •  ".join(info.get("genres", [])[:3])

    row_w = 0
    if info.get("type"):
        row_w += pill_size(info["type"].upper(), sfont, 16 * b, 5 * b)[0] + 10 * b
    if info.get("year"):
        row_w += pill_size(info["year"], sfont, 16 * b, 5 * b)[0]
    cw = max([text_w(l, tfont) for l in lines] + [row_w, text_w(gtxt, gfont), int(300 * b)])
    pw = int(cw + pad * 2 + ring_gap + ring_r * 2)
    ph = int(pad + ph_ + 18 * b + th + 16 * b + text_h(gfont) + pad)
    ph = max(ph, ring_r * 2 + pad * 2)
    x0, y0 = int((W - pw) / 2), H - m - ph
    rad = int(min(46 * b, ph / 2))

    add_smooth_gradient_bottom(img, H * 0.45, 150)
    glass_panel(img, layer, (x0, y0, x0 + pw, y0 + ph), rad, 30 * b, white=46, border_color=(255, 255, 255, 190))

    # glossy diagonal sheen
    sheen = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    ImageDraw.Draw(sheen).polygon([(0, 0), (int(pw * 0.55), 0), (int(pw * 0.30), ph), (0, ph)], fill=(255, 255, 255, 26))
    sheen.putalpha(ImageChops.multiply(sheen.split()[3], rounded_mask(pw, ph, rad)))
    paste_rgba(layer, sheen, x0, y0)

    # left content
    y = y0 + pad
    cur = x0 + pad
    if info.get("type"):
        w1, _ = draw_pill_badge(layer, cur, y, info["type"].upper(), sfont, (255, 255, 255, 48), (255, 255, 255, 150), (255, 255, 255, 255), 16 * b, 5 * b)
        cur += w1 + 10 * b
    if info.get("year"):
        draw_pill_badge(layer, cur, y, info["year"], sfont, (0, 0, 0, 55), (255, 255, 255, 90), (255, 255, 255, 235), 16 * b, 5 * b)
    y += ph_ + 18 * b
    y += draw_lines(layer, lines, tfont, x0 + pad, y) + 16 * b
    if gtxt:
        draw_rich(layer, x0 + pad, y, gtxt, gfont, (245, 248, 255, 225))

    # rating ring
    if rating:
        rcx, rcy = x0 + pw - pad - ring_r, y0 + ph // 2
        S = 4
        ts = int(ring_r * 2 + 24 * b)
        tile = Image.new("RGBA", (ts * S, ts * S), (0, 0, 0, 0))
        td = ImageDraw.Draw(tile)
        c = ts * S // 2
        rw = int(14 * b * S)
        rr = ring_r * S - rw // 2
        box = (c - rr, c - rr, c + rr, c + rr)
        td.ellipse(box, outline=(255, 255, 255, 60), width=rw)
        sweep = 360.0 * max(0.02, min(1.0, rating / 10.0))
        steps = max(8, int(sweep / 4))
        for i in range(steps):
            a0 = -90 + sweep * i / steps
            a1 = -90 + sweep * (i + 1) / steps + 1.2
            col = lerp_color((255, 214, 0), (255, 120, 0), i / max(1, steps - 1))
            td.arc(box, a0, a1, fill=col + (255,), width=rw)
        for ang, col in ((-90, (255, 214, 0)), (-90 + sweep, (255, 120, 0))):    # round caps
            ex, ey = c + rr * math.cos(math.radians(ang)), c + rr * math.sin(math.radians(ang))
            td.ellipse((ex - rw / 2, ey - rw / 2, ex + rw / 2, ey + rw / 2), fill=col + (255,))
        paste_rgba(layer, tile.resize((ts, ts), Image.LANCZOS), rcx - ts / 2, rcy - ts / 2)
        nfont = load_font(58 * b, family="poppins-xb")
        txt = f"{rating:.1f}"
        nw = _PROBE.textlength(txt, font=nfont)
        text_shadow(layer, (rcx - nw / 2, rcy + cap_h(nfont) / 2), txt, nfont, (255, 255, 255, 255), anchor="ls")


@fonts("bungee", "rajdhani-b")
def d_neon_tokyo(img, layer, info, b):
    """12. 🌃 Neon Tokyo: real neon-tube glowing title (magenta) + cyan neon underline on night tint"""
    W, H = img.size
    m = int(70 * b)
    img.alpha_composite(Image.new("RGBA", img.size, (8, 0, 24, 85)))
    add_smooth_gradient_bottom(img, H * 0.62, 225, color=(8, 0, 22))

    tfont, lines = fit_lines(info["title"], 140 * b, 56 * b, W * 0.78, 2)
    sfont, mfont = load_font(27 * b), load_font(31 * b)
    step, cap = line_step(tfont), cap_h(tfont)
    th = block_h(tfont, len(lines))
    ph = pill_size("X", sfont, 18 * b, 6 * b)[1]
    mh = text_h(mfont)
    lw_ = int(max(text_w(l, tfont) for l in lines))
    line_h = max(3, int(5 * b))
    total = ph + 24 * b + th + 22 * b + line_h + 20 * b + mh
    y = H - m - total

    pink, cyan = (255, 40, 175), (0, 232, 255)
    tags = []
    if info.get("type"):
        tags.append((info["type"].upper(), (0, 232, 255, 28), (0, 232, 255, 255), (190, 250, 255, 255)))
    if info.get("year"):
        tags.append((info["year"], (255, 40, 175, 28), (255, 70, 190, 255), (255, 205, 240, 255)))
    if info.get("rating"):
        tags.append((f"★ {info['rating']}", (255, 204, 0, 30), (255, 204, 0, 255), (255, 224, 80, 255)))
    pill_row_center(layer, W, y, tags, sfont, 18 * b, 6 * b, 14 * b)
    y += ph + 24 * b

    for i, ln in enumerate(lines):
        tw = _PROBE.textlength(ln, font=tfont)
        neon_text(layer, (W - tw) / 2, y + i * step + cap, ln, tfont, pink)
    y += th + 22 * b

    # neon underline
    ux0, ux1 = (W - lw_) / 2, (W + lw_) / 2
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle((ux0, y, ux1, y + line_h), radius=line_h // 2, fill=cyan + (255,))
    layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(int(10 * b))))
    layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(int(4 * b))))
    ImageDraw.Draw(layer).rounded_rectangle((ux0, y, ux1, y + line_h), radius=line_h // 2, fill=(215, 252, 255, 255))
    y += line_h + 20 * b

    if info.get("genres"):
        gtxt = "  •  ".join(info["genres"][:3]).upper()
        gw = text_w(gtxt, mfont)
        draw_rich(layer, (W - gw) / 2, y, gtxt, mfont, (170, 245, 255, 255))


@fonts("bebas", "rajdhani-b", upper=True)
def d_mega_score(img, layer, info, b):
    """14. 🏅 Mega Score: giant ghost rating number (gold outline) + bold title - rating thaan hero"""
    W, H = img.size
    m = int(70 * b)
    add_smooth_gradient_bottom(img, H * 0.66, 225)

    big = info.get("rating") or ""
    label = "RATING"
    if not big:
        big, label = info.get("year") or "", "YEAR"
    num_left = W - m

    if big:
        nfont = load_font(H * 0.54, family="anton")
        ncap = cap_h(nfont)
        nw = _PROBE.textlength(big, font=nfont)
        nx = W - m - nw
        nbase = H - int(m * 0.75)
        num_left = nx
        sw = max(3, int(5 * b))
        bb = _PROBE.textbbox((0, 0), big, font=nfont, anchor="ls", stroke_width=sw)
        pad = sw + 6
        tw_, th_ = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
        ox, oy = pad - bb[0], pad - bb[1]
        fm = Image.new("L", (tw_, th_), 0)
        ImageDraw.Draw(fm).text((ox, oy), big, font=nfont, fill=255, anchor="ls")
        sm = Image.new("L", (tw_, th_), 0)
        ImageDraw.Draw(sm).text((ox, oy), big, font=nfont, fill=255, anchor="ls", stroke_width=sw)
        ring = ImageChops.subtract(sm, fm)                    # outline only
        tile = Image.new("RGBA", (tw_, th_), (0, 0, 0, 0))
        col = Image.new("RGBA", (1, th_))
        for yy in range(th_):
            t = min(1.0, max(0.0, (yy - (oy - ncap)) / float(ncap)))
            col.putpixel((0, yy), multi_lerp([(0, (255, 226, 60, 255)), (1, (255, 120, 0, 255))], t))
        gfill = col.resize((tw_, th_))
        gfill.putalpha(fm.point(lambda p: int(p * 0.34)))     # translucent fill
        tile.alpha_composite(gfill)
        outline = col.resize((tw_, th_))
        outline.putalpha(ring)
        tile.alpha_composite(outline)
        paste_rgba(layer, tile, nx - ox, nbase - oy)

        lfont = load_font(34 * b)
        lt = f"★ {label}" if label == "RATING" else label
        draw_rich(layer, nx + 4 * b, nbase - ncap - 26 * b - cap_h(lfont), lt, lfont, (255, 214, 60, 255))

    max_w = max(W * 0.30, num_left - m - 50 * b)
    tfont, lines = fit_lines(info["title"], 180 * b, 66 * b, max_w, 3)
    sfont, gfont = load_font(27 * b), load_font(30 * b)
    th = block_h(tfont, len(lines))
    ph = pill_size("X", sfont, 18 * b, 6 * b)[1]
    gtxt = "  •  ".join(info.get("genres", [])[:3])
    total = ph + 20 * b + th + (18 * b + text_h(gfont) if gtxt else 0)
    y = H - m - total

    cur = m
    if info.get("type"):
        w1, _ = draw_pill_badge(layer, cur, y, info["type"].upper(), sfont, (255, 205, 0, 255), None, (20, 14, 0, 255), 18 * b, 6 * b)
        cur += w1 + 12 * b
    if info.get("year") and label == "RATING":
        draw_pill_badge(layer, cur, y, info["year"], sfont, (0, 0, 0, 110), (255, 255, 255, 140), (255, 255, 255, 240), 16 * b, 6 * b)
    y += ph + 20 * b
    y += draw_lines(layer, lines, tfont, m, y)
    if gtxt:
        draw_rich(layer, m, y + 18 * b, gtxt, gfont, (255, 240, 205, 235))


@fonts("luckiest", "lilita", upper=True)
def d_sticker_pop(img, layer, info, b):
    """16. 🍭 Sticker Pop: tilted cartoon sticker - yellow title, thick white + black outline, colorful pills"""
    W, H = img.size
    m = int(70 * b)
    add_smooth_gradient_bottom(img, H * 0.55, 200)

    tfont, lines = fit_lines(info["title"], 175 * b, 70 * b, W * 0.60, 2)
    sfont, gfont = load_font(30 * b), load_font(28 * b)
    step, cap = line_step(tfont), cap_h(tfont)
    th = block_h(tfont, len(lines))
    s_in, s_out = max(5, int(9 * b)), max(8, int(14 * b))
    ph = pill_size("X", sfont, 18 * b, 6 * b)[1]
    gph = pill_size("X", gfont, 16 * b, 5 * b)[1]
    gens = info.get("genres", [])[:3]

    ink = (22, 14, 12, 255)
    row1 = []
    if info.get("type"):
        row1.append((info["type"].upper(), (255, 214, 0, 255), (255, 255, 255, 255)))
    if info.get("year"):
        row1.append((info["year"], (255, 255, 255, 255), (255, 255, 255, 255)))
    if info.get("rating"):
        row1.append((f"★ {info['rating']}", (255, 70, 150, 255), (255, 255, 255, 255)))

    w_row1 = sum(pill_size(t, sfont, 18 * b, 6 * b)[0] for t, _, _ in row1) + 12 * b * max(0, len(row1) - 1)
    w_row3 = sum(pill_size(g, gfont, 16 * b, 5 * b)[0] for g in gens) + 10 * b * max(0, len(gens) - 1)
    tw_max = max([_PROBE.textlength(l, font=tfont) for l in lines] + [1])
    pad = int(40 * b)
    gw = int(max(tw_max + s_out * 2, w_row1, w_row3) + pad * 2)
    gh = int(pad + ph + 20 * b + th + s_out * 2 + (20 * b + gph if gens else 0) + pad)
    grp = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))

    y = pad
    cur = pad
    for t, bg, bd in row1:
        txtcol = (255, 255, 255, 255) if t.startswith("★") else ink
        w1, _ = draw_pill_badge(grp, cur, y, t, sfont, bg, ink, txtcol, 18 * b, 6 * b)
        cur += w1 + 12 * b
    y += ph + 20 * b + s_out

    gd = ImageDraw.Draw(grp)
    base0 = y + cap
    shadow_off = int(9 * b)
    for i, ln in enumerate(lines):
        bx = pad + s_out
        by = int(base0 + i * step)
        gd.text((bx + shadow_off, by + shadow_off), ln, font=tfont, fill=(0, 0, 0, 200), anchor="ls", stroke_width=s_out, stroke_fill=(0, 0, 0, 200))
        gd.text((bx, by), ln, font=tfont, fill=(255, 255, 255, 255), anchor="ls", stroke_width=s_out, stroke_fill=ink)
        gd.text((bx, by), ln, font=tfont, fill=(255, 255, 255, 255), anchor="ls", stroke_width=s_in, stroke_fill=(255, 255, 255, 255))
        gd.text((bx, by), ln, font=tfont, fill=(255, 224, 30, 255), anchor="ls")
    y += th + s_out

    if gens:
        cur = pad
        y += 20 * b
        pal = [(70, 225, 255, 255), (150, 255, 120, 255), (255, 160, 90, 255)]
        for i, gname in enumerate(gens):
            w1, _ = draw_pill_badge(grp, cur, y, gname, gfont, pal[i % 3], ink, ink, 16 * b, 5 * b)
            cur += w1 + 10 * b

    # sparkles
    def sparkle(cx, cy, r):
        pts = []
        for k in range(8):
            a = -math.pi / 2 + k * math.pi / 4
            rr = r if k % 2 == 0 else r * 0.3
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        gd.polygon(pts, fill=(255, 255, 255, 255), outline=ink)
    sparkle(gw - pad * 0.5, pad + ph + 10 * b, 26 * b)
    sparkle(gw - pad * 1.5, pad + ph * 0.2, 14 * b)

    # tilt + sticker shadow
    grp = grp.rotate(3, expand=True, resample=Image.BICUBIC)
    sh = Image.new("RGBA", grp.size, (0, 0, 0, 0))
    sh.putalpha(grp.split()[3].point(lambda p: int(p * 0.45)))
    sh = sh.filter(ImageFilter.GaussianBlur(int(8 * b)))
    px, py = m - int(30 * b), H - int(40 * b) - grp.height
    paste_rgba(layer, sh, px + 8 * b, py + 12 * b)
    paste_rgba(layer, grp, px, py)


@fonts("montserrat-sb", "montserrat-md")
def d_clean_minimal(img, layer, info, b):
    """18. 🤍 Clean Minimal: no boxes, no pills - thin line, light title, quiet rating | genres row"""
    W, H = img.size
    m = int(84 * b)
    add_smooth_gradient_bottom(img, H * 0.52, 200)

    tfont, lines = fit_lines(info["title"], 112 * b, 56 * b, W * 0.62, 2)
    lfont, mfont = load_font(22 * b), load_font(29 * b, family="poppins-md")
    th = block_h(tfont, len(lines))
    mh = text_h(mfont)
    total = cap_h(lfont) + 26 * b + th + 24 * b + mh
    y = H - m - total

    # label: short line + TYPE / YEAR
    label = "   /   ".join([p for p in [(info.get("type") or "").upper(), info.get("year") or ""] if p])
    ly = y
    ImageDraw.Draw(layer).rectangle((m, ly + cap_h(lfont) / 2 - 1, m + int(54 * b), ly + cap_h(lfont) / 2 + max(1, int(2 * b)) - 1), fill=(255, 255, 255, 235))
    if label:
        draw_spaced(layer, m + int(54 * b) + 18 * b, ly, label, lfont, 3.2 * b, (255, 255, 255, 235))
    y += cap_h(lfont) + 26 * b

    y += draw_lines(layer, lines, tfont, m, y) + 24 * b

    x = m
    if info.get("rating"):
        x += draw_rich(layer, x, y, f"★ {info['rating']}", mfont, (255, 255, 255, 255)) + 26 * b
        if info.get("genres"):
            ImageDraw.Draw(layer).rectangle((x, y - 2 * b, x + max(1, int(2 * b)), y + cap_h(mfont) + 2 * b), fill=(255, 255, 255, 170))
            x += 26 * b
    if info.get("genres"):
        draw_rich(layer, x, y, "  •  ".join(info["genres"][:3]), mfont, (255, 255, 255, 225))



# ======================= ROUND 2: FIXED + NEW DESIGNS =======================

@fonts("chakra-b", "chakra-sb")
def d_cyber_logo(img, layer, info, b):
    """7. 🔥 Cyber Logo: BIG official TMDB title logo + cyan neon aura + HUD brackets (logo illana neon text title)"""
    W, H = img.size
    m = int(72 * b)
    add_smooth_gradient_bottom(img, H * 0.68, 238)
    add_angled_gradient_left(img, W * 0.50, 120)

    sfont, gfont = load_font(27 * b), load_font(25 * b)
    ph = pill_size("X", sfont, 18 * b, 6 * b)[1]
    bar_h, bar_w = max(3, int(5 * b)), int(210 * b)
    max_row = int(W * 0.60)

    logo = prep_logo(info["logo_bytes"], W * 0.58, H * 0.36) if info.get("logo_bytes") else None

    items = []
    if info.get("rating"):
        items.append((f"★ {info['rating']}", (255, 204, 0, 35), (255, 204, 0, 220), (255, 215, 0, 255)))
    for g in info.get("genres", [])[:3]:
        items.append((g, (0, 240, 255, 22), (0, 240, 255, 120), (220, 245, 255, 235)))
    flow_h = flow_height(items, gfont, max_row, 16 * b, 6 * b, 10 * b, 10 * b)

    if logo is not None:
        main_h = logo.height
    else:
        tfont, lines = fit_lines(info["title"], 150 * b, 60 * b, W * 0.62, 2)
        main_h = block_h(tfont, len(lines))

    total = ph + 20 * b + main_h + 20 * b + bar_h + 18 * b + flow_h
    y = H - m - total

    # category + year
    cat = info["type"].upper() if info.get("type") else "ANIME"
    w1, _ = draw_pill_badge(layer, m, y, f"⚡ {cat}", sfont, (0, 240, 255, 30), (0, 240, 255, 210), (0, 240, 255, 255), 18 * b, 6 * b)
    if info.get("year"):
        draw_pill_badge(layer, m + w1 + 12 * b, y, info["year"], sfont, (255, 255, 255, 25), (255, 255, 255, 90), (255, 255, 255, 235), 16 * b, 6 * b)
    y += ph + 20 * b

    if logo is not None:
        lx, ly = m, int(y)
        a = logo.getchannel("A")
        sh = Image.new("RGBA", (logo.width + 160, logo.height + 160), (0, 0, 0, 0))     # dark base shadow
        sh.paste((0, 0, 0, 210), (80, 80 + int(8 * b)), a)
        paste_rgba(layer, sh.filter(ImageFilter.GaussianBlur(int(14 * b))), lx - 80, ly - 80)
        aura = Image.new("RGBA", (logo.width + 200, logo.height + 200), (0, 0, 0, 0))   # neon aura
        aura.paste((0, 240, 255, 190), (100, 100), a)
        aura = aura.filter(ImageFilter.GaussianBlur(int(16 * b)))
        paste_rgba(layer, aura, lx - 100, ly - 100)
        paste_rgba(layer, aura.filter(ImageFilter.GaussianBlur(int(4 * b))), lx - 100, ly - 100)
        paste_rgba(layer, logo, lx, ly)
        # HUD corner brackets
        d = ImageDraw.Draw(layer)
        cb, cw_, cs = (0, 240, 255, 230), max(3, int(4 * b)), int(40 * b)
        g = int(24 * b)
        corner_bracket(d, lx - g, ly - g, cs, cw_, 1, 1, cb)
        corner_bracket(d, lx + logo.width + g, ly + logo.height + g, cs, cw_, -1, -1, cb)
    else:
        step, cap = line_step(tfont), cap_h(tfont)
        for i, ln in enumerate(lines):
            neon_text(layer, m, y + i * step + cap, ln, tfont, (0, 225, 255))
    y += main_h + 20 * b

    for i in range(bar_w):          # cyan -> violet bar
        t = i / float(bar_w)
        ImageDraw.Draw(layer).line([(m + i, y), (m + i, y + bar_h)], fill=(int(168 * t), int(240 - 155 * t), int(255 - 8 * t), 255))
    y += bar_h + 18 * b

    draw_flow(layer, m, y, items, gfont, max_row, 16 * b, 6 * b, 10 * b, 10 * b)


@fonts("poppins-b", "poppins-md")
def d_vision_glass(img, layer, info, b):
    """3. 💎 Vision Glass: Modern Floating Frosted Glass Dock with Specular Shine"""
    W, H = img.size
    pad, m = int(45 * b), int(60 * b)
    tfont, lines = fit_lines(info["title"], 84 * b, 44 * b, W * 0.50, 2)
    sfont, gfont = load_font(28 * b), load_font(24 * b)

    row_w = 0
    if info.get("type"):
        row_w += pill_size(info["type"].upper(), sfont, 14 * b, 4 * b)[0] + 10 * b
    if info.get("year"):
        row_w += pill_size(info["year"], sfont, 12 * b, 4 * b)[0] + 10 * b
    if info.get("rating"):
        row_w += pill_size(f"★ {info['rating']}", sfont, 14 * b, 4 * b)[0] + 24 * b

    gitems = [(g, (255, 255, 255, 20), (255, 255, 255, 60), (240, 240, 245, 215)) for g in info.get("genres", [])[:3]]
    gen_nat = sum(pill_size(t[0], gfont, 14 * b, 4 * b)[0] for t in gitems) + 10 * b * max(0, len(gitems) - 1)
    cw = int(max([text_w(l, tfont) for l in lines] + [int(320 * b), row_w, min(gen_nat, W * 0.50)]))
    pw = int(cw + pad * 2)
    gen_h = flow_height(gitems, gfont, cw, 14 * b, 4 * b, 10 * b, 8 * b)       # genres wrap -> box-ku ulla thaan irukkum
    ph = int(pad + 36 * b + 16 * b + block_h(tfont, len(lines)) + (16 * b + gen_h if gitems else 0) + pad)

    x0, y0 = m, H - m - ph
    glass_panel(img, layer, (x0, y0, x0 + pw, y0 + ph), 36 * b, 26 * b, white=55)

    y = y0 + pad
    cur_x = x0 + pad
    if info.get("type"):
        tw, _ = draw_pill_badge(layer, cur_x, y, info["type"].upper(), sfont, (255, 255, 255, 35), (255, 255, 255, 90), (255, 255, 255, 240), 14 * b, 4 * b)
        cur_x += tw + 10 * b
    if info.get("year"):
        yw, _ = draw_pill_badge(layer, cur_x, y, info["year"], sfont, (255, 255, 255, 20), (255, 255, 255, 60), (255, 255, 255, 210), 12 * b, 4 * b)
        cur_x += yw + 10 * b
    if info.get("rating"):
        rt = f"★ {info['rating']}"
        draw_pill_badge(layer, x0 + pw - pad - pill_size(rt, sfont, 14 * b, 4 * b)[0], y, rt, sfont, (255, 204, 0, 40), (255, 204, 0, 200), (255, 215, 0, 255), 14 * b, 4 * b)

    y += 36 * b + 16 * b
    y += draw_lines(layer, lines, tfont, x0 + pad, y) + 16 * b
    draw_flow(layer, x0 + pad, y, gitems, gfont, cw, 14 * b, 4 * b, 10 * b, 8 * b)


@fonts("russo", "rajdhani-b", upper=True)
def d_manga_panel(img, layer, info, b):
    """17. 📖 Manga Panel: White comic frame + solid white title box with hard black shadow"""
    W, H = img.size
    d = ImageDraw.Draw(layer)
    fi = int(22 * b)
    d.rectangle((fi, fi, W - fi, H - fi), outline=(255, 255, 255, 255), width=max(4, int(10 * b)))

    tfont, lines = fit_lines(info["title"], 100 * b, 48 * b, W * 0.58, 2)
    sfont, mfont = load_font(26 * b), load_font(26 * b)
    padx, pady = int(34 * b), int(24 * b)

    def make(gs):
        parts = [p for p in [info.get("year"), f"★ {info['rating']}" if info.get("rating") else None] + gs if p]
        return "  /  ".join(parts)
    meta = fit_meta(make, info.get("genres", [])[:2], mfont, W * 0.60)       # meta text box-ku ulla fit aagum

    cw = max([text_w(l, tfont) for l in lines] + [text_w(meta, mfont), int(300 * b)])
    bw = int(cw + padx * 2)
    bh = int(pady * 2 + block_h(tfont, len(lines)) + 12 * b + text_h(mfont))
    x0 = int(70 * b)
    y0 = H - int(80 * b) - bh
    off = int(12 * b)

    d.rectangle((x0 + off, y0 + off, x0 + bw + off, y0 + bh + off), fill=(0, 0, 0, 255))   # hard shadow
    d.rectangle((x0, y0, x0 + bw, y0 + bh), fill=(255, 255, 255, 255))
    d.rectangle((x0, y0, x0 + bw, y0 + bh), outline=(0, 0, 0, 255), width=max(3, int(5 * b)))

    tag = (info.get("type") or "NEW SERIES").upper()
    tgw = int(text_w(tag, sfont) + 30 * b)
    tgh = int(text_h(sfont) + 14 * b)
    d.rectangle((x0, y0 - tgh, x0 + tgw, y0), fill=(220, 20, 30, 255))
    draw_rich(layer, x0 + 15 * b, y0 - tgh + (tgh - cap_h(sfont)) / 2, tag, sfont, (255, 255, 255, 255), shadow=False)

    y = y0 + pady
    step = line_step(tfont)
    for i, ln in enumerate(lines):
        draw_rich(layer, x0 + padx, y + i * step, ln, tfont, (12, 12, 14, 255), shadow=False)
    y += block_h(tfont, len(lines)) + 12 * b
    draw_rich(layer, x0 + padx, y, meta, mfont, (70, 70, 78, 255), shadow=False)


@fonts("anton", "rajdhani-b", upper=True)
def d_blade_slash(img, layer, info, b):
    """8. ⚔️ Blade Slash: small soft black shadow behind text + glowing crimson tapered blade slash"""
    W, H = img.size
    m = int(72 * b)

    tfont, lines = fit_lines(info["title"], 150 * b, 62 * b, W * 0.42, 3)
    sfont, mfont = load_font(27 * b), load_font(31 * b)
    th = block_h(tfont, len(lines))
    ph = pill_size("X", sfont, 18 * b, 6 * b)[1]
    bar_h, bar_w, skew = max(4, int(8 * b)), int(190 * b), int(16 * b)

    def make(gs):
        parts = []
        if info.get("rating"):
            parts.append(f"★ {info['rating']}")
        if gs:
            parts.append("  •  ".join(gs))
        return "   |   ".join(parts)
    meta = fit_meta(make, info.get("genres", [])[:3], mfont, W * 0.42)

    total = ph + 20 * b + th + 20 * b + bar_h + 18 * b + text_h(mfont)
    y = H - m - total
    pills_w = (pill_size(info["type"].upper(), sfont, 18 * b, 6 * b)[0] + 12 * b if info.get("type") else 0) + \
              (pill_size(info["year"], sfont, 16 * b, 6 * b)[0] if info.get("year") else 0)
    block_w = int(max([text_w(l, tfont) for l in lines] + [text_w(meta, mfont), bar_w, pills_w]))

    # --- small soft black shadow just behind the text (half-image panel illa) ---
    ps = int(48 * b)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((m - ps, y - ps, m + block_w + ps, H - m + ps), radius=int(44 * b), fill=(0, 0, 0, 190))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(int(52 * b))))
    add_smooth_gradient_bottom(img, H * 0.25, 90)

    # --- glowing tapered blade slash beside the text ---
    bx = m + block_w + int(150 * b)
    bot_y, tip_y = H + int(10 * b), int(H * 0.50)
    tip_x = bx + int(W * 0.075)
    bw = int(22 * b)
    poly = [(bx - bw, bot_y), (tip_x, tip_y), (bx + int(bw * 0.3), bot_y)]
    blade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(blade).polygon(poly, fill=(255, 30, 70, 235))
    glow = blade.filter(ImageFilter.GaussianBlur(int(16 * b)))
    img.alpha_composite(glow)
    img.alpha_composite(glow)
    img.alpha_composite(blade)
    core = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(core).line([(bx - int(bw * 0.15), bot_y), (tip_x, tip_y)], fill=(255, 240, 244, 255), width=max(2, int(4 * b)))
    img.alpha_composite(core)
    thin = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(thin).line([(bx + int(60 * b), bot_y), (tip_x + int(34 * b), int(H * 0.68))], fill=(255, 30, 70, 190), width=max(2, int(4 * b)))
    img.alpha_composite(thin.filter(ImageFilter.GaussianBlur(int(5 * b))))
    img.alpha_composite(thin)

    # --- text block ---
    cur = m
    if info.get("type"):
        w1, _ = draw_pill_badge(layer, cur, y, info["type"].upper(), sfont, (225, 20, 55, 255), None, (255, 255, 255, 255), 18 * b, 6 * b)
        cur += w1 + 12 * b
    if info.get("year"):
        draw_pill_badge(layer, cur, y, info["year"], sfont, (0, 0, 0, 110), (255, 255, 255, 140), (255, 255, 255, 240), 16 * b, 6 * b)
    y += ph + 20 * b
    y += draw_lines(layer, lines, tfont, m, y) + 20 * b
    ImageDraw.Draw(layer).polygon(
        [(m + skew, y), (m + bar_w + skew, y), (m + bar_w, y + bar_h), (m, y + bar_h)], fill=(255, 35, 70, 255))
    y += bar_h + 18 * b
    draw_rich(layer, m, y, meta, mfont, (255, 232, 238, 240))


@fonts("dela", "rajdhani-b", upper=True)
def d_anime_opening(img, layer, info, b):
    """6. ⛩️ Anime Opening: TV anime OP title card - slanted outlined logo, speed lines, red tag, score burst"""
    W, H = img.size
    m = int(72 * b)
    add_smooth_gradient_bottom(img, H * 0.56, 190)

    # speed (focus) lines behind the title
    rnd = random.Random(sum(map(ord, info["title"])))
    fx, fy = m + W * 0.24, H - m - H * 0.17
    sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sl)
    for _ in range(130):
        a = rnd.uniform(0, 2 * math.pi)
        r0 = rnd.uniform(0.20, 0.34) * H
        r1 = r0 + rnd.uniform(0.25, 0.75) * H
        sd.line([(fx + math.cos(a) * r0, fy + math.sin(a) * r0), (fx + math.cos(a) * r1, fy + math.sin(a) * r1)],
                fill=(255, 255, 255, rnd.randint(30, 85)), width=max(1, int(rnd.uniform(1, 4.5) * b)))
    fade = Image.linear_gradient("L").transpose(Image.ROTATE_270).resize((W, H)).point(lambda p: int(p * 0.9))
    sl.putalpha(ImageChops.multiply(sl.split()[3], fade))
    img.alpha_composite(sl)

    # --- slanted title logo: white fill + dark outline + red offset shadow ---
    tfont, lines = fit_lines(info["title"], 142 * b, 54 * b, W * 0.50, 3)
    sfont, mfont = load_font(27 * b), load_font(28 * b)
    cap, step = cap_h(tfont), line_step(tfont)
    so, off = max(6, int(13 * b)), int(10 * b)
    pad = so + off + 6
    tw = int(max(_PROBE.textlength(l, font=tfont) for l in lines))
    th = block_h(tfont, len(lines))
    gw, gh = tw + pad * 2, th + pad * 2
    tile = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    for i, ln in enumerate(lines):
        td.text((pad + off, pad + cap + i * step + off), ln, font=tfont, fill=(255, 35, 60, 255), anchor="ls",
                stroke_width=so, stroke_fill=(255, 35, 60, 255))
    for i, ln in enumerate(lines):
        td.text((pad, pad + cap + i * step), ln, font=tfont, fill=(255, 255, 255, 255), anchor="ls",
                stroke_width=so, stroke_fill=(14, 10, 22, 255))
    k = 0.18
    nw = gw + int(k * gh)
    tile = tile.transform((nw, gh), Image.AFFINE, (1, k, -k * gh, 0, 1, 0), resample=Image.BICUBIC)

    # --- meta bar text (fits) ---
    def make(gs):
        parts = []
        if info.get("rating"):
            parts.append(f"★ {info['rating']}")
        if gs:
            parts.append("  •  ".join(gs))
        return "   |   ".join(parts)
    meta = fit_meta(make, info.get("genres", [])[:3], mfont, W * 0.46)

    ph = pill_size("X", sfont, 20 * b, 6 * b)[1]
    bar_h = int(mfont.size * 0.95 + 16 * b)
    total = ph + 12 * b + gh + 4 * b + bar_h
    y = H - m - total

    # tag row (slanted labels)
    sk = int(12 * b)
    tx = m
    if info.get("type"):
        tt = info["type"].upper()
        wt = int(text_w(tt, sfont) + 34 * b)
        para(layer, tx, y, wt, ph, sk, (230, 25, 50, 255))
        draw_rich(layer, tx + sk / 2 + 17 * b, y + (ph - cap_h(sfont)) / 2, tt, sfont, (255, 255, 255, 255), shadow=False)
        tx += wt + sk + 12 * b
    if info.get("year"):
        wy = int(text_w(info["year"], sfont) + 30 * b)
        para(layer, tx, y, wy, ph, sk, (10, 8, 16, 230), (255, 255, 255, 235), 2)
        draw_rich(layer, tx + sk / 2 + 15 * b, y + (ph - cap_h(sfont)) / 2, info["year"], sfont, (255, 255, 255, 255), shadow=False)
    y += ph + 12 * b

    paste_rgba(layer, tile, m - pad, y)

    # score burst at the title's top-right
    if info.get("rating"):
        R = int(78 * b)
        bcx = min(m + tw + k * gh * 0.50 + R + 14 * b, W * 0.72)
        bcy = y + pad + cap * 0.30
        burst(layer, bcx, bcy, R, (255, 226, 0, 255), (14, 10, 22, 255), 22, 0.78, max(4, int(6 * b)))
        nf = load_font(44 * b)
        rt = str(info["rating"])
        nw_ = _PROBE.textlength(rt, font=nf)
        ImageDraw.Draw(layer).text((bcx - nw_ / 2, bcy + cap_h(nf) / 2), rt, font=nf, fill=(14, 10, 22, 255), anchor="ls")
    y += gh + 4 * b

    # meta bar
    bw_ = int(text_w(meta, mfont) + 40 * b)
    para(layer, m, y, bw_, bar_h, sk, (8, 6, 14, 225), (255, 255, 255, 220), 2)
    draw_rich(layer, m + sk / 2 + 20 * b, y + (bar_h - cap_h(mfont)) / 2, meta, mfont, (255, 255, 255, 245), shadow=False)


@fonts("montserrat-sb", "montserrat-md")
def d_golden_hour(img, layer, info, b):
    """9. 🌅 Golden Hour: Shinkai-style warm sunset grade, sun flare, floating light particles, glowing title"""
    W, H = img.size
    m = int(80 * b)
    rnd = random.Random(sum(map(ord, info["title"])))

    img.alpha_composite(Image.new("RGBA", img.size, (255, 150, 90, 40)))           # warm grade

    sx, sy = int(W * 0.84), int(H * 0.15)                                         # sun glow
    R = int(H * 0.42)
    rg = Image.radial_gradient("L").resize((2 * R, 2 * R), Image.BICUBIC)
    sun = Image.new("RGBA", (2 * R, 2 * R), (255, 226, 170, 255))
    sun.putalpha(rg.point(lambda p: int(((255 - p) / 255.0) ** 2.2 * 235)))
    paste_rgba(img, sun, sx - R, sy - R)
    st = Image.new("RGBA", (W, H), (0, 0, 0, 0))                                  # anamorphic streak
    ImageDraw.Draw(st).ellipse((sx - W * 0.34, sy - int(4 * b), sx + W * 0.34, sy + int(4 * b)), fill=(255, 236, 200, 85))
    img.alpha_composite(st.filter(ImageFilter.GaussianBlur(int(6 * b))))

    fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))                                  # lens flare discs
    fd = ImageDraw.Draw(fl)
    for t, rad, col in [(0.38, 34, (255, 196, 140, 70)), (0.62, 22, (150, 210, 255, 60)), (0.80, 48, (255, 140, 190, 46)),
                        (1.02, 28, (255, 220, 160, 64)), (1.30, 70, (180, 160, 255, 34))]:
        px, py = sx + (W / 2 - sx) * t, sy + (H / 2 - sy) * t
        r = rad * b
        fd.ellipse((px - r, py - r, px + r, py + r), fill=col)
        fd.ellipse((px - r, py - r, px + r, py + r), outline=col[:3] + (min(255, col[3] + 60),), width=max(1, int(2 * b)))
    img.alpha_composite(fl.filter(ImageFilter.GaussianBlur(max(1, int(1.5 * b)))))

    bk = Image.new("RGBA", (W, H), (0, 0, 0, 0))                                  # floating light particles
    bd = ImageDraw.Draw(bk)
    for _ in range(46):
        x, yy, r = rnd.randint(0, W), rnd.randint(0, int(H * 0.78)), rnd.uniform(3, 15) * b
        col = rnd.choice([(255, 236, 200), (255, 210, 160), (255, 255, 255), (255, 190, 200)])
        bd.ellipse((x - r, yy - r, x + r, yy + r), fill=col + (rnd.randint(45, 140),))
    img.alpha_composite(bk.filter(ImageFilter.GaussianBlur(max(1, int(1.3 * b)))))
    add_smooth_gradient_bottom(img, H * 0.55, 205, color=(34, 10, 48))

    # --- text ---
    tfont, lines = fit_lines(info["title"], 112 * b, 54 * b, W * 0.62, 2)
    lfont, mfont = load_font(24 * b, family="montserrat-md"), load_font(29 * b, family="montserrat-md")
    step, cap = line_step(tfont), cap_h(tfont)
    th = block_h(tfont, len(lines))
    ph = pill_size("X", mfont, 18 * b, 6 * b)[1]
    label = "   ·   ".join([p for p in [(info.get("type") or "").upper(), info.get("year") or ""] if p])
    line_h = max(2, int(3 * b))
    total = cap_h(lfont) + 26 * b + th + 20 * b + line_h + 22 * b + ph
    y = H - m - total

    draw_icon(layer, "sparkle", m + 11 * b, y + cap_h(lfont) / 2, 22 * b, (255, 224, 170, 255))
    if label:
        draw_spaced(layer, m + 34 * b, y, label, lfont, 3.4 * b, (255, 224, 180, 255))
    y += cap_h(lfont) + 26 * b

    for i, ln in enumerate(lines):
        glow_text(layer, m, y + i * step + cap, ln, tfont, (255, 255, 255, 255), (255, 170, 120, 255), int(14 * b))
    y += th + 20 * b

    lw_ = int(320 * b)
    for i in range(lw_):                                                          # fading peach line
        ImageDraw.Draw(layer).line([(m + i, y), (m + i, y + line_h)], fill=(255, 205, 160, int(230 * (1 - i / float(lw_)))))
    y += line_h + 22 * b

    x = m
    if info.get("rating"):
        rt = f"★ {info['rating']}"
        pw_, _ = draw_pill_badge(layer, x, y, rt, mfont, (255, 255, 255, 40), (255, 255, 255, 140), (255, 255, 255, 255), 18 * b, 6 * b)
        x += pw_ + 22 * b

    def make(gs):
        return "  •  ".join(gs)
    gtxt = fit_meta(make, info.get("genres", [])[:3], mfont, W * 0.62 - (x - m))
    if gtxt:
        draw_rich(layer, x, y + (ph - cap_h(mfont)) / 2, gtxt, mfont, (255, 244, 232, 245))


@fonts("dela", "rajdhani-b", upper=True)
def d_rising_sun(img, layer, info, b):
    """15. 🔴 Rising Sun: big red sun disc, japanese brush-stroke underline, red hanko score seal, vertical katakana"""
    W, H = img.size
    m = int(72 * b)
    add_smooth_gradient_bottom(img, H * 0.55, 195)

    # --- red sun disc (soft radial fade + glow + ring) ---
    R = int(H * 0.31)
    scx, scy = int(m + W * 0.15), int(H * 0.50)
    pad_s = int(90 * b)
    n = 2 * R + pad_s * 2
    glow = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((pad_s - 8 * b, pad_s - 8 * b, pad_s + 2 * R + 8 * b, pad_s + 2 * R + 8 * b), fill=(255, 40, 60, 105))
    paste_rgba(layer, glow.filter(ImageFilter.GaussianBlur(int(34 * b))), scx - n // 2, scy - n // 2)
    S = 2
    cm = Image.new("L", (2 * R * S, 2 * R * S), 0)
    ImageDraw.Draw(cm).ellipse((0, 0, 2 * R * S - 1, 2 * R * S - 1), fill=255)
    cm = cm.resize((2 * R, 2 * R), Image.LANCZOS)
    rg = Image.radial_gradient("L").resize((2 * R, 2 * R), Image.BICUBIC).point(lambda p: int(138 - min(p, 255) * 0.28))
    disc = Image.new("RGBA", (2 * R, 2 * R), (228, 26, 46, 255))
    disc.putalpha(ImageChops.multiply(rg, cm))
    paste_rgba(layer, disc, scx - R, scy - R)
    ring = Image.new("RGBA", (n * S, n * S), (0, 0, 0, 0))
    rr = R + int(20 * b)
    ImageDraw.Draw(ring).ellipse(((pad_s + R - rr) * S, (pad_s + R - rr) * S, (pad_s + R + rr) * S, (pad_s + R + rr) * S),
                                 outline=(255, 255, 255, 125), width=max(2, int(3 * b)) * S)
    paste_rgba(layer, ring.resize((n, n), Image.LANCZOS), scx - n // 2, scy - n // 2)

    # --- hanko score seal + vertical katakana (top-left) ---
    ky = m
    cx_col = m + int(56 * b)
    if info.get("rating"):
        sz = int(112 * b)
        seal = Image.new("RGBA", (sz * 3, sz * 3), (0, 0, 0, 0))
        sdr = ImageDraw.Draw(seal)
        sdr.rounded_rectangle((0, 0, sz * 3 - 1, sz * 3 - 1), radius=int(16 * b) * 3, fill=(220, 20, 38, 255))
        ins = int(8 * b) * 3
        sdr.rounded_rectangle((ins, ins, sz * 3 - 1 - ins, sz * 3 - 1 - ins), radius=int(10 * b) * 3, outline=(255, 255, 255, 235), width=max(2, int(3 * b)) * 3)
        paste_rgba(layer, seal.resize((sz, sz), Image.LANCZOS), m, ky)
        nf, lf = load_font(46 * b), load_font(17 * b)
        rt = str(info["rating"])
        nw_ = _PROBE.textlength(rt, font=nf)
        d_ = ImageDraw.Draw(layer)
        d_.text((m + sz / 2 - nw_ / 2, ky + sz * 0.70), rt, font=nf, fill=(255, 255, 255, 255), anchor="ls")
        lw2 = _PROBE.textlength("SCORE", font=lf)
        d_.text((m + sz / 2 - lw2 / 2, ky + sz * 0.27 + cap_h(lf)), "SCORE", font=lf, fill=(255, 235, 235, 255), anchor="ls")
        ky += sz + int(26 * b)
        cx_col = m + sz // 2
    kf = load_font(60 * b, family="dela")
    for ch in "アニメ":
        text_shadow(layer, (cx_col, ky + 34 * b), ch, kf, (255, 255, 255, 240), anchor="mm")
        ky += int(76 * b)

    # --- bottom-left text ---
    tfont, lines = fit_lines(info["title"], 132 * b, 52 * b, W * 0.60, 3)
    sfont, mfont = load_font(27 * b), load_font(29 * b)
    step, cap = line_step(tfont), cap_h(tfont)
    th = block_h(tfont, len(lines))
    ph = pill_size("X", sfont, 18 * b, 6 * b)[1]
    brush_h = int(20 * b)

    def make(gs):
        return "  •  ".join(gs)
    gtxt = fit_meta(make, info.get("genres", [])[:3], mfont, W * 0.58)
    total = ph + 18 * b + th + 14 * b + brush_h + 16 * b + (text_h(mfont) if gtxt else 0)
    y = H - m - total
    x0 = m + int(10 * b)

    cur = x0
    if info.get("type"):
        w1, _ = draw_pill_badge(layer, cur, y, info["type"].upper(), sfont, (255, 255, 255, 245), None, (14, 10, 22, 255), 18 * b, 6 * b)
        cur += w1 + 12 * b
    if info.get("year"):
        draw_pill_badge(layer, cur, y, info["year"], sfont, (0, 0, 0, 90), (255, 255, 255, 220), (255, 255, 255, 255), 16 * b, 6 * b)
    y += ph + 18 * b
    y += draw_lines(layer, lines, tfont, x0, y) + 14 * b

    bw_ = int(max(max(text_w(l, tfont) for l in lines) * 0.92, 280 * b))
    brush_stroke(layer, x0, y, bw_, brush_h, (230, 25, 45, 255), seed=sum(map(ord, info["title"])))
    brush_stroke(layer, x0 + int(bw_ * 0.08), y + int(brush_h * 0.30), int(bw_ * 0.45), max(2, int(brush_h * 0.22)), (255, 255, 255, 150), seed=7)
    y += brush_h + 16 * b
    if gtxt:
        draw_rich(layer, x0, y, gtxt, mfont, (255, 240, 240, 240))



# ======================= DESIGNS REGISTRY =======================
# Slot numbers (1-18) maaralai - so users-oda saved style selection break aagaadhu.
# 6, 8, 9, 10, 12, 14, 15, 16, 18 -> pudhu "super" designs.

DESIGNS = {
    1: ("🌟 Cyber Glow", d_cyber_neon),
    2: ("🎬 Cinematic Prime", d_cinematic_prime),
    3: ("💎 Vision Glass", d_vision_glass),
    4: ("🎌 Tokyo Action", d_tokyo_action),
    5: ("🌌 Aurora Horizon", d_aurora_horizon),
    6: ("⛩️ Anime Opening", d_anime_opening),
    7: ("🔥 Cyber Logo", d_cyber_logo),
    8: ("⚔️ Blade Slash", d_blade_slash),
    9: ("🌅 Golden Hour", d_golden_hour),
    10: ("🫧 Liquid Glass", d_liquid_glass),
    11: ("⚡ Comic Pop", d_comic_pop),
    12: ("🌃 Neon Tokyo", d_neon_tokyo),
    13: ("🌸 Sakura Dream", d_sakura_dream),
    14: ("🏅 Mega Score", d_mega_score),
    15: ("🔴 Rising Sun", d_rising_sun),
    16: ("🍭 Sticker Pop", d_sticker_pop),
    17: ("📖 Manga Panel", d_manga_panel),
    18: ("🤍 Clean Minimal", d_clean_minimal),
}

def design_name(st):
    return DESIGNS[st][0] if st in DESIGNS else "Plain (Watermark only)"
