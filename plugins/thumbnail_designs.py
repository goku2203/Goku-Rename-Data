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
            c["title"], c["ui"] = title, ui
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
    "👑": "crown", "💥": "burst", "🩸": "drop", "🌸": "flower",
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


# ======================= 18 THUMBNAIL DESIGNS =======================

@fonts("orbitron", "rajdhani-b")
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
    cw = max([text_w(l, tfont) for l in lines] + [int(320 * b), int(row_w)])
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
        draw_pill_badge(layer, x0 + pw - pad - pill_size(f"★ {info['rating']}", sfont, 14 * b, 4 * b)[0], y, f"★ {info['rating']}", sfont, (255, 204, 0, 40), border_color=(255, 204, 0, 200), text_color=(255, 215, 0, 255), pad_x=14 * b, pad_y=4 * b)
    
    y += 36 * b + 16 * b
    # Title
    y += draw_lines(layer, lines, tfont, x0 + pad, y) + 16 * b
    
    # Genre capsules
    cur_x = x0 + pad
    for g in info.get("genres", [])[:3]:
        gw, _ = draw_pill_badge(layer, cur_x, y, g, gfont, (255, 255, 255, 20), border_color=(255, 255, 255, 60), text_color=(240, 240, 245, 215), pad_x=14 * b, pad_y=4 * b)
        cur_x += gw + 10 * b


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


@fonts("cinzel", "poppins-sb", upper=True)
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


@fonts("orbitron", "rajdhani-b")
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


@fonts("bangers", "poppins-b", upper=True)
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


@fonts("righteous", "poppins-md")
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
    draw_rich(layer, x0 + 15 * b, y0 - tgh + (tgh - cap_h(sfont)) / 2, tag, sfont, (255, 255, 255, 255), shadow=False)

    y = y0 + pady
    step = line_step(tfont)
    for i, ln in enumerate(lines):
        draw_rich(layer, x0 + padx, y + i * step, ln, tfont, (12, 12, 14, 255), shadow=False)
    y += block_h(tfont, len(lines)) + 12 * b
    parts = [p for p in [info.get("year"), f"★ {info['rating']}" if info.get("rating") else None] + info.get("genres", [])[:2] if p]
    draw_rich(layer, x0 + padx, y, "  /  ".join(parts), mfont, (70, 70, 78, 255), shadow=False)


# ======================= 8 NEW DESIGNS (slots 8, 9, 10, 12, 14, 15, 16, 18) =======================

@fonts("anton", "rajdhani-b", upper=True)
def d_blade_slash(img, layer, info, b):
    """8. ⚔️ Blade Slash: dark diagonal panel cut by a glowing crimson blade edge"""
    W, H = img.size
    m = int(72 * b)
    top_x, bot_x = int(W * 0.64), int(W * 0.47)

    # --- diagonal dark panel (strong on the left, lighter near the blade) ---
    S = 2
    mask = Image.new("L", (W * S, H * S), 0)
    ImageDraw.Draw(mask).polygon([(0, 0), (top_x * S, 0), (bot_x * S, H * S), (0, H * S)], fill=255)
    mask = mask.resize((W, H), Image.LANCZOS)
    grad = Image.linear_gradient("L").transpose(Image.ROTATE_270).resize((W, H))
    grad = grad.point(lambda p: int(105 + (p / 255.0) * 75))
    panel = Image.new("RGBA", (W, H), (6, 4, 10, 255))
    panel.putalpha(ImageChops.multiply(grad, mask))
    img.alpha_composite(panel)
    add_smooth_gradient_bottom(img, H * 0.35, 120)

    # --- glowing blade edge ---
    def slash(offset, width, color, glow, alpha):
        t = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(t).line([(top_x + offset, -10), (bot_x + offset, H + 10)], fill=color[:3] + (alpha,), width=width)
        if glow:
            g = t.filter(ImageFilter.GaussianBlur(width * 1.6))
            img.alpha_composite(g)
            img.alpha_composite(g)
        img.alpha_composite(t)
    slash(0, max(4, int(9 * b)), (255, 30, 70), True, 255)
    slash(0, max(2, int(3 * b)), (255, 235, 240), False, 255)
    slash(int(30 * b), max(2, int(4 * b)), (255, 30, 70), True, 170)

    # --- text block ---
    tfont, lines = fit_lines(info["title"], 150 * b, 62 * b, W * 0.40, 3)
    sfont, mfont = load_font(27 * b), load_font(31 * b)
    th = block_h(tfont, len(lines))
    ph = pill_size("X", sfont, 18 * b, 6 * b)[1]
    bar_h, bar_w, skew = max(4, int(8 * b)), int(190 * b), int(16 * b)
    mh = text_h(mfont)
    total = ph + 20 * b + th + 20 * b + bar_h + 18 * b + mh
    y = H - m - total

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

    meta = []
    if info.get("rating"):
        meta.append(f"★ {info['rating']}")
    if info.get("genres"):
        meta.append("  •  ".join(info["genres"][:3]))
    draw_rich(layer, m, y, "   |   ".join(meta), mfont, (255, 232, 238, 240))


@fonts("audiowide", "rajdhani-b")
def d_synthwave_sunset(img, layer, info, b):
    """9. 🌆 Synthwave Sunset: striped retro sun + neon perspective grid + chrome gradient title"""
    W, H = img.size
    horizon = int(H * 0.80)
    cx = W // 2

    # dusk tint (transparent at top -> deep purple at horizon)
    gy0 = int(H * 0.28)
    gh = H - gy0
    g = Image.linear_gradient("L").resize((W, gh)).point(lambda p: int((p / 255.0) ** 1.15 * 215))
    dusk = Image.new("RGBA", (W, gh), (34, 4, 66, 255))
    dusk.putalpha(g)
    img.alpha_composite(dusk, dest=(0, gy0))

    # sun glow + sun
    R = int(H * 0.21)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - R * 1.35, horizon - R * 1.35, cx + R * 1.35, horizon + R * 1.35), fill=(255, 40, 150, 150))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(int(48 * b))))

    S = 2
    sm = Image.new("L", (2 * R * S, 2 * R * S), 0)
    ImageDraw.Draw(sm).ellipse((0, 0, 2 * R * S - 1, 2 * R * S - 1), fill=255)
    sd = ImageDraw.Draw(sm)
    for j in range(7):          # stripes get thicker towards the horizon
        yy = R * S - int(R * S * 0.62) + int(j * R * S * 0.088)
        th_ = int((2 + j * 1.7) * b * S)
        sd.rectangle((0, yy, 2 * R * S, yy + th_), fill=0)
    sm = sm.resize((2 * R, 2 * R), Image.LANCZOS)
    sun = Image.new("RGBA", (2 * R, 2 * R))
    col = Image.new("RGBA", (1, 2 * R))
    for yy in range(2 * R):
        col.putpixel((0, yy), multi_lerp([(0, (255, 232, 90, 255)), (0.5, (255, 95, 150, 255)), (1, (190, 40, 210, 255))], yy / (2 * R)) + ())
    sun = col.resize((2 * R, 2 * R))
    sun.putalpha(sm.point(lambda p: int(p * 0.95)))
    img.alpha_composite(sun, dest=(cx - R, horizon - R))

    # floor (dark) + neon grid
    fh = H - horizon
    floor = Image.new("RGBA", (W, fh), (14, 0, 34, 255))
    fa = Image.linear_gradient("L").resize((W, fh)).point(lambda p: int(215 + p * 0.1))
    floor.putalpha(fa)
    img.alpha_composite(floor, dest=(0, horizon))

    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    lw = max(2, int(3 * b))
    for i in range(-14, 15):
        gd.line([(cx, horizon), (cx + i * W * 0.13, H)], fill=(255, 50, 200, 210), width=lw)
    for k in range(1, 9):
        yy = horizon + fh * ((k / 9.0) ** 2)
        gd.line([(0, yy), (W, yy)], fill=(255, 50, 200, 210), width=lw)
    # grid sirusa irukka - horizon-ku close-la fade
    fade = Image.linear_gradient("L").resize((W, fh)).point(lambda p: int(60 + p * 0.75))
    fade_full = Image.new("L", (W, H), 0)
    fade_full.paste(fade, (0, horizon))
    grid.putalpha(ImageChops.multiply(grid.split()[3], fade_full))
    img.alpha_composite(grid.filter(ImageFilter.GaussianBlur(int(5 * b))))
    img.alpha_composite(grid)
    hl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(hl).line([(0, horizon), (W, horizon)], fill=(0, 238, 255, 255), width=max(2, int(4 * b)))
    img.alpha_composite(hl.filter(ImageFilter.GaussianBlur(int(7 * b))))
    img.alpha_composite(hl)

    # --- text (centered above the horizon) ---
    tfont, lines = fit_lines(info["title"], 150 * b, 56 * b, W * 0.82, 2)
    sfont, gfont = load_font(29 * b), load_font(32 * b)
    step = line_step(tfont)
    cap = cap_h(tfont)
    th = block_h(tfont, len(lines))
    ph = pill_size("X", sfont, 16 * b, 6 * b)[1]
    gh_ = text_h(gfont)

    y_gen = horizon - int(26 * b) - gh_
    y_title = y_gen - int(18 * b) - th
    y_pills = y_title - int(20 * b) - ph

    tags = []
    if info.get("type"):
        tags.append((info["type"].upper(), (255, 0, 150, 70), (255, 60, 190, 255), (255, 215, 245, 255)))
    if info.get("year"):
        tags.append((info["year"], (0, 0, 0, 120), (0, 238, 255, 230), (200, 250, 255, 255)))
    if info.get("rating"):
        tags.append((f"★ {info['rating']}", (255, 204, 0, 40), (255, 204, 0, 240), (255, 220, 60, 255)))
    pill_row_center(layer, W, y_pills, tags, sfont, 16 * b, 6 * b, 12 * b)

    stops = [(0, (225, 250, 255)), (0.48, (255, 255, 255)), (0.52, (255, 190, 235)), (1, (255, 60, 170))]
    for i, ln in enumerate(lines):
        tw = _PROBE.textlength(ln, font=tfont)
        gradient_text(layer, (W - tw) / 2, y_title + i * step + cap, ln, tfont, stops,
                      stroke=max(3, int(5 * b)), stroke_fill=(38, 0, 70, 255))

    if info.get("genres"):
        gtxt = "  •  ".join(info["genres"][:3]).upper()
        gw = text_w(gtxt, gfont)
        draw_rich(layer, (W - gw) / 2, y_gen, gtxt, gfont, (120, 240, 255, 255))


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


@fonts("righteous", "rajdhani-b")
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


@fonts("cinzel", "poppins-md", upper=True)
def d_letterbox(img, layer, info, b):
    """15. 🎥 Letterbox Cinema: black widescreen bars + gold hairlines + elegant serif title in the bottom bar"""
    W, H = img.size
    gold = (212, 175, 95, 255)
    top_h = int(H * 0.075)

    tfont, lines = fit_lines(info["title"], 80 * b, 38 * b, W * 0.80, 2)
    mfont = load_font(27 * b)
    th = block_h(tfont, len(lines))
    pad_t, pad_b = int(30 * b), int(34 * b)
    bot_h = max(int(H * 0.22), int(pad_t + th + 18 * b + text_h(mfont) + pad_b))

    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, top_h), fill=(0, 0, 0, 255))
    d.rectangle((0, H - bot_h, W, H), fill=(0, 0, 0, 255))
    hl = max(2, int(2.5 * b))
    d.rectangle((0, top_h, W, top_h + hl), fill=gold)
    d.rectangle((0, H - bot_h - hl, W, H - bot_h), fill=gold)

    # top bar label
    lfont = load_font(21 * b, family="poppins-md")
    parts = [p for p in [(info.get("type") or "").upper(), info.get("year") or ""] if p]
    label = "   •   ".join(parts)
    if label:
        sp = 4 * b
        lw = spaced_width(label, lfont, sp)
        draw_spaced(layer, (W - lw) / 2, (top_h - cap_h(lfont)) / 2, label, lfont, sp, gold)

    # title + meta in bottom bar
    y = H - bot_h + pad_t
    y += draw_lines(layer, lines, tfont, 0, y, fill=(250, 242, 225, 255), align="center", box_w=W) + 18 * b
    meta = []
    if info.get("rating"):
        meta.append(f"★ {info['rating']}")
    if info.get("genres"):
        meta.append("  •  ".join(info["genres"][:3]))
    mt = "     |     ".join(meta)
    if mt:
        mw = text_w(mt, mfont)
        draw_rich(layer, (W - mw) / 2, y, mt, mfont, (222, 196, 140, 255), shadow=False)


@fonts("bangers", "poppins-xb", upper=True)
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


@fonts("poppins-md", "poppins-sb")
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



# ======================= DESIGNS REGISTRY =======================
# Slot numbers (1-18) maaralai - so users-oda saved style selection break aagaadhu.
# 8, 9, 10, 12, 14, 15, 16, 18 -> pudhu "super" designs.

DESIGNS = {
    1: ("🌟 Cyber Glow", d_cyber_neon),
    2: ("🎬 Cinematic Prime", d_cinematic_prime),
    3: ("💎 Vision Glass", d_vision_glass),
    4: ("🎌 Tokyo Action", d_tokyo_action),
    5: ("🌌 Aurora Horizon", d_aurora_horizon),
    6: ("🏆 Royale Gold", d_royale_gold),
    7: ("🔥 Cyber Logo", d_cyber_logo),
    8: ("⚔️ Blade Slash", d_blade_slash),
    9: ("🌆 Synthwave Sunset", d_synthwave_sunset),
    10: ("🫧 Liquid Glass", d_liquid_glass),
    11: ("⚡ Comic Pop", d_comic_pop),
    12: ("🌃 Neon Tokyo", d_neon_tokyo),
    13: ("🌸 Sakura Dream", d_sakura_dream),
    14: ("🏅 Mega Score", d_mega_score),
    15: ("🎥 Letterbox Cinema", d_letterbox),
    16: ("🍭 Sticker Pop", d_sticker_pop),
    17: ("📖 Manga Panel", d_manga_panel),
    18: ("🤍 Clean Minimal", d_clean_minimal),
}

def design_name(st):
    return DESIGNS[st][0] if st in DESIGNS else "Plain (Watermark only)"
