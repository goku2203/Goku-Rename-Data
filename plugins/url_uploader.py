import os, time, aiohttp, asyncio
from urllib.parse import urlparse, unquote
from pyrogram import Client, filters
from helper.database import digital_botz
from helper.utils import humanbytes, remove_path, file_queue_lock
from plugins.file_rename import upload_files, DUMP_STICKER_ID, renamer

@Client.on_message(filters.private & filters.regex(r"^https?://"))
async def url_uploader_handler(client, message):
    user_id = message.from_user.id
    url = message.text.strip()
    
    user_data = await digital_botz.get_user_data(user_id)
    upload_type = user_data.get('upload_type', 'video')
    
    if not upload_type:
        return await message.reply_text("⚠️ Default Output Format is not set!\n\nFirst use `/set_type` command to select Document or Video.")
        
    actual_upload_type = "document" if upload_type == "doc" else "video"
        
    rkn_processing = await message.reply_text("`⏳ URL Added to Queue... Please wait your turn...`")
    
    async with file_queue_lock:
        await rkn_processing.edit("`🔗 URL Detected... Starting Download...`")
    
    original_filename = "Downloaded_video.mkv"
    local_path = ""
    
    # 1 & 2. Extract Name from Header & Download the file
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return await rkn_processing.edit("❌ Failed to download from the provided URL. Ensure it is a direct link.")
                
                # File name extract panra puthiya logic
                cd = response.headers.get('Content-Disposition')
                extracted_name = None
                if cd:
                    if 'filename="' in cd:
                        extracted_name = cd.split('filename="')[1].split('"')[0]
                    elif 'filename=' in cd:
                        extracted_name = cd.split('filename=')[1].split(';')[0].strip()
                
                if not extracted_name:
                    parsed_url = urlparse(str(response.url))
                    extracted_name = unquote(os.path.basename(parsed_url.path))
                
                if extracted_name and "." in extracted_name:
                    original_filename = extracted_name
                    
                os.makedirs("Renames", exist_ok=True)
                local_path = f"Renames/{original_filename}"
                
                total_size = int(response.headers.get('content-length', 0))
                
                with open(local_path, 'wb') as f:
                    downloaded = 0
                    start_time = time.time()
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress every 3 seconds
                        if time.time() - start_time > 3:
                            try:
                                await rkn_processing.edit(f"**📥 Downloading from URL:**\n\n📦 Size: {humanbytes(downloaded)} / {humanbytes(total_size)}")
                                start_time = time.time()
                            except: 
                                pass
    except Exception as e:
        return await rkn_processing.edit(f"❌ Error during download: {e}")
        
    await rkn_processing.edit("`📝 Applying Auto-Rename Format...`")
    
    # 3. Apply Auto-Rename logic
    info = renamer.extract_all_info(original_filename)
    format_template = user_data.get('format_template', "{filename}")
    prefix = user_data.get('prefix', None)
    suffix = user_data.get('suffix', None)
    
    ext_str = (info.get('extension') or original_filename.rsplit('.', 1)[-1]).lstrip('.').strip()
    info['extension'] = ext_str
    
    full_caption_name = renamer.apply_format_template(info, format_template)
    if not full_caption_name.endswith(f".{ext_str}"):
        full_caption_name += f".{ext_str}"
        
    cap_base = full_caption_name.rsplit('.', 1)[0]
    if prefix: 
        cap_base = f"{prefix} {cap_base}"
    if suffix: 
        cap_base = f"{cap_base} {suffix}"
    
    final_caption_name = f"{cap_base}.{ext_str}".strip()
    new_local_path = f"Renames/{final_caption_name}"
    
    os.rename(local_path, new_local_path)
    
    # 4. Prepare Thumbnail and Caption
    c_caption = user_data.get('caption', None)
    if c_caption:
        caption = c_caption.format(filename=final_caption_name, filesize=humanbytes(os.path.getsize(new_local_path)), duration="00:00:00")
    else:
        caption = f"**{final_caption_name}**"

    c_thumb = user_data.get('file_id', None)
    ph_path = None
    if c_thumb:
        ph_path = await client.download_media(c_thumb)
        
    await rkn_processing.edit("`📤 Starting Upload...`")

    # 5. Upload the file
    filw, error = await upload_files(
        client, message.chat.id, actual_upload_type, new_local_path, 
        ph_path, caption, 0, rkn_processing
    )
    
    if error:
        try:
            await rkn_processing.edit(f"❌ Upload Error: {error}")
        except:
            pass
    else:
        # Handle Dump Channel Forwarding
        dump_id = await digital_botz.get_dump(user_id)
        if dump_id and filw:
            try:
                await filw.copy(int(dump_id))
                await client.send_sticker(chat_id=int(dump_id), sticker=DUMP_STICKER_ID)
            except Exception:
                pass
                
        # --- Puthiya Auto-Delete code with Try-Except (Crash Fix) ---
        try:
            await rkn_processing.edit("✅ Uploaded Successfully!\n\n_Auto deleting in 5 seconds..._")
            await
