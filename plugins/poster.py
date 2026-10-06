import asyncio
import aiohttp
import io
import os
import time
from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, InputMediaPhoto
from PIL import Image
from helper.database import digital_botz

# Import designs and helpers from our new file
from thumbnail_designs import (
    DESIGNS, design_name, load_font, _PROBE,
    glass_panel, paste_rgba, telegram_icon, text_shadow
)

# Enter your TMDB API Key here
TMDB_API_KEY = "f0ed821364e340369110e83b814899ed"

DEFAULT_WM = "@Techgokul"      # Default watermark if user hasn't set one
SCALE_MIN = 0.4
SCALE_MAX = 3.0
SCALE_STEP = 0.2
AUTO_DELETE_SECONDS = 120      # Auto delete time for poster message

WAITING = {}          # State to wait for user's watermark name
IMG_CACHE = {}        # Image bytes cache for faster loading
BACKDROP_CACHE = {}   # Cache for TMDB backdrops list
INFO_CACHE = {}       # Cache for title, year, and rating


# ======================= BASIC HELPERS =======================

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
    """Required info for designs: Title, year, rating, genres"""
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


# ======================= WATERMARK =======================

def draw_watermark(img, layer, text, scale):
    """Top right frosted glass pill + Telegram logo + white text"""
    b = img.width / 1920            # Auto adjust based on image size
    unit = b * scale                # User defined size
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
    idx = idx % len(backdrops)  # Loops for Next/Back buttons
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
            f"__Select a design. Watermark & size will be saved permanently.__\n\n"
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
    """Updates media if photo exists, else deletes text and sends new photo"""
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
            asyncio.create_task(auto_delete(sent))  # Starts only for the first time
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
        return await message.reply_text("**__Please provide a Custom Name__\n\nEx :- `/set_watermark @Techgokul`**")

    watermark_name = message.text.split(" ", 1)[1]
    await digital_botz.set_watermark(message.from_user.id, watermark_name)
    await message.reply_text(f"**Watermark Name saved successfully:** `{watermark_name}`")


# --- Step 1: Search Anime and Show List ---
@Client.on_message(filters.private & filters.command(['poster', 'p']))
async def poster_cmd(client, message):
    if len(message.command) == 1:
        return await message.reply_text("**__Please provide Anime Name__\n\nEx :- `/p Naruto`**")

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
            if len(buttons) == 5:   # Show Top 5 only
                break

        if not buttons:
            return await process_msg.edit("**Anime not found! Please check the spelling.**")

        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="close_search")])
        await process_msg.edit(
            f"**Search Results for:** `{query}`\n\nSelect one from the list below:",
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
            return await query.message.edit("**No landscape image found for this anime!**")
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


# --- Size + / - (Permanent save on update) ---
@Client.on_callback_query(filters.regex(r"^wmsize\|"), group=1)
async def wm_size_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx, st, op = parts[1], parts[2], int(parts[3]), parse_st(parts, 4), parts[5]
    user_id = query.from_user.id

    scale = await get_scale(user_id)
    new_scale = round(scale + SCALE_STEP, 1) if op == "p" else round(scale - SCALE_STEP, 1)
    new_scale = min(SCALE_MAX, max(SCALE_MIN, new_scale))

    if new_scale == scale:
        return await query.answer("Size limit reached!", show_alert=True)

    await query.answer(f"Size: {new_scale}x ✅")
    await digital_botz.set_wm_scale(user_id, new_scale)   # Permanent save in DB

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
        "**✏️ Send your Watermark Name**\n\nEx :- `@Techgokul`\n\n__(Send within 60 seconds)__",
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

        # Refreshes poster with the new watermark
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
    message.stop_propagation()   # Stops message from going to other handlers (like auto rename)


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
