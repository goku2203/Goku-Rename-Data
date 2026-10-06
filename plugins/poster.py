import asyncio
import aiohttp
import io
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, InputMediaPhoto
from PIL import Image, ImageDraw, ImageFont, ImageFilter
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
            # Callback data: show_img | tmdb_id | media_type | image_index | scale
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"show_img|{tmdb_id}|{media_type}|0|1.0")])
            
        # Cancel click panna search msg and user command delete aaga pudhu callback
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="close_search")])
        
        await process_msg.edit(
            f"**Search Results for:** `{query}`\n\nKela irukkura list la onna select pannunga:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await process_msg.edit(f"**Error:** `{e}`")

# --- Search Cancel aagumbothu User Command Delete aagum logic ---
@Client.on_callback_query(filters.regex(r"^close_search$"), group=1)
async def close_search_cb(client, query: CallbackQuery):
    await query.answer()
    try:
        await query.message.delete() # Bot msg delete aagum
        if query.message.reply_to_message:
            await query.message.reply_to_message.delete() # User anuppuna '/p name' delete aagum
    except:
        pass

# --- Step 2 & 3: Fetch Image, Glass Watermark, Size Adjust & Fast Next/Back ---
@Client.on_callback_query(filters.regex(r"^show_img\|"), group=1)
async def show_image_cb(client, query: CallbackQuery):
    # Button loading delay a thavirkka
    try: await query.answer() 
    except: pass 
    
    data_parts = query.data.split("|")
    tmdb_id = data_parts[1]
    media_type = data_parts[2]
    img_index = int(data_parts[3])
    scale = float(data_parts[4]) if len(data_parts) > 4 else 1.0 # Size adjust scale parameter
    
    user_id = query.from_user.id
    
    # Text message a photo va maatha pogumbothu mattum text kaattum
    if not query.message.photo:
        await query.message.edit_text("`Processing Glass Watermark...`")
    
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
                
        # --- DRAW GLASS BLUR WATERMARK ---
        img = Image.open(io.BytesIO(img_data)).convert("RGBA")
        
        watermark_text = await digital_botz.get_watermark(user_id)
        if not watermark_text:
            watermark_text = "@Techgokul"
            
        # Size Button-kku yeppadi font size maaruthu
        base_font_size = int(40 * scale)
        try:
            font = ImageFont.load_default(size=base_font_size)
        except:
            font = ImageFont.load_default()
            
        # Watermark Box calculations
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        box_width = int(text_width + (80 * scale)) 
        box_height = max(int(text_height + (20 * scale)), int(50 * scale))
        
        # Top Right corner position
        x0 = img.width - box_width - int(30 * scale)
        y0 = int(30 * scale)
        x1 = x0 + box_width
        y1 = y0 + box_height
        
        crop_box = (int(x0), int(y0), int(x1), int(y1))
        
        # 1. Glass Blur Effect (Background Crop -> Blur -> Paste)
        glass_region = img.crop(crop_box).filter(ImageFilter.GaussianBlur(15))
        darken = Image.new("RGBA", glass_region.size, (0, 0, 0, 90)) # Glass transparency
        glass_region = Image.alpha_composite(glass_region.convert("RGBA"), darken)
        
        # Rounded edges for glass panel
        radius = int(25 * scale)
        mask = Image.new("L", glass_region.size, 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle((0, 0, glass_region.width, glass_region.height), radius=radius, fill=255)
        
        img.paste(glass_region, crop_box, mask=mask)
        
        # 2. Draw Telegram Blue circle inside the box
        circle_d = int(30 * scale)
        cx0 = x0 + int(15 * scale)
        cy0 = y0 + (box_height - circle_d) // 2
        cx1 = cx0 + circle_d
        cy1 = cy0 + circle_d
        draw.ellipse([cx0, cy0, cx1, cy1], fill=(36, 161, 222, 255))
        
        # 3. Draw White Text
        text_x = cx1 + int(10 * scale)
        text_y = y0 + (box_height - text_height) // 2 - int(5 * scale)
        draw.text((text_x, text_y), watermark_text, fill=(255, 255, 255, 255), font=font)
        
        # Merge and save
        final_img = Image.alpha_composite(img, overlay).convert("RGB")
        out_path = f"poster_{user_id}.jpg"
        final_img.save(out_path, format="JPEG", quality=90)
        
        # --- NEXT, BACK & SIZE ADJUST BUTTONS ---
        nav_buttons = []
        if len(backdrops) > 1:
            nav_buttons.append([
                InlineKeyboardButton("⬅️ Back", callback_data=f"show_img|{tmdb_id}|{media_type}|{img_index - 1}|{scale}"),
                InlineKeyboardButton(f"{img_index + 1}/{len(backdrops)}", callback_data="ignore"),
                InlineKeyboardButton("Next ➡️", callback_data=f"show_img|{tmdb_id}|{media_type}|{img_index + 1}|{scale}")
            ])
            
        # Watermark Size Adjust Buttons (Scale + / -)
        nav_buttons.append([
            InlineKeyboardButton("Size ➕", callback_data=f"show_img|{tmdb_id}|{media_type}|{img_index}|{round(scale + 0.2, 1)}"),
            InlineKeyboardButton("Size ➖", callback_data=f"show_img|{tmdb_id}|{media_type}|{img_index}|{round(max(0.4, scale - 0.2), 1)}")
        ])
            
        nav_buttons.append([InlineKeyboardButton("🗑 Delete Now", callback_data="delete_auto")])
        markup = InlineKeyboardMarkup(nav_buttons)
        caption_text = f"Landscape Image {img_index + 1} 🌅\n\n*(This message will auto-delete in 2 minutes)*"
        
        # --- FAST IMAGE CHANGE LOGIC ---
        if query.message.photo:
            # Delete pannama InputMediaPhoto vachu change panrathala Fast-a image maarum
            await query.message.edit_media(
                media=InputMediaPhoto(open(out_path, "rb"), caption=caption_text),
                reply_markup=markup
            )
        else:
            # First time text msg la irunthu photo va maarum pothu
            await query.message.delete()
            sent_photo = await client.send_photo(
                chat_id=user_id,
                photo=out_path,
                caption=caption_text,
                reply_markup=markup
            )
            
            # Auto-delete first time mattum start aagum
            async def auto_delete_task(msg):
                await asyncio.sleep(120)
                try: await msg.delete()
                except: pass
            asyncio.create_task(auto_delete_task(sent_photo))
            
        if os.path.exists(out_path):
            os.remove(out_path)
            
    except Exception as e:
        # Error vantha user kku edit panni kaattum
        try: await query.message.edit(f"**Error:** `{e}`")
        except: pass

@Client.on_callback_query(filters.regex(r"^delete_auto$"), group=1)
async def manual_delete_cb(client, query: CallbackQuery):
    await query.answer("Deleted!")
    try:
        await query.message.delete()
        if query.message.reply_to_message:
            await query.message.reply_to_message.delete()
    except:
        pass

@Client.on_callback_query(filters.regex(r"^ignore$"), group=1)
async def ignore_cb(client, query: CallbackQuery):
    await query.answer()
