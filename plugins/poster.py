import asyncio
import aiohttp
import io
import os
import time
import textwrap
from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, InputMediaPhoto
from PIL import Image, ImageDraw, ImageFilter, ImageOps
from helper.database import goku_stark

# Import designs and helpers from thumbnail_designs.py
try:
    from plugins.thumbnail_designs import (
        DESIGNS, design_name, load_font, _PROBE,
        glass_panel, paste_rgba, telegram_icon, text_shadow, rounded_mask
    )
except ImportError:
    from thumbnail_designs import (
        DESIGNS, design_name, load_font, _PROBE,
        glass_panel, paste_rgba, telegram_icon, text_shadow, rounded_mask
    )

# Enter your TMDB API Key here
TMDB_API_KEY = ""

DEFAULT_WM = "@Techgokul"      # Default watermark if user hasn't set one
SCALE_MIN = 0.4
SCALE_MAX = 3.0
SCALE_STEP = 0.2
AUTO_DELETE_SECONDS = 3600      # Auto delete time for poster message (1 Hours)

# Dynamic text calculate panra logic
if AUTO_DELETE_SECONDS >= 3600:
    AUTO_DELETE_TEXT = f"{AUTO_DELETE_SECONDS // 3600} hours"
else:
    AUTO_DELETE_TEXT = f"{AUTO_DELETE_SECONDS // 60} minutes"

WAITING = {}          # State to wait for user's watermark name (inline & menu)
IMG_CACHE = {}        # Image bytes cache for faster loading
BACKDROP_CACHE = {}   # Cache for TMDB backdrops list
INFO_CACHE = {}       # Cache for title, year, rating, genres
LOGO_CACHE = {}       # Cache for TMDB title logos
SEARCH_CACHE = {}     # Cache for user search query


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
    if len(IMG_CACHE) >= 15:
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

async def get_logo(media_type, tmdb_id, size="w500"):
    """Fetches transparent PNG title logo from TMDB images"""
    key = f"{media_type}_{tmdb_id}_{size}"
    if key in LOGO_CACHE:
        return LOGO_CACHE[key]
    try:
        data = await get_json(
            f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/images",
            params={"api_key": TMDB_API_KEY},
        )
        logos = data.get("logos", [])
        if logos:
            en_logos = [l["file_path"] for l in logos if l.get("iso_639_1") == "en"]
            path = en_logos[0] if en_logos else (logos[0]["file_path"] if logos else None)
            if path:
                bytes_data = await get_bytes(f"https://image.tmdb.org/t/p/{size}{path}")
                if len(LOGO_CACHE) >= 30:
                    LOGO_CACHE.pop(next(iter(LOGO_CACHE)))
                LOGO_CACHE[key] = bytes_data
                return bytes_data
    except Exception:
        pass
    return None

async def get_info(media_type, tmdb_id):
    """Required info for designs: Title, year, rating, genres, type"""
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
            "year": date[:4] if date else "",
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
        s = await goku_stark.get_wm_scale(user_id)
        s = float(s) if s else 1.0
    except Exception:
        s = 1.0
    return min(SCALE_MAX, max(SCALE_MIN, s))

async def get_wm_text(user_id):
    try:
        t = await goku_stark.get_watermark(user_id)
    except Exception:
        t = None
    return t or DEFAULT_WM


# ======================= WATERMARK RENDERING =======================

def draw_watermark(img, layer, text, scale):
    """
    Top right frosted glass capsule pill + Telegram icon + bold white text.
    Dark translucent acrylic pill backing guarantees 100% crisp visibility
    even on pure white/bright backgrounds as requested (matching sample badge).
    """
    b = img.width / 1920            # Auto adjust based on image width
    unit = b * scale                # User defined scale
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
    radius = h // 2

    # 1. Background blur under pill
    blur = 16 * unit
    pad_blur = int(blur * 2)
    bx0, by0 = max(0, x0 - pad_blur), max(0, y0 - pad_blur)
    bx1, by1 = min(img.width, x0 + w + pad_blur), min(img.height, y0 + h + pad_blur)
    region = img.crop((bx0, by0, bx1, by1)).filter(ImageFilter.GaussianBlur(blur))
    region = region.crop((x0 - bx0, y0 - by0, x0 - bx0 + w, y0 - by0 + h))

    # 2. Pure Frosted Glass Overlay (Transparent Effect)
    glass_overlay = Image.new("RGBA", region.size, (255, 255, 255, 40))
    region = Image.alpha_composite(region, glass_overlay)
    img.paste(region, (x0, y0), rounded_mask(w, h, radius))

    # 3. Outer delicate glass shine border
    S = 3
    bl = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    bw = max(1, int(1.8 * unit))
    ImageDraw.Draw(bl).rounded_rectangle(
        (0, 0, w * S - 1, h * S - 1), radius=radius * S,
        outline=(255, 255, 255, 75), width=bw * S
    )
    paste_rgba(layer, bl.resize((w, h), Image.LANCZOS), x0, y0)

    # 4. Telegram icon
    paste_rgba(layer, telegram_icon(icon_d), x0 + pad_l, y0 + (h - icon_d) // 2)

    # 5. Bold text with glass effect (translucent white + soft shadow)
    tx = x0 + pad_l + icon_d + gap - bbox[0]
    ty = y0 + (h - th) // 2 - bbox[1]
    text_shadow(layer, (tx, ty), text, font, fill=(255, 255, 255, 255), shadow_color=(0, 0, 0, 200))

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
    idx = idx % len(backdrops)
    img_bytes = await get_bytes(f"https://image.tmdb.org/t/p/original{backdrops[idx]}")
    text = await get_wm_text(user_id)
    scale = await get_scale(user_id)
    info = await get_info(media_type, tmdb_id)
    
    # If title logo design is chosen (Design 7), fetch TMDB logo bytes
    if (st == 7) and info and not info.get("logo_bytes"):
        logo_bytes = await get_logo(media_type, tmdb_id)
        if logo_bytes:
            info["logo_bytes"] = logo_bytes

    out_path = f"poster_{user_id}_{int(time.time() * 1000)}.jpg"
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, build_poster, img_bytes, text, scale, out_path, st, info)
    return out_path, idx, len(backdrops), text, scale, info


# ======================= BUTTONS & CAPTIONS =======================

# 1. Raw Landscape Browser View (Zero rendering, instant load)
def raw_markup(tmdb_id, mt, idx, total):
    rows = []
    if total > 1:
        rows.append([
            InlineKeyboardButton("◀️ Prev", callback_data=f"show_raw|{tmdb_id}|{mt}|{idx - 1}"),
            InlineKeyboardButton(f"{idx + 1}/{total}", callback_data="ignore"),
            InlineKeyboardButton("Next ▶️", callback_data=f"show_raw|{tmdb_id}|{mt}|{idx + 1}"),
        ])
    rows.append([
        InlineKeyboardButton("⚡ Generate Image", callback_data=f"gen_normal|{tmdb_id}|{mt}|{idx}"),
        InlineKeyboardButton("🎨 Custom Style", callback_data=f"cstyle|{tmdb_id}|{mt}|{idx}|1")
    ])
    rows.append([
        InlineKeyboardButton("🏷 Custom Logo", callback_data=f"clpos|{tmdb_id}|{mt}|{idx}|b")
    ])
    rows.append([
        InlineKeyboardButton("🔙 Back", callback_data=f"back_search|{tmdb_id}|{mt}"),
        InlineKeyboardButton("🗑 Delete", callback_data="delete_auto")
    ])
    return InlineKeyboardMarkup(rows)

def raw_caption(idx, total, info):
    title = info.get("title") or "Unknown"
    year = info.get("year", "")
    rating = info.get("rating", "")
    genres = " • ".join(info.get("genres", []))
    meta = []
    if info.get("type"):
        meta.append(info["type"])
    if year:
        meta.append(year)
    if rating:
        meta.append(f"★ {rating}")
    meta_str = "  |  ".join(meta) if meta else ""

    caption = (
        f"🌅 **Landscape Backdrop** • `{idx + 1}/{total}`\n"
        f"🎬 **Title:** `{title}`\n"
    )
    if meta_str:
        caption += f"ℹ️ {meta_str}\n"
    if genres:
        caption += f"🎭 **Genres:** `{genres}`\n"
    caption += (
        f"\n👉 **Choose an option below:**\n"
        f"• **⚡ Generate Image:** Normal poster with glass watermark\n"
        f"• **🎨 Custom Style:** 12 aesthetic thumbnail templates\n"
        f"• **🏷 Custom Logo:** Title logo (top / bottom / bottom-left) + your own photo\n\n"
        f"*(Auto-deletes in {AUTO_DELETE_TEXT})*"
    )
    return caption

# 2. Normal Generated Poster View (Watermark only)
def normal_poster_markup(tmdb_id, mt, idx, total):
    rows = []
    if total > 1:
        rows.append([
            InlineKeyboardButton("◀️ Prev", callback_data=f"gen_normal|{tmdb_id}|{mt}|{idx - 1}"),
            InlineKeyboardButton(f"{idx + 1}/{total}", callback_data="ignore"),
            InlineKeyboardButton("Next ▶️", callback_data=f"gen_normal|{tmdb_id}|{mt}|{idx + 1}"),
        ])
    rows.append([
        InlineKeyboardButton("🎨 Custom Style", callback_data=f"cstyle|{tmdb_id}|{mt}|{idx}|1"),
        InlineKeyboardButton("🖼 Browse Raw", callback_data=f"show_raw|{tmdb_id}|{mt}|{idx}")
    ])
    rows.append([
        InlineKeyboardButton("🔙 Back", callback_data=f"back_search|{tmdb_id}|{mt}"),
        InlineKeyboardButton("🗑 Delete Now", callback_data="delete_auto")
    ])
    return InlineKeyboardMarkup(rows)

def normal_poster_caption(idx, total, text, scale, info):
    title = info.get("title") or "Poster"
    return (
        f"✨ **Poster Generated** • `{idx + 1}/{total}`\n"
        f"🎬 **Title:** `{title}`\n"
        f"🏷 **Watermark:** `{text}` | 📏 **Size:** `{scale}x`\n\n"
        f"*(Auto-deletes in {AUTO_DELETE_TEXT})*"
    )

# 3. Custom Style Panel View (18 Designs, Clean, and Back)
def style_markup(tmdb_id, mt, idx, st):
    def dbtn(n):
        name = DESIGNS[n][0]
        return InlineKeyboardButton(f"✅ {name}" if st == n else name,
                                    callback_data=f"dsgn|{tmdb_id}|{mt}|{idx}|{n}")
    return InlineKeyboardMarkup([
        [dbtn(1), dbtn(2)],
        [dbtn(3), dbtn(4)],
        [dbtn(5), dbtn(6)],
        [dbtn(7), dbtn(8)],
        [dbtn(9), dbtn(10)],
        [dbtn(11), dbtn(12)],
        [dbtn(13), dbtn(14)],
        [dbtn(15), dbtn(16)],
        [dbtn(17), dbtn(18)],
        [
            InlineKeyboardButton("✅ 🧹 Clean" if st == 0 else "🧹 Clean", callback_data=f"dsgn|{tmdb_id}|{mt}|{idx}|0"),
            InlineKeyboardButton("🔙 Back", callback_data=f"show_raw|{tmdb_id}|{mt}|{idx}"),
        ],
        [InlineKeyboardButton("🗑 Delete Now", callback_data="delete_auto")],
    ])

def style_caption(text, scale, st, info=None):
    title = (info.get("title") if info else "") or ""
    tag = f"🎬 **Title:** `{title}`\n" if title else ""
    return (
        f"**🎨 CUSTOM STYLE STUDIO**\n"
        f"{tag}"
        f"🖼 **Design:** `{design_name(st)}`\n"
        f"🏷 **Watermark:** `{text}` | 📏 **Size:** `{scale}x`\n\n"
        f"__Select a design above. Use /set_watermark to adjust your watermark text & size.__\n\n"
        f"*(Auto-deletes in {AUTO_DELETE_TEXT})*"
    )

# 4. Standalone /set_watermark Menu
def wm_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Add / Change Name", callback_data="wm_menu_name")],
        [
            InlineKeyboardButton("➖ Size (0.2x)", callback_data="wm_menu_scale|m"),
            InlineKeyboardButton("➕ Size (0.2x)", callback_data="wm_menu_scale|p"),
        ],
        [
            InlineKeyboardButton("🔄 Reset to Default", callback_data="wm_menu_reset"),
            InlineKeyboardButton("❌ Close", callback_data="wm_menu_close")
        ]
    ])

async def wm_menu_text(user_id, status_alert=None):
    text = await get_wm_text(user_id)
    scale = await get_scale(user_id)
    msg = (
        f"🏷 **Watermark & Branding Settings**\n\n"
        f"Manage your personal watermark text and size below.\n"
        f"All changes are **permanently saved** in the database and applied to all your posters automatically!\n\n"
        f"• 🏷 **Current Watermark:** `{text}`\n"
        f"• 📏 **Current Scale:** `{scale}x`\n"
    )
    if status_alert:
        msg += f"\n{status_alert}\n"
    msg += "\n*Select an action below:*"
    return msg

async def get_cmd_id(client, chat_id, msg_id):
    """ID of the user's original /p command that this bot message is replying to."""
    try:
        full = await client.get_messages(chat_id, msg_id)
    except Exception:
        return None
    if not full:
        return None
    rid = getattr(full, "reply_to_message_id", None)
    if not rid and getattr(full, "reply_to_message", None):
        rid = full.reply_to_message.id
    return rid or None

async def delete_cmd(client, chat_id, msg_id):
    """Deletes the user's /p command message linked to the given bot message."""
    rid = await get_cmd_id(client, chat_id, msg_id)
    if rid:
        try:
            await client.delete_messages(chat_id, rid)
        except Exception:
            pass

async def auto_delete(client, msg, cmd_id=None):
    await asyncio.sleep(AUTO_DELETE_SECONDS)
    chat_id = msg.chat.id
    if not cmd_id:
        cmd_id = getattr(msg, "reply_to_message_id", None)
    try:
        # 1. User anupina original command (/p name) ah first delete pannum
        if cmd_id:
            await client.delete_messages(chat_id, cmd_id)
    except Exception:
        pass
    try:
        # 2. Bot anupina poster ah delete pannum
        await msg.delete()
    except Exception:
        pass

async def deliver(client, query, media_source, caption, markup):
    """
    Updates media if photo message exists, else deletes text message and sends photo.
    media_source can be a local file path or a URL.
    Cleans up local temporary files automatically.
    """
    is_url = isinstance(media_source, str) and (media_source.startswith("http://") or media_source.startswith("https://"))
    local_file_to_clean = media_source if (not is_url and os.path.exists(media_source)) else None

    # Force fetch full message to safely get reply_to_message link
    reply_id = await get_cmd_id(client, query.message.chat.id, query.message.id)

    try:
        if query.message.photo:
            try:
                await query.message.edit_media(
                    media=InputMediaPhoto(media_source, caption=caption),
                    reply_markup=markup
                )
            except MessageNotModified:
                pass
            except Exception:
                # If editing with URL failed, download bytes and edit with file
                if is_url:
                    bytes_data = await get_bytes(media_source)
                    tmp_path = f"tmp_raw_{query.from_user.id}_{int(time.time() * 1000)}.jpg"
                    with open(tmp_path, "wb") as f:
                        f.write(bytes_data)
                    local_file_to_clean = tmp_path
                    try:
                        await query.message.edit_media(
                            media=InputMediaPhoto(tmp_path, caption=caption),
                            reply_markup=markup
                        )
                    except MessageNotModified:
                        pass
        else:
            await query.message.delete()
            try:
                sent = await client.send_photo(
                    chat_id=query.message.chat.id,
                    photo=media_source,
                    caption=caption,
                    reply_markup=markup,
                    reply_to_message_id=reply_id
                )
            except Exception:
                if is_url:
                    bytes_data = await get_bytes(media_source)
                    tmp_path = f"tmp_raw_{query.from_user.id}_{int(time.time() * 1000)}.jpg"
                    with open(tmp_path, "wb") as f:
                        f.write(bytes_data)
                    local_file_to_clean = tmp_path
                    sent = await client.send_photo(
                        chat_id=query.message.chat.id,
                        photo=tmp_path,
                        caption=caption,
                        reply_markup=markup,
                        reply_to_message_id=reply_id
                    )
            if sent:
                asyncio.create_task(auto_delete(client, sent, reply_id))
    finally:
        if local_file_to_clean and os.path.exists(local_file_to_clean):
            try:
                os.remove(local_file_to_clean)
            except Exception:
                pass

def parse_st(parts, pos):
    try:
        st = int(parts[pos])
    except Exception:
        st = 0
    return st if st in DESIGNS or st == 0 else 0


# ======================= COMMAND HANDLERS =======================

# --- /set_watermark Command ---
@Client.on_message(filters.private & filters.command(['set_watermark']))
async def set_watermark_cmd(client, message):
    user_id = message.from_user.id
    if len(message.command) > 1:
        watermark_name = message.text.split(" ", 1)[1].strip()[:30]
        await goku_stark.set_watermark(user_id, watermark_name)
        text = await wm_menu_text(user_id, status_alert=f"✅ Watermark Name saved: `{watermark_name}`")
        return await message.reply_text(text, reply_markup=wm_menu_markup())

    text = await wm_menu_text(user_id)
    await message.reply_text(text, reply_markup=wm_menu_markup())


# --- /p or /poster Command (Search Anime & Movies) ---
@Client.on_message(filters.private & filters.command(['poster', 'p']))
async def poster_cmd(client, message):
    if len(message.command) == 1:
        return await message.reply_text("**__Please provide Anime or Movie Name__\n\nEx :- `/p Naruto` or `/p Avengers`**")

    query = message.text.split(" ", 1)[1].strip()
    user_id = message.from_user.id
    SEARCH_CACHE[user_id] = query
    process_msg = await message.reply_text("`🔍 Searching TMDB...`", quote=True)

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
                btn_text, callback_data=f"show_raw|{res.get('id')}|{media_type}|0"
            )])
            if len(buttons) == 5:   # Show Top 5 matches
                break

        if not buttons:
            return await process_msg.edit("**Anime / Movie not found! Please check spelling.**")

        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="close_search")])
        await process_msg.edit(
            f"**Search Results for:** `{query}`\n\nSelect a title to view landscape backdrops:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await process_msg.edit(f"**Error:** `{e}`")


@Client.on_callback_query(filters.regex(r"^close_search$"), group=1)
async def close_search_cb(client, query: CallbackQuery):
    await query.answer()
    # 1. User anupina /p command message delete, 2. bot message delete
    await delete_cmd(client, query.message.chat.id, query.message.id)
    try:
        await query.message.delete()
    except Exception:
        pass


# --- Back to Search Results from Landscape / Poster View ---
@Client.on_callback_query(filters.regex(r"^back_search"), group=1)
async def back_search_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    search_query = SEARCH_CACHE.get(user_id)

    if not search_query:
        parts = query.data.split("|")
        if len(parts) >= 3:
            tmdb_id, media_type = parts[1], parts[2]
            info = await get_info(media_type, tmdb_id)
            search_query = info.get("title")

    if not search_query:
        return await query.answer("Search session expired. Use /p <name> again!", show_alert=True)

    await query.answer("🔙 Back to search results...")

    try:
        data = await get_json(
            "https://api.themoviedb.org/3/search/multi",
            params={"api_key": TMDB_API_KEY, "query": search_query},
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
                btn_text, callback_data=f"show_raw|{res.get('id')}|{media_type}|0"
            )])
            if len(buttons) == 5:
                break

        if not buttons:
            return await query.answer("No titles found!", show_alert=True)

        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="close_search")])

        # Delete panrathuku munnadi link ah thedi edukkanum
        reply_id = await get_cmd_id(client, query.message.chat.id, query.message.id)

        try:
            await query.message.delete()
        except Exception:
            pass
        await client.send_message(
            chat_id=query.message.chat.id,
            text=f"**Search Results for:** `{search_query}`\n\nSelect a title to view landscape backdrops:",
            reply_markup=InlineKeyboardMarkup(buttons),
            reply_to_message_id=reply_id
        )
    except Exception as e:
        try:
            await query.message.reply_text(f"**Error:** `{e}`")
        except Exception:
            pass


# ======================= 1. RAW LANDSCAPE VIEW =======================

async def display_raw(client, query, tmdb_id, media_type, idx):
    backdrops = await get_backdrops(media_type, tmdb_id)
    if not backdrops:
        if query.message.photo:
            return await query.message.edit_caption("**❌ No landscape backdrop images found!**")
        return await query.message.edit_text("**❌ No landscape backdrop images found!**")

    total = len(backdrops)
    idx = idx % total
    info = await get_info(media_type, tmdb_id)
    raw_url = f"https://image.tmdb.org/t/p/w1280{backdrops[idx]}"

    await deliver(
        client, query, raw_url,
        raw_caption(idx, total, info),
        raw_markup(tmdb_id, media_type, idx, total)
    )

@Client.on_callback_query(filters.regex(r"^show_raw\|"), group=1)
async def show_raw_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx = parts[1], parts[2], int(parts[3])

    try:
        await query.answer("⏳ Loading landscape image...")
    except Exception:
        pass

    if not query.message.photo:
        try:
            await query.message.edit_text("`  Fetching landscape image...`")
        except Exception:
            pass

    try:
        await display_raw(client, query, tmdb_id, media_type, idx)
    except Exception as e:
        try:
            if query.message.photo:
                await query.message.edit_caption(f"**Error:** `{e}`")
            else:
                await query.message.edit_text(f"**Error:** `{e}`")
        except Exception:
            pass

# Backward compatibility alias
@Client.on_callback_query(filters.regex(r"^show_img\|"), group=1)
async def show_img_alias_cb(client, query: CallbackQuery):
    await show_raw_cb(client, query)


# ======================= 2. NORMAL GENERATE IMAGE =======================

@Client.on_callback_query(filters.regex(r"^gen_normal\|"), group=1)
async def generate_normal_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx = parts[1], parts[2], int(parts[3])
    user_id = query.from_user.id

    try:
        await query.answer("⚡ Generating poster with glass watermark...")
    except Exception:
        pass

    try:
        res = await render(user_id, tmdb_id, media_type, idx, st=0)
        if not res:
            return await query.message.edit_caption("**❌ Failed to render poster!**")
        path, idx, total, text, scale, info = res
        await deliver(
            client, query, path,
            normal_poster_caption(idx, total, text, scale, info),
            normal_poster_markup(tmdb_id, media_type, idx, total)
        )
    except Exception as e:
        try:
            await query.message.edit_caption(f"**Error:** `{e}`")
        except Exception:
            pass


# ======================= 3. CUSTOM STYLE PANEL =======================

async def show_panel(client, query, user_id, tmdb_id, media_type, idx, st):
    res = await render(user_id, tmdb_id, media_type, idx, st)
    if not res:
        return
    path, idx, total, text, scale, info = res
    await deliver(
        client, query, path,
        style_caption(text, scale, st, info),
        style_markup(tmdb_id, media_type, idx, st)
    )

@Client.on_callback_query(filters.regex(r"^cstyle\|"), group=1)
async def custom_style_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx, st = parts[1], parts[2], int(parts[3]), parse_st(parts, 4)
    st = st if st in DESIGNS else 1
    
    try:
        await query.answer("  Opening Custom Style Menu...")
        info = await get_info(media_type, tmdb_id)
        text = await get_wm_text(query.from_user.id)
        scale = await get_scale(query.from_user.id)
        
        caption = style_caption(text, scale, st, info)
        markup = style_markup(tmdb_id, media_type, idx, st)
        
        await query.message.edit_caption(caption=caption, reply_markup=markup)
    except Exception as e:
        try:
            await query.message.edit_caption(f"**Error:** `{e}`")
        except Exception:
            pass

# --- 12 Design Selection Buttons ---
@Client.on_callback_query(filters.regex(r"^dsgn\|"), group=1)
async def design_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx, st = parts[1], parts[2], int(parts[3]), parse_st(parts, 4)

    status_name = "Clean (Watermark Only)" if st == 0 else design_name(st)
    try:
        await query.answer(f"🎨 {status_name} ✅")
    except Exception:
        pass

    try:
        await show_panel(client, query, query.from_user.id, tmdb_id, media_type, idx, st)
    except Exception as e:
        try:
            await query.message.edit_caption(f"**Error:** `{e}`")
        except Exception:
            pass

# --- Size + / - (Supported if called) ---
@Client.on_callback_query(filters.regex(r"^wmsize\|"), group=1)
async def wm_size_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx, st, op = parts[1], parts[2], int(parts[3]), parse_st(parts, 4), parts[5]
    user_id = query.from_user.id

    scale = await get_scale(user_id)
    new_scale = round(scale + SCALE_STEP, 1) if op == "p" else round(scale - SCALE_STEP, 1)
    new_scale = min(SCALE_MAX, max(SCALE_MIN, new_scale))

    if new_scale == scale:
        return await query.answer("Size limit reached! (0.4x - 3.0x)", show_alert=True)

    await query.answer(f"📏 Size: {new_scale}x ✅")
    await goku_stark.set_wm_scale(user_id, new_scale)   # Permanent DB Save

    try:
        await show_panel(client, query, user_id, tmdb_id, media_type, idx, st)
    except Exception as e:
        try:
            await query.message.edit_caption(f"**Error:** `{e}`")
        except Exception:
            pass

# --- Set My Watermark button (from poster) ---
@Client.on_callback_query(filters.regex(r"^wmset\|"), group=1)
async def wm_set_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx, st = parts[1], parts[2], int(parts[3]), parse_st(parts, 4)
    user_id = query.from_user.id
    await query.answer()

    prompt = await client.send_message(
        query.message.chat.id,
        "**✏️ Send your new Watermark Name**\n\nEx :- `@Techgokul`\n\n__(Send text within 60 seconds)__",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="wmcancel")]])
    )
    WAITING[user_id] = {
        "mode": "poster",
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
        if state and state.get("prompt_id") == prompt.id:
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


# ======================= 4. STANDALONE /set_watermark CALLBACKS =======================

@Client.on_callback_query(filters.regex(r"^wm_menu_name$"), group=1)
async def wm_menu_name_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    await query.answer()

    prompt = await client.send_message(
        query.message.chat.id,
        "**✏️ Send your Watermark Name**\n\nEx :- `@Techgokul`\n\n__(Send text within 60 seconds)__",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="wmcancel")]])
    )
    WAITING[user_id] = {
        "mode": "menu",
        "chat_id": query.message.chat.id,
        "menu_id": query.message.id,
        "prompt_id": prompt.id,
    }

    async def timeout():
        await asyncio.sleep(60)
        state = WAITING.get(user_id)
        if state and state.get("prompt_id") == prompt.id:
            WAITING.pop(user_id, None)
            try:
                await prompt.delete()
            except Exception:
                pass
    asyncio.create_task(timeout())

@Client.on_callback_query(filters.regex(r"^wm_menu_scale\|"), group=1)
async def wm_menu_scale_cb(client, query: CallbackQuery):
    op = query.data.split("|")[1]
    user_id = query.from_user.id

    scale = await get_scale(user_id)
    new_scale = round(scale + SCALE_STEP, 1) if op == "p" else round(scale - SCALE_STEP, 1)
    new_scale = min(SCALE_MAX, max(SCALE_MIN, new_scale))

    if new_scale == scale:
        return await query.answer("Size limit reached! (0.4x - 3.0x)", show_alert=True)

    await goku_stark.set_wm_scale(user_id, new_scale)
    await query.answer(f"📏 Size: {new_scale}x ✅")
    text = await wm_menu_text(user_id, status_alert=f"📏 Size updated: `{new_scale}x` ✅")
    try:
        await query.message.edit_text(text, reply_markup=wm_menu_markup())
    except MessageNotModified:
        pass

@Client.on_callback_query(filters.regex(r"^wm_menu_reset$"), group=1)
async def wm_menu_reset_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    await goku_stark.set_watermark(user_id, DEFAULT_WM)
    await goku_stark.set_wm_scale(user_id, 1.0)
    await query.answer("Reset to default watermark & size! ✅")
    text = await wm_menu_text(user_id, status_alert="🔄 Reset to defaults (`@Techgokul`, `1.0x`) ✅")
    try:
        await query.message.edit_text(text, reply_markup=wm_menu_markup())
    except MessageNotModified:
        pass

@Client.on_callback_query(filters.regex(r"^wm_menu_close$"), group=1)
async def wm_menu_close_cb(client, query: CallbackQuery):
    await query.answer("Closed")
    try:
        await query.message.delete()
    except Exception:
        pass


# ======================= INPUT LISTENER (Watermark Name) =======================

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
        await goku_stark.set_watermark(user_id, name)

        # Cleanup prompt and input messages
        for chat_id, msg_id in ((message.chat.id, message.id), (st["chat_id"], st.get("prompt_id"))):
            if msg_id:
                try:
                    await client.delete_messages(chat_id, msg_id)
                except Exception:
                    pass

        mode = st.get("mode", "poster")
        if mode == "menu":
            text = await wm_menu_text(user_id, status_alert=f"✅ Watermark Name saved: `{name}`")
            try:
                await client.edit_message_text(
                    chat_id=st["chat_id"],
                    message_id=st["menu_id"],
                    text=text,
                    reply_markup=wm_menu_markup()
                )
            except Exception:
                await client.send_message(st["chat_id"], f"**Watermark saved:** `{name}` ✅")
        else:
            # Refreshes poster with the new watermark
            try:
                res = await render(user_id, st["tmdb_id"], st["media_type"], st["idx"], st["st"])
                if res:
                    path, idx, total, text, scale, info = res
                    try:
                        await client.edit_message_media(
                            chat_id=st["chat_id"],
                            message_id=st["photo_id"],
                            media=InputMediaPhoto(path, caption=style_caption(text, scale, st["st"], info)),
                            reply_markup=style_markup(st["tmdb_id"], st["media_type"], idx, st["st"])
                        )
                    except Exception:
                        await client.send_message(st["chat_id"], f"**Watermark saved:** `{name}` ✅")
                    finally:
                        if os.path.exists(path):
                            os.remove(path)
            except Exception:
                await client.send_message(st["chat_id"], f"**Watermark saved:** `{name}` ✅")

    message.stop_propagation()


# ======================= 5. CUSTOM LOGO (position -> OK -> Manual Photo) =======================

LOGO_POS = {
    "t":  ("⬆️ Top", "top"),
    "b":  ("⬇️ Bottom", "bottom"),
    "bl": ("↙️ Bottom Left", "bottom_left"),
}
WAIT_PHOTO = {}              # State: user is expected to send a manual photo
PHOTO_WAIT_SECONDS = 120


def _pos_code(parts, pos=4):
    try:
        c = parts[pos]
    except Exception:
        c = "b"
    return c if c in LOGO_POS else "b"


def _edge_gradient(size, top, frac=0.38, max_alpha=170):
    """Soft dark fade on top/bottom edge so the logo is visible on any photo."""
    w, h = size
    gh = max(2, int(h * frac))
    col = Image.new("L", (1, gh))
    for y in range(gh):
        t = y / (gh - 1)
        t = (1 - t) if top else t
        col.putpixel((0, y), int(max_alpha * (t ** 1.6)))
    mask = col.resize((w, gh))
    shade = Image.new("RGBA", (w, gh), (0, 0, 0, 255))
    shade.putalpha(mask)
    grad = Image.new("RGBA", size, (0, 0, 0, 0))
    grad.paste(shade, (0, 0 if top else h - gh))
    return grad


def _text_logo(title):
    """Fallback when TMDB has no title logo: draw the title as a bold white text logo."""
    title = (title or "").strip() or " "
    lines = textwrap.wrap(title, width=20)[:3] or [title]
    font = load_font(200)
    boxes = [_PROBE.textbbox((0, 0), ln, font=font) for ln in lines]
    widths = [b[2] - b[0] for b in boxes]
    heights = [b[3] - b[1] for b in boxes]
    gap = 24
    pad = 30
    cw = max(widths) + pad * 2
    ch = sum(heights) + gap * (len(lines) - 1) + pad * 2
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    y = pad
    for ln, bx, w, h in zip(lines, boxes, widths, heights):
        x = (cw - w) // 2 - bx[0]
        d.text((x + 6, y - bx[1] + 6), ln, font=font, fill=(0, 0, 0, 190))
        d.text((x, y - bx[1]), ln, font=font, fill=(255, 255, 255, 255))
        y += h + gap
    return canvas


def build_logo_poster(img_bytes, logo_bytes, title, text, scale, pos, out_path):
    """Title logo at chosen position (top / bottom / bottom_left) + glass watermark."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(img_bytes))).convert("RGBA")
    b = img.width / 1920
    margin = int(48 * b)

    logo = None
    if logo_bytes:
        try:
            logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
        except Exception:
            logo = None
    if logo is None:
        logo = _text_logo(title)

    box = logo.getchannel("A").getbbox()
    if box:
        logo = logo.crop(box)

    max_w = int(img.width * 0.34)
    max_h = int(img.height * 0.22)
    r = min(max_w / logo.width, max_h / logo.height)
    logo = logo.resize((max(1, int(logo.width * r)), max(1, int(logo.height * r))), Image.LANCZOS)
    lw, lh = logo.size

    if pos == "top":
        x, y = (img.width - lw) // 2, margin
    elif pos == "bottom_left":
        x, y = margin, img.height - lh - margin
    else:  # bottom (center)
        x, y = (img.width - lw) // 2, img.height - lh - margin

    img = Image.alpha_composite(img, _edge_gradient(img.size, top=(pos == "top")))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.alpha_composite(logo, dest=(max(0, x), max(0, y)))
    draw_watermark(img, layer, text, scale)

    final = Image.alpha_composite(img, layer).convert("RGB")
    final.save(out_path, format="JPEG", quality=90)


async def _compose_logo(user_id, tmdb_id, media_type, img_bytes, pos):
    text = await get_wm_text(user_id)
    scale = await get_scale(user_id)
    info = await get_info(media_type, tmdb_id)
    logo_bytes = await get_logo(media_type, tmdb_id, "original")
    out_path = f"logo_{user_id}_{int(time.time() * 1000)}.jpg"
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, build_logo_poster, img_bytes, logo_bytes, info.get("title", ""), text, scale, pos, out_path
    )
    return out_path, text, scale, info, bool(logo_bytes)


async def render_logo(user_id, tmdb_id, media_type, idx, pos):
    backdrops = await get_backdrops(media_type, tmdb_id)
    if not backdrops:
        return None
    idx = idx % len(backdrops)
    img_bytes = await get_bytes(f"https://image.tmdb.org/t/p/original{backdrops[idx]}")
    path, text, scale, info, has_logo = await _compose_logo(user_id, tmdb_id, media_type, img_bytes, pos)
    return path, idx, len(backdrops), text, scale, info, has_logo


# ---------- Buttons & captions ----------

def logo_pos_markup(tmdb_id, mt, idx, code):
    def pbtn(c):
        label = LOGO_POS[c][0]
        return InlineKeyboardButton(
            f"✅ {label}" if c == code else label,
            callback_data=f"clpos|{tmdb_id}|{mt}|{idx}|{c}"
        )
    return InlineKeyboardMarkup([
        [pbtn("t"), pbtn("b")],
        [pbtn("bl")],
        [InlineKeyboardButton("✔️ OK", callback_data=f"clok|{tmdb_id}|{mt}|{idx}|{code}")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"show_raw|{tmdb_id}|{mt}|{idx}")],
    ])


def logo_pos_caption(info, code):
    title = info.get("title") or ""
    tag = f"🎬 **Title:** `{title}`\n" if title else ""
    return (
        f"**🏷 CUSTOM LOGO**\n"
        f"{tag}\n"
        f"📍 **Where should the title logo be placed?**\n"
        f"Selected: **{LOGO_POS[code][0]}**\n\n"
        f"__Choose a position above, then tap ✔️ OK.__\n\n"
        f"*(Auto-deletes in {AUTO_DELETE_TEXT})*"
    )


def logo_panel_markup(tmdb_id, mt, idx, code):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📷 Manual Photo", callback_data=f"clphoto|{tmdb_id}|{mt}|{idx}|{code}")],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"clback|{tmdb_id}|{mt}|{idx}|{code}"),
            InlineKeyboardButton("❌ Close", callback_data="delete_auto"),
        ],
    ])


def logo_panel_caption(code, text, scale, info, has_logo, manual=False):
    title = info.get("title") or ""
    tag = f"🎬 **Title:** `{title}`\n" if title else ""
    src = "📷 Your photo" if manual else "🌅 TMDB backdrop"
    note = "" if has_logo else "\n⚠️ __TMDB logo not found, so the title text is used as logo.__\n"
    return (
        f"**🏷 CUSTOM LOGO STUDIO**\n"
        f"{tag}"
        f"🖼 **Image:** {src}\n"
        f"📍 **Logo Position:** {LOGO_POS[code][0]}\n"
        f"🏷 **Watermark:** `{text}` | 📏 **Size:** `{scale}x`\n"
        f"{note}\n"
        f"__Tap 📷 Manual Photo, then send your own image. The logo and watermark will be added to it.__\n\n"
        f"*(Auto-deletes in {AUTO_DELETE_TEXT})*"
    )


# ---------- Callbacks ----------

# Position selection screen (also used when a position button is tapped)
@Client.on_callback_query(filters.regex(r"^clpos\|"), group=1)
async def logo_pos_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx, code = parts[1], parts[2], int(parts[3]), _pos_code(parts)

    try:
        await query.answer(f"📍 {LOGO_POS[code][0]}")
    except Exception:
        pass

    try:
        info = await get_info(media_type, tmdb_id)
        await query.message.edit_caption(
            caption=logo_pos_caption(info, code),
            reply_markup=logo_pos_markup(tmdb_id, media_type, idx, code)
        )
    except MessageNotModified:
        pass
    except Exception as e:
        try:
            await query.message.edit_caption(f"**Error:** `{e}`")
        except Exception:
            pass


# Back from the Custom Logo panel -> position screen (with the plain backdrop again)
@Client.on_callback_query(filters.regex(r"^clback\|"), group=1)
async def logo_back_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx, code = parts[1], parts[2], int(parts[3]), _pos_code(parts)

    try:
        await query.answer("🔙 Back")
    except Exception:
        pass

    try:
        backdrops = await get_backdrops(media_type, tmdb_id)
        if not backdrops:
            return await query.message.edit_caption("**❌ No landscape backdrop images found!**")
        idx = idx % len(backdrops)
        info = await get_info(media_type, tmdb_id)
        raw_url = f"https://image.tmdb.org/t/p/w1280{backdrops[idx]}"
        await deliver(
            client, query, raw_url,
            logo_pos_caption(info, code),
            logo_pos_markup(tmdb_id, media_type, idx, code)
        )
    except Exception as e:
        try:
            await query.message.edit_caption(f"**Error:** `{e}`")
        except Exception:
            pass


# OK -> Custom Logo panel (logo placed on the backdrop + watermark)
@Client.on_callback_query(filters.regex(r"^clok\|"), group=1)
async def logo_ok_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx, code = parts[1], parts[2], int(parts[3]), _pos_code(parts)
    user_id = query.from_user.id

    try:
        await query.answer("⏳ Placing logo...")
    except Exception:
        pass

    try:
        res = await render_logo(user_id, tmdb_id, media_type, idx, LOGO_POS[code][1])
        if not res:
            return await query.message.edit_caption("**❌ Failed to render poster!**")
        path, idx, total, text, scale, info, has_logo = res
        await deliver(
            client, query, path,
            logo_panel_caption(code, text, scale, info, has_logo),
            logo_panel_markup(tmdb_id, media_type, idx, code)
        )
    except Exception as e:
        try:
            await query.message.edit_caption(f"**Error:** `{e}`")
        except Exception:
            pass


# Manual Photo -> ask the user to send an image
@Client.on_callback_query(filters.regex(r"^clphoto\|"), group=1)
async def logo_photo_cb(client, query: CallbackQuery):
    parts = query.data.split("|")
    tmdb_id, media_type, idx, code = parts[1], parts[2], int(parts[3]), _pos_code(parts)
    user_id = query.from_user.id
    await query.answer()

    old = WAIT_PHOTO.pop(user_id, None)
    if old and old.get("prompt_id"):
        try:
            await client.delete_messages(old["chat_id"], old["prompt_id"])
        except Exception:
            pass

    prompt = await client.send_message(
        query.message.chat.id,
        f"**📷 Send your Photo**\n\n"
        f"Logo position: **{LOGO_POS[code][0]}**\n"
        f"Your image will come back with the logo + watermark.\n\n"
        f"__(Send the photo within {PHOTO_WAIT_SECONDS} seconds)__",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="clcancel")]])
    )
    WAIT_PHOTO[user_id] = {
        "chat_id": query.message.chat.id,
        "photo_id": query.message.id,
        "prompt_id": prompt.id,
        "tmdb_id": tmdb_id,
        "media_type": media_type,
        "idx": idx,
        "code": code,
    }

    async def timeout():
        await asyncio.sleep(PHOTO_WAIT_SECONDS)
        state = WAIT_PHOTO.get(user_id)
        if state and state.get("prompt_id") == prompt.id:
            WAIT_PHOTO.pop(user_id, None)
            try:
                await prompt.delete()
            except Exception:
                pass
    asyncio.create_task(timeout())


@Client.on_callback_query(filters.regex(r"^clcancel$"), group=1)
async def logo_cancel_cb(client, query: CallbackQuery):
    WAIT_PHOTO.pop(query.from_user.id, None)
    await query.answer("Cancelled")
    try:
        await query.message.delete()
    except Exception:
        pass


# Listener: user sends the manual photo (as photo or as image file)
async def _photo_wait_filter(_, __, message):
    if not (message.from_user and message.from_user.id in WAIT_PHOTO):
        return False
    if message.photo:
        return True
    doc = message.document
    return bool(doc and (doc.mime_type or "").startswith("image/"))

photo_waiting = filters.create(_photo_wait_filter)

@Client.on_message(filters.private & photo_waiting, group=-1)
async def receive_logo_photo(client, message):
    user_id = message.from_user.id
    st = WAIT_PHOTO.pop(user_id, None)
    if not st:
        return

    status = await message.reply_text("`⏳ Applying logo & watermark...`", quote=True)
    path = None
    try:
        buf = await client.download_media(message, in_memory=True)
        img_bytes = buf.getvalue()
        path, text, scale, info, has_logo = await _compose_logo(
            user_id, st["tmdb_id"], st["media_type"], img_bytes, LOGO_POS[st["code"]][1]
        )
        caption = logo_panel_caption(st["code"], text, scale, info, has_logo, manual=True)
        markup = logo_panel_markup(st["tmdb_id"], st["media_type"], st["idx"], st["code"])
        try:
            await client.edit_message_media(
                chat_id=st["chat_id"],
                message_id=st["photo_id"],
                media=InputMediaPhoto(path, caption=caption),
                reply_markup=markup
            )
        except MessageNotModified:
            pass
        except Exception:
            # Panel message is gone (auto-deleted) -> send a fresh one
            await client.send_photo(st["chat_id"], path, caption=caption, reply_markup=markup)
    except Exception as e:
        try:
            await client.send_message(st["chat_id"], f"**❌ Error:** `{e}`")
        except Exception:
            pass
    finally:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        for chat_id, msg_id in ((message.chat.id, message.id), (st["chat_id"], st.get("prompt_id")), (status.chat.id, status.id)):
            if msg_id:
                try:
                    await client.delete_messages(chat_id, msg_id)
                except Exception:
                    pass

    message.stop_propagation()


# ======================= MISC CALLBACKS =======================

@Client.on_callback_query(filters.regex(r"^delete_auto$"), group=1)
async def manual_delete_cb(client, query: CallbackQuery):
    await query.answer("Deleted!")
    # 1. User anupina /p command message delete, 2. bot message delete
    await delete_cmd(client, query.message.chat.id, query.message.id)
    try:
        await query.message.delete()
    except Exception:
        pass

@Client.on_callback_query(filters.regex(r"^ignore$"), group=1)
async def ignore_cb(client, query: CallbackQuery):
    await query.answer()
