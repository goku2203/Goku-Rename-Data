import asyncio
import aiohttp
import io
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from PIL import Image, ImageDraw, ImageFont
from helper.database import digital_botz

# --- Set Custom Watermark Name ---
@Client.on_message(filters.private & filters.command(['set_watermark']))
async def set_watermark_cmd(client, message):
    if len(message.command) == 1:
        return await message.reply_text("**__Please provide a Custom Name__\n\nEx :- `/set_watermark @Techgokul`**")
    
    watermark_name = message.text.split(" ", 1)[1]
    await digital_botz.set_watermark(message.from_user.id, watermark_name)
    await message.reply_text(f"**Watermark Name saved successfully:** `{watermark_name}`\n\nNow try the `/p Anime Name` command.")

# --- Generate Poster Command ---
@Client.on_message(filters.private & filters.command(['poster', 'p']))
async def poster_cmd(client, message):
    if len(message.command) == 1:
        return await message.reply_text("**__Please provide an Anime Name__\n\nEx :- `/p Naruto`**")
    
    anime_title = message.text.split(" ", 1)[1]
    
    buttons = [
        [InlineKeyboardButton("🌅 Generate Poster", callback_data=f"gen_poster|{anime_title}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="close")]
    ]
    
    await message.reply_text(
        f"**Anime:** `{anime_title}`\n\nClick the button below to generate the poster.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- Button Click Action & Image Processing ---
@Client.on_callback_query(filters.regex(r"^gen_poster\|"))
async def generate_poster_cb(client, query: CallbackQuery):
    anime_title = query.data.split("|")[1]
    user_id = query.from_user.id
    
    process_msg = await query.message.edit_text("`Drawing anime landscape... Please wait...`")
    
    # Fetch image using API (Landscape 1280x720)
    api_url = f"https://image.pollinations.ai/prompt/Beautiful%20masterpiece%20anime%20landscape%20background%20for%20{anime_title}%20with%20title%20text?width=1280&height=720&nologo=true"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    return await process_msg.edit("`API Error! Cannot generate the image.`")
                img_data = await resp.read()
                
        # Add Glass Effect Watermark using Pillow
        img = Image.open(io.BytesIO(img_data)).convert("RGBA")
        txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)
        
        # Get user's saved watermark name
        watermark_text = await digital_botz.get_watermark(user_id)
        if not watermark_text:
            watermark_text = "@Techgokul" # Default name
            
        # Use default font with size 40
        font = ImageFont.load_default(size=40)
        
        # Calculate position for Top Right corner
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        x_pos = img.width - text_width - 30  # 30px gap from right
        y_pos = 30 # 30px gap from top
        
        # Draw semi-transparent text (Glass effect)
        draw.text((x_pos, y_pos), watermark_text, fill=(255, 255, 255, 150), font=font)
        
        # Create final image
        final_img = Image.alpha_composite(img, txt_layer).convert("RGB")
        
        # Save and send the image
        out_path = f"poster_{user_id}.jpg"
        final_img.save(out_path, format="JPEG", quality=90)
        
        del_button = [[InlineKeyboardButton("🗑 Delete Now", callback_data="delete_auto")]]
        
        sent_photo = await client.send_photo(
            chat_id=user_id,
            photo=out_path,
            caption=f"**{anime_title}** Landscape Poster 🌅\n\n*(This message will auto-delete in 2 minutes)*",
            reply_markup=InlineKeyboardMarkup(del_button)
        )
        
        await process_msg.delete()
        
        import os
        if os.path.exists(out_path):
            os.remove(out_path)
            
        # Auto-delete after 2 minutes (120 seconds)
        await asyncio.sleep(120)
        try:
            await sent_photo.delete()
        except:
            pass
            
    except Exception as e:
        await process_msg.edit(f"**Error:** `{e}`")

# --- Manual Delete Button Action ---
@Client.on_callback_query(filters.regex(r"^delete_auto$"))
async def manual_delete_cb(client, query: CallbackQuery):
    try:
        await query.message.delete()
    except:
        pass
