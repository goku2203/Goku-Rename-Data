import asyncio
import aiohttp
import io
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

WAITING = {}          # user_id -> watermark name ku wait panra state
IMG_CACHE = {}        # image bytes cache (Size +/- fast aaga)
BACKDROP_CACHE = {}   # tmdb backdrops list cache

# Bold font venumna bot folder la "font.ttf" nu oru font file podunga (Poppins-Bold etc.)
FONT_PATHS = [
    "font.ttf",
    "Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "arialbd.ttf",
]


# ======================= HELPERS =======================

def load_font(size):
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


def telegram_icon(d):
    """Telegram blue circle + white paper plane (smooth aaga draw panna 4x la vera panni resize)"""
    S = 4
    big = d * S
    icon = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    dr = ImageDraw.Draw(icon)
    dr.ellipse([0, 0, big - 1, big - 1], fill=(36, 161, 222, 255))
    k = big / 100
    plane = [(22, 48), (77, 26), (66, 74), (50, 62), (43, 71), (40, 57)]
    dr.polygon([(x * k, y * k) for x, y in plane], fill=(255, 255, 255, 255))
    dr.line([(40 * k, 57 * k), (64 * k, 38 * k)], fill=(36, 161, 222, 255), width=max(1, int(2 * k)))
    return icon.resize((d, d), Image.LANCZOS)


def build_poster(img_bytes, text, scale, out_path):
    """Glass pill watermark (top right) - Telegram logo + white text"""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

    base = img.width / 1920            # image size ku yetha maathiri auto adjust
    unit = base * scale                # user set pannina size
    margin = int(40 * base)

    font = load_font(max(10, int(34 * unit)))
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = probe.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    h = max(24, int(64 * unit))
    icon_d = int(h * 0.62)
    pad_l = (h - icon_d) // 2
    gap = int(14 * unit)
    pad_r = int(h * 0.45)
    w = pad_l + icon_d + gap + tw + pad_r

    x0 = max(0, img.width - w - margin)
    y0 = margin
    box = (x0, y0, x0 + w, y0 + h)

    # 1. Glass: background crop -> blur -> dark tint -> pill shape la paste
    # Frosted glass: konjam periya area crop panni blur panrom (edge la black varaama irukka)
    pad = int(24 * unit)
    bx0, by0 = max(0, x0 - pad), max(0, y0 - pad)
    bx1, by1 = min(img.width, x0 + w + pad), min(img.height, y0 + h + pad)
    region = img.crop((bx0, by0, bx1, by1)).filter(ImageFilter.GaussianBlur(max(4, int(18 * unit))))
    region = region.crop((x0 - bx0, y0 - by0, x0 - bx0 + w, y0 - by0 + h))
    # Black illa - light white frosted tint (GLASS_WHITE kootina innum white aagum, kuraichaa clear aagum)
    region = Image.alpha_composite(region, Image.new("RGBA", region.size, (0, 0, 0, 22)))
    region = Image.alpha_composite(region, Image.new("RGBA", region.size, (255, 255, 255, GLASS_WHITE)))

    m = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 4 - 1, h * 4 - 1), radius=h * 2, fill=255)
    mask = m.resize((w, h), Image.LANCZOS)
    img.paste(region, (x0, y0), mask)

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))

    # 2. Glass edge (thin white border)
    bl = Image.new("RGBA", (w * 4, h * 4), (0, 0, 0, 0))
    ImageDraw.Draw(bl).rounded_rectangle(
        (0, 0, w * 4 - 1, h * 4 - 1), radius=h * 2,
        outline=(255, 255, 255, 140), width=max(4, int(6 * unit))
    )
    layer.alpha_composite(bl.resize((w, h), Image.LANCZOS), dest=(x0, y0))

    # 3. Telegram logo
    layer.alpha_composite(telegram_icon(icon_d), dest=(x0 + pad_l, y0 + (h - icon_d) // 2))

    # 4. White text
    tx = x0 + pad_l + icon_d + gap - bbox[0]
    ty = y0 + (h - th) // 2 - bbox[1]
    # Soft shadow - bright background la kooda text clear aa theriyum
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((tx - x0, ty - y0 + max(1, int(2 * unit))), text, font=font, fill=(0, 0, 0, 120))
    sh = sh.filter(ImageFilter.GaussianBlur(max(1, int(3 * unit))))
    layer.alpha_composite(sh, dest=(x0, y0))

    ImageDraw.Draw(layer).text((tx, ty), text, font=font, fill=(255, 255, 255, 255))

    final = Image.alpha_composite(img, layer).convert("RGB")
    final.save(out_path, format="JPEG", quality=90)


async def render(user_id, tmdb_id, media_type, idx):
    backdrops = await get_backdrops(media_type, tmdb_id)
    if not backdrops:
        return None
    idx = idx % len(backdrops)  # Next/Back loop aagum
    img_bytes = await get_bytes(f"https://image.tmdb.org/t/p/original{backdrops[idx]}")
    text = await get_wm_text(user_id)
    scale = await get_scale(user_id)
    out_path = f"poster_{user_id}_{int(time.time() * 1000)}.jpg"
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, build_poster, img_bytes, text, scale, out_path)  # bot hang aagaama
    return out_path, idx, len(backdrops), text, scale


# ======================= BUTTONS / CAPTIONS =======================

def main_markup(tmdb_id, mt, idx, total):
    rows = []
    if total > 1:
        rows.append([
            InlineKeyboardButton("⬅️ Back", callback_data=f"show_img|{tmdb_id}|{mt}|{idx - 1}"),
            InlineKeyboardButton(f"{idx + 1}/{total}", callback_data="ignore"),
            InlineKeyboardButton("Next ➡️", callback_data=f"show_img|{tmdb_id}|{mt}|{idx + 1}"),
        ])
    rows.append([InlineKeyboardButton("🎨 Custom Style", callback_data=f"cstyle|{tmdb_id}|{mt}|{idx}")])
    rows.append([InlineKeyboardButton("🗑 Delete Now", callback_data="delete_auto")])
    return InlineKeyboardMarkup(rows)


def style_markup(tmdb_id, mt, idx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Set My Watermark", callback_data=f"wmset|{tmdb_id}|{mt}|{idx}")],
        [
            InlineKeyboardButton("➖ Size", callback_data=f"wmsize|{tmdb_id}|{mt}|{idx}|m"),
            InlineKeyboardButton("➕ Size", callback_data=f"wmsize|{tmdb_id}|{mt}|{idx}|p"),
        ],
        [InlineKeyboardButton("⬅️ Back to Poster", callback_data=f"show_img|{tmdb_id}|{mt}|{idx}")],
        [InlineKeyboardButton("🗑 Delete Now", callback_data="delete_auto")],
    ])


def main_caption(idx):
    return (f"Landscape Image {idx + 1} 🌅\n\n"
            f"*(This message will auto-delete in {AUTO_DELETE_SECONDS // 60} minutes)*")


def style_caption(text, scale):
    return (f"**🎨 CUSTOM STYLE**\n"
            f"__Watermark & size - ore thadava set pannina permanent a save aagum__\n\n"
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
                btn_text, callback_data=f"show_img|{res.get('id')}|{media_type}|0"
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

    _, tmdb_id, media_type, idx = query.data.split("|")[:4]
    user_id = query.from_user.id

    if not query.message.photo:
        await query.message.edit_text("`Processing Glass Watermark...`")

    try:
        res = await render(user_id, tmdb_id, media_type, int(idx))
        if not res:
            return await query.message.edit("**Intha anime kku landscape image kidaikkala bro!**")
        path, idx, total, _, _ = res
        await deliver(client, query, path, main_caption(idx), main_markup(tmdb_id, media_type, idx, total))
    except Exception as e:
        try:
            await query.message.edit(f"**Error:** `{e}`")
        except Exception:
            pass


# ======================= CUSTOM STYLE PANEL =======================

@Client.on_callback_query(filters.regex(r"^cstyle\|"), group=1)
async def custom_style_cb(client, query: CallbackQuery):
    try:
        await query.answer()
    except Exception:
        pass

    _, tmdb_id, media_type, idx = query.data.split("|")[:4]
    try:
        res = await render(query.from_user.id, tmdb_id, media_type, int(idx))
        if not res:
            return
        path, idx, total, text, scale = res
        await deliver(client, query, path, style_caption(text, scale), style_markup(tmdb_id, media_type, idx))
    except Exception as e:
        try:
            await query.message.edit_caption(f"**Error:** `{e}`")
        except Exception:
            pass


# --- Size + / - (ore thadava set pannina permanent) ---
@Client.on_callback_query(filters.regex(r"^wmsize\|"), group=1)
async def wm_size_cb(client, query: CallbackQuery):
    _, tmdb_id, media_type, idx, op = query.data.split("|")[:5]
    user_id = query.from_user.id

    scale = await get_scale(user_id)
    new_scale = round(scale + SCALE_STEP, 1) if op == "p" else round(scale - SCALE_STEP, 1)
    new_scale = min(SCALE_MAX, max(SCALE_MIN, new_scale))

    if new_scale == scale:
        return await query.answer("Idhukku mela/keela pogaadhu bro!", show_alert=True)

    await query.answer(f"Size: {new_scale}x ✅")
    await digital_botz.set_wm_scale(user_id, new_scale)   # DB la permanent save

    try:
        res = await render(user_id, tmdb_id, media_type, int(idx))
        if not res:
            return
        path, idx, total, text, scale = res
        await deliver(client, query, path, style_caption(text, scale), style_markup(tmdb_id, media_type, idx))
    except Exception as e:
        try:
            await query.message.edit_caption(f"**Error:** `{e}`")
        except Exception:
            pass


# --- Set My Watermark button ---
@Client.on_callback_query(filters.regex(r"^wmset\|"), group=1)
async def wm_set_cb(client, query: CallbackQuery):
    _, tmdb_id, media_type, idx = query.data.split("|")[:4]
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
        "idx": int(idx),
    }

    async def timeout():
        await asyncio.sleep(60)
        st = WAITING.get(user_id)
        if st and st["prompt_id"] == prompt.id:
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
            res = await render(user_id, st["tmdb_id"], st["media_type"], st["idx"])
            if res:
                path, idx, total, text, scale = res
                try:
                    await client.edit_message_media(
                        chat_id=st["chat_id"],
                        message_id=st["photo_id"],
                        media=InputMediaPhoto(path, caption=style_caption(text, scale)),
                        reply_markup=style_markup(st["tmdb_id"], st["media_type"], idx)
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
