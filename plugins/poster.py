import asyncio
import aiohttp
import io
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from PIL import Image, ImageDraw, ImageFont
from helper.database import digital_botz

# Inga unga TMDB API Key a podunga
TMDB_API_KEY = "f0ed821364e340369110e83b814899ed"

# --- Set Custom Watermark Name ---
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
    
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                
        results = data.get("results", [])
        if not results:
            return await process_msg.edit("**Anime kidaikkala bro! Spelling check pannunga.**")
            
        buttons = []
        # Top 5 results a buttons la kaatta porom
        for res in results[:5]:
            media_type = res.get("media_type")
            if media_type not in ["tv", "movie"]:
                continue
            title = res.get("name") if media_type == "tv" else res.get("title")
            year = res.get("first_air_date", "")[:4] if media_type == "tv" else res.get("release_date", "")[:4]
            tmdb_id = res.get("id")
            
            btn_text = f"{title} ({year})"
            # Callback data: tmdb_id | media_type | image_index
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"show_img|{tmdb_id}|{media_type}|0")])
            
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="close")])
        
        await process_msg.edit(
            f"**Search Results for:** `{query}`\n\nKela irukkura list la onna select pannunga:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await process_msg.edit(f"**Error:** `{e}`")

# --- Step 2 & 3: Fetch Image, Add Watermark & Show Next/Back ---
@Client.on_callback_query(filters.regex(r"^show_img\|"), group=1)
async def show_image_cb(client, query: CallbackQuery):
    await query.answer() # Button loading animation a udane stop panna
    _, tmdb_id, media_type, img_index = query.data.split("|")
    img_index = int(img_index)
    user_id = query.from_user.id
    
    await query.message.edit_text("`Fetching original landscape image...`")
    
    # Get landscape backdrops from TMDB
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/images?api_key={TMDB_API_KEY}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                
        backdrops = data.get("backdrops", [])
        if not backdrops:
            return await query.message.edit("**Intha anime kku landscape image kidaikkala bro!**")
            
        # Limit index correctly for Next/Back
        if img_index >= len(backdrops):
            img_index = 0
        elif img_index < 0:
            img_index = len(backdrops) - 1
            
        selected_img = backdrops[img_index]["file_path"]
        img_url = f"https://image.tmdb.org/t/p/original{selected_img}"
        
        # Download Image
        async with aiohttp.ClientSession() as session:
            async with session.get(img_url) as resp:
                img_data = await resp.read()
                
        # --- DRAW WATERMARK (Exact style from 2nd photo) ---
        img = Image.open(io.BytesIO(img_data)).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        
        watermark_text = await digital_botz.get_watermark(user_id)
        if not watermark_text:
            watermark_text = "@Techgokul"
            
        try:
            # Try loading a readable size font
            font = ImageFont.load_default(size=40)
        except:
            font = ImageFont.load_default()
            
        # Exact Watermark Box calculations
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        box_width = text_width + 80  # Space for text + logo + padding
        box_height = max(text_height + 20, 50)
        
        # Top Right corner position
        x0 = img.width - box_width - 30
        y0 = 30
        x1 = x0 + box_width
        y1 = y0 + box_height
        
        # 1. Draw Black semi-transparent rounded box
        draw.rounded_rectangle([x0, y0, x1, y1], radius=25, fill=(0, 0, 0, 180))
        
        # 2. Draw Telegram Blue circle inside the box
        circle_d = 30
        cx0 = x0 + 15
        cy0 = y0 + (box_height - circle_d) // 2
        cx1 = cx0 + circle_d
        cy1 = cy0 + circle_d
        draw.ellipse([cx0, cy0, cx1, cy1], fill=(36, 161, 222, 255))
        
        # 3. Draw White Text
        text_x = cx1 + 10
        text_y = y0 + (box_height - text_height) // 2 - 5
        draw.text((text_x, text_y), watermark_text, fill=(255, 255, 255, 255), font=font)
        
        # Merge and save
        final_img = Image.alpha_composite(img, overlay).convert("RGB")
        out_path = f"poster_{user_id}.jpg"
        final_img.save(out_path, format="JPEG", quality=90)
        
        # --- NEXT, BACK & DELETE BUTTONS ---
        nav_buttons = []
        if len(backdrops) > 1:
            nav_buttons.append([
                InlineKeyboardButton("⬅️ Back", callback_data=f"show_img|{tmdb_id}|{media_type}|{img_index - 1}"),
                InlineKeyboardButton(f"{img_index + 1}/{len(backdrops)}", callback_data="ignore"),
                InlineKeyboardButton("Next ➡️", callback_data=f"show_img|{tmdb_id}|{media_type}|{img_index + 1}")
            ])
            
        nav_buttons.append([InlineKeyboardButton("🗑 Delete Now", callback_data="delete_auto")])
        
        await query.message.delete()
        
        sent_photo = await client.send_photo(
            chat_id=user_id,
            photo=out_path,
            caption=f"Landscape Image {img_index + 1} 🌅\n\n*(This message will auto-delete in 2 minutes)*",
            reply_markup=InlineKeyboardMarkup(nav_buttons)
        )
        
        import os
        if os.path.exists(out_path):
            os.remove(out_path)
            
        # Auto-delete after 120 seconds
        await asyncio.sleep(120)
        try:
            await sent_photo.delete()
        except:
            pass
            
    except Exception as e:
        await query.message.edit(f"**Error:** `{e}`")

@Client.on_callback_query(filters.regex(r"^delete_auto$"), group=1)
async def manual_delete_cb(client, query: CallbackQuery):
    await query.answer("Deleted!")
    try:
        await query.message.delete()
    except:
        pass

@Client.on_callback_query(filters.regex(r"^ignore$"), group=1)
async def ignore_cb(client, query: CallbackQuery):
    await query.answer()
