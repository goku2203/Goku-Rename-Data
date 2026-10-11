import os, re, time, aiohttp, asyncio
from urllib.parse import urlparse, unquote
from pyrogram import Client, filters
from helper.database import digital_botz
from helper.utils import humanbytes, remove_path, file_queue_lock
from plugins.file_rename import upload_files, DUMP_STICKER_ID, renamer
from script import script

# Filename total length limit (file renamer-la irukkura same 60 limit)
MAX_NAME_LEN = 60


def normalize_season_episode(name: str) -> str:
    """[S03-E01] / S03-E01 / S03 E01  ->  S03E01  (auto_rename parser-ku purira maathiri)"""
    name = re.sub(r'[\[\(]\s*(S\d{1,2})\s*[-_. ]?\s*(E(?:P)?\d{1,4})\s*[\]\)]', r' \1\2 ', name, flags=re.IGNORECASE)
    name = re.sub(r'(?<![A-Za-z0-9])(S\d{1,2})[-_. ](E(?:P)?\d{1,4})(?![A-Za-z0-9])', r'\1\2', name, flags=re.IGNORECASE)
    return name


def build_clean_filename(info, prefix, suffix, ext_str, limit=MAX_NAME_LEN):
    """File renamer maathiri filename: prefix + title + SxxExx + quality + suffix (spaces-oda, underscore illama)."""
    title = (info.get('title') or '').replace("_", " ")
    se = f"{info.get('season') or ''}{info.get('episode') or ''}"
    quality = (info.get('quality') or '').replace("_", " ")

    parts_except_title = [p for p in (prefix, se, quality, suffix) if p]
    extra_len = sum(len(p) for p in parts_except_title) + len(parts_except_title)
    ext_len = len(ext_str) + 1 if ext_str else 0

    max_title_len = limit - extra_len - ext_len
    if max_title_len > 0 and len(title) > max_title_len:
        title = title[:max_title_len].strip()
    elif max_title_len <= 0:
        title = ""

    name = " ".join(p for p in (prefix, title, se, quality, suffix) if p)
    name = re.sub(r'[\\/:*?"<>|]', "", name)   # file-system-ku problem varra characters mattum remove
    name = " ".join(name.split())
    return f"{name}.{ext_str}" if ext_str else name


async def add_metadata(file_path: str) -> str:
    """File renamer maathiri ffmpeg-la script.METADATA_TITLE metadata add pannum. Fail aanaalum original file use aagum."""
    title = script.METADATA_TITLE
    folder, name = os.path.split(file_path)
    meta_path = os.path.join(folder, f"meta_{name}")
    cmd = [
        "ffmpeg", "-y", "-i", file_path, "-c", "copy", "-map", "0",
        "-metadata", f"title={title}",
        "-metadata", f"encoder={title}",
        "-metadata", f"uploader={title}",
        "-metadata", f"website={title}",
        "-metadata", f"artist={title}",
        "-metadata", f"notes={title}",
        "-metadata:s:v", f"title={title}",
        "-metadata:s:a", f"title={title}",
        "-metadata:s:s", f"title={title}",
        meta_path,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await proc.communicate()
        if proc.returncode == 0 and os.path.exists(meta_path) and os.path.getsize(meta_path) > 0:
            os.remove(file_path)
            os.rename(meta_path, file_path)
        elif os.path.exists(meta_path):
            os.remove(meta_path)
    except Exception as e:
        print(f"[URL-METADATA] failed: {e}", flush=True)
        if os.path.exists(meta_path):
            try: os.remove(meta_path)
            except Exception: pass
    return file_path


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
                        await rkn_processing.edit("❌ Failed to download from the provided URL. Ensure it is a direct link.")
                        await asyncio.sleep(5)
                        try:
                            await message.delete()
                            await rkn_processing.delete()
                        except:
                            pass
                        return
                
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
        await rkn_processing.edit(f"❌ Error during download: {e}")
        await asyncio.sleep(5)
        try:
            await message.delete()
            await rkn_processing.delete()
        except:
            pass
        return
        
    await rkn_processing.edit("`📝 Applying Auto-Rename Format...`")
    
    # 3. Apply Auto-Rename logic
    parse_name = normalize_season_episode(original_filename)
    info = renamer.extract_all_info(parse_name)
    format_template = user_data.get('format_template', "{filename}")
    if format_template is None:
        format_template = "{filename}"
    prefix = user_data.get('prefix', None)
    suffix = user_data.get('suffix', None)
    
    ext_str = (info.get('extension') or original_filename.rsplit('.', 1)[-1]).lstrip('.').strip()
    if not ext_str:
        ext_str = "mkv"
    info['extension'] = ext_str
    
    # --- CAPTION: autorename format padi (maarala) ---
    full_caption_name = renamer.apply_format_template(info, format_template)
    if not full_caption_name.endswith(f".{ext_str}"):
        full_caption_name += f".{ext_str}"
        
    cap_base = full_caption_name.rsplit('.', 1)[0]
    if prefix: 
        cap_base = f"{prefix} {cap_base}"
    if suffix: 
        cap_base = f"{cap_base} {suffix}"
    
    final_caption_name = f"{cap_base}.{ext_str}".strip()

    # --- FILENAME: file renamer maathiri (title + SxxExx + quality, 60 limit, underscore illa) ---
    new_filename = build_clean_filename(info, prefix, suffix, ext_str)
    new_local_path = f"Renames/{new_filename}"
    print(f"[URL-RENAME-DEBUG] raw={original_filename!r} -> new={new_filename!r}", flush=True)
    
    os.rename(local_path, new_local_path)

    # --- METADATA: file renamer maathiri (script.py la METADATA_TITLE) ---
    try:
        await rkn_processing.edit("`🏷️ Adding Metadata...`")
    except Exception:
        pass
    await add_metadata(new_local_path)
    
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
        dump_status = await digital_botz.get_dump_status(user_id)
        if dump_id and dump_status and filw:
            try:
                await filw.copy(int(dump_id))
                await client.send_sticker(chat_id=int(dump_id), sticker=DUMP_STICKER_ID)
            except Exception:
                pass
                
        # --- Upload success aanadhum user anuppuna URL message-a udane delete ---
        try:
            await message.delete()
        except Exception:
            pass

        # --- Success message kaattitu 5 second-la delete ---
        try:
            await rkn_processing.edit("**Uploaded Successfully!...**")
            await asyncio.sleep(5)
            await rkn_processing.delete()
        except Exception:
            pass
