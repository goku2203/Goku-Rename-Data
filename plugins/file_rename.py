# pyrogram imports
from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.file_id import FileId
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply

# hachoir imports
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image

# bots imports
from helper.utils import progress_for_pyrogram, convert, humanbytes, add_prefix_suffix, remove_path, file_queue_lock, run_cancellable, safe_delete, cleanup_files
from helper.database import goku_stark
from config import Config
from script import script
from plugins.auto_rename import EnhancedAutoRenamer
from plugins.post_forward import send_post_for_title, discard_post, confirm_post, announce_post

# extra imports
from asyncio import sleep
import os, time, asyncio

UPLOAD_TEXT = """Uploading Started...."""
DOWNLOAD_TEXT = """Download Started..."""
DUMP_STICKER_ID = "CAACAgUAAxkBAAFV0UBqycw4qxCyJ5mQX5vaagAByfx3bXAAAtcWAAKfJ8FVz-LGkVxoORY9BA"

app = Client("4gb_FileRenameBot", api_id=Config.API_ID, api_hash=Config.API_HASH, session_string=Config.STRING_SESSION)

@Client.on_message(filters.private & (filters.audio | filters.document | filters.video))
async def rename_start(client, message):
    user_id  = message.from_user.id
    rkn_file = getattr(message, message.media.value)
    if not Config.STRING_SESSION:
        if rkn_file.file_size > 2000 * 1024 * 1024:
            return await message.reply_text("Sᴏʀʀy Bʀᴏ Tʜɪꜱ Bᴏᴛ Iꜱ Dᴏᴇꜱɴ'ᴛ Sᴜᴩᴩᴏʀᴛ Uᴩʟᴏᴀᴅɪɴɢ Fɪʟᴇꜱ Bɪɢɢᴇʀ Tʜᴀɴ 2Gʙ+")
   
    filename = rkn_file.file_name
    if not "." in filename:
        if "." in filename:
            extn = filename.rsplit('.', 1)[-1]
        else:
            extn = "mkv"
        filename = filename + "." + extn
        
    filesize = humanbytes(rkn_file.file_size)
    mime_type = rkn_file.mime_type
    dcid = FileId.decode(rkn_file.file_id).dc_id
    extension_type = mime_type.split('/')[0]
    
    upload_type = await goku_stark.get_upload_type(user_id)
    rename_mode = await goku_stark.get_rename_mode(user_id)
    
    # Auto Mode Logic
    if rename_mode == "auto":
        if upload_type:
            class DummyUpdate:
                def __init__(self, msg, usr, u_type):
                    self.message = msg
                    self.data = f"upload#{u_type}"
                    self.from_user = usr
                    
            processing_msg = await message.reply("`Please Wait...`", reply_to_message_id=message.id)
            processing_msg.reply_to_message = message
            actual_type = "document" if upload_type == "doc" else "video"
            dummy_update = DummyUpdate(processing_msg, message.from_user, actual_type)
            await upload_doc(client, dummy_update)
            return
        else:
            button = [[InlineKeyboardButton("📁 Dᴏᴄᴜᴍᴇɴᴛ",callback_data = "upload#document")]]
            if message.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
                button.append([InlineKeyboardButton("🎥 Vɪᴅᴇᴏ", callback_data = "upload#video")])
            elif message.media == MessageMediaType.AUDIO:
                button.append([InlineKeyboardButton("🎵 Aᴜᴅɪᴏ", callback_data = "upload#audio")])
                
            await message.reply(
                text=script.FILE_INFO_TXT.format(filename, extension_type.upper(), filesize, mime_type, dcid),
                reply_to_message_id=message.id,
                reply_markup=InlineKeyboardMarkup(button)
            )
            return

    # Manual Mode Logic
    await message.reply(
        text=script.MANUAL_RENAME_TXT.format(filename, extension_type.upper(), filesize, mime_type, dcid),
        reply_to_message_id=message.id,
        reply_markup=ForceReply(True)
    )

@Client.on_message(filters.private & filters.text & filters.reply)
async def custom_rename_handler(client, message):
    prompt_msg = message.reply_to_message
    
    if not prompt_msg.text or "Sᴇʟᴇᴄᴛ Tʜᴇ Oᴜᴛᴩᴜᴛ Fɪʟᴇ Tyᴩᴇ" not in prompt_msg.text:
        return
    
    file_msg = prompt_msg.reply_to_message
    if not file_msg or not file_msg.media:
        file_msg = await client.get_messages(message.chat.id, prompt_msg.reply_to_message_id)
        if not file_msg or not file_msg.media:
            return await message.reply_text("❌ Original file not found! Please send the file again.")
            
    custom_name = message.text
    user_id = message.from_user.id
    
    upload_type = await goku_stark.get_upload_type(user_id)
    if not upload_type:
        return await message.reply_text("❌ Default Output Format set aagala!\n\nFirst `/set_type` Use the command to select **Document** or **Video**, then send your file.")
        
    processing_msg = await client.send_message(message.chat.id, "`Please Wait...`")
    
    try:
        await prompt_msg.delete()
        await message.delete()
    except:
        pass
    
    processing_msg.reply_to_message = file_msg 
    actual_type = "document" if upload_type == "doc" else "video"
    
    class DummyUpdate:
        def __init__(self, msg, usr, u_type, c_name):
            self.message = msg
            self.data = f"upload#{u_type}"
            self.from_user = usr
            self.custom_name = c_name
            
    dummy = DummyUpdate(processing_msg, message.from_user, actual_type, custom_name)
    await upload_doc(client, dummy)

async def upload_files(bot, sender_id, upload_type, file_path, ph_path, caption, duration, rkn_processing):
    try:
        if not os.path.exists(file_path):
            return None, f"File not found: {file_path}"
                    
        real_filename = os.path.basename(file_path)
                    
        if upload_type == "document":
            filw = await bot.send_document(
                sender_id,
                document=file_path,
                file_name=real_filename,
                thumb=ph_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("**📤 Upload Started...**", rkn_processing, time.time(), real_filename))
        
        elif upload_type == "video":
            filw = await bot.send_video(
                sender_id,
                video=file_path,
                file_name=real_filename,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=(UPLOAD_TEXT, rkn_processing, time.time()))
        
        elif upload_type == "audio":
            filw = await bot.send_audio(
                sender_id,
                audio=file_path,
                file_name=real_filename,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=(UPLOAD_TEXT, rkn_processing, time.time()))
        else:
            return None, f"Unknown upload type: {upload_type}"
        
        return filw, None
        
    except Exception as e:
        return None, str(e)

renamer = EnhancedAutoRenamer()

async def _upload_doc_impl(bot, update, files, state=None):
    if state is None:
        state = {}
    rkn_processing = await update.message.edit("`⏳ File Added to Queue... Please wait your turn...`")
    
    async with file_queue_lock:
        await rkn_processing.edit("`🔄 Processing Started...`")
        
        user_id = int(update.message.chat.id)

    file = update.message.reply_to_message
    if not file:
        await rkn_processing.edit("Error: Original file message is missing or deleted! Please resend the file.")
        return False
    media = getattr(file, file.media.value)
    
    custom_name = getattr(update, "custom_name", None)
    user_data = await goku_stark.get_user_data(user_id)
    
    raw_ext = ""
    if media and getattr(media, "file_name", None) and "." in media.file_name:
        raw_ext = media.file_name.rsplit(".", 1)[-1].strip()
    if not raw_ext:
        raw_ext = "mkv"

    if custom_name:
        new_name = custom_name.replace("_", " ")
        if "." not in new_name:
            info = renamer.extract_all_info(media.file_name) if media.file_name else {}
            ext = (info.get('extension') or raw_ext or "mkv").lstrip(".").strip()
            new_name += f".{ext}"
            
        final_caption_name = new_name
        new_filename = new_name
        post_title = renamer.extract_all_info(new_name).get('title')
    else:
        # --- NEW FEATURE: Filename la underlines irunthu box illana, Caption a check panra logic ---
        source_name = media.file_name

        if file.caption:
            # 1. Caption la 'File Name:' nu irukka nu check pannum
            if "File Name:" in file.caption:
                for line in file.caption.split('\n'):
                    if "File Name:" in line:
                        source_name = line.split("File Name:")[1].strip()
                        break
            # 2. Illana, file_name la box illama, caption starting la box '[' iruntha athai eduthukkum
            elif not media.file_name.strip().startswith("["):
                first_line = file.caption.split('\n')[0].strip()
                if first_line.startswith("["):
                    source_name = first_line

        # Ippo pudhu source_name a vechu info extract pannum (Toons box automatic a remove aagidum)
        info = renamer.extract_all_info(source_name)
        
        # Caption-la irunthu Season, Quality, extra details thedi yedukkum logic
        if file.caption:
            caption_info = renamer.extract_all_info(file.caption.replace("\n", " "))
            for key, value in caption_info.items():
                if key not in ["title", "original_name", "extension"] and not info.get(key) and value:
                    info[key] = value
                    
        post_title = info.get('title')   # prefix & S01 naduvula irukkura name (post thedurathukku)

        format_template = user_data.get('format_template', "{filename}")
        if format_template is None:
            format_template = "{filename}"

        prefix = user_data.get('prefix', None)
        suffix = user_data.get('suffix', None)
        ext_str = (info.get('extension') or raw_ext or 'mkv').lstrip('.').strip()
        if not ext_str:
            ext_str = 'mkv'
        info['extension'] = ext_str

        # --- 1. CAPTION GENERATION (Full Format Template Applied) ---
        cap_info = info.copy()
        for k, v in cap_info.items():
            if isinstance(v, str) and k != 'extension':
                cap_info[k] = v.replace("_", " ")
        
        full_caption_name = renamer.apply_format_template(cap_info, format_template)
        if not full_caption_name.endswith(f".{ext_str}"):
            full_caption_name += f".{ext_str}"

        if "." in full_caption_name:
            cap_base = full_caption_name.rsplit('.', 1)[0]
            cap_ext = f".{full_caption_name.rsplit('.', 1)[1]}"
        else:
            cap_base = full_caption_name
            cap_ext = ""
            
        cap_base = cap_base.replace("_", " ")
            
        if prefix:
            cap_base = f"{prefix} {cap_base}"
        if suffix:
            cap_base = f"{cap_base} {suffix}"
            
        final_caption_name = f"{cap_base}{cap_ext}"
        final_caption_name = " ".join(final_caption_name.split())

        # --- 2. FILENAME GENERATION (Total 60 Characters Limit) ---
        # Prefix, Suffix la irukka underlines azhiyathu. Title, S, E, Q la ulla underlines space aagum.
        title_str = info.get('title', '').replace("_", " ")
        season_str = info.get('season', '').replace("_", " ")
        episode_str = info.get('episode', '').replace("_", " ")
        quality_str = info.get('quality', '').replace("_", " ")
        
        prefix_str = prefix if prefix else ""
        suffix_str = suffix if suffix else ""
        se_str = f"{season_str}{episode_str}"

        # Total 60 characters limit logic
        parts_except_title = []
        if prefix_str: parts_except_title.append(prefix_str)
        if se_str: parts_except_title.append(se_str)
        if quality_str: parts_except_title.append(quality_str)
        if suffix_str: parts_except_title.append(suffix_str)
        
        # Calculate extra length (prefix + SE + quality + extension + spaces)
        extra_len = sum(len(p) for p in parts_except_title) + len(parts_except_title)
        ext_len = len(ext_str) + 1 if ext_str else 0
        
        max_title_len = 60 - extra_len - ext_len
        
        # Cut the title so the entire filename exactly fits 60 characters
        if max_title_len > 0 and len(title_str) > max_title_len:
            title_str = title_str[:max_title_len].strip()
        elif max_title_len <= 0:
            title_str = ""

        file_name_parts = []
        if prefix_str: file_name_parts.append(prefix_str)
        if title_str: file_name_parts.append(title_str)
        if se_str: file_name_parts.append(se_str)
        if quality_str: file_name_parts.append(quality_str)
        if suffix_str: file_name_parts.append(suffix_str)
            
        file_name_core = " ".join(file_name_parts)
        file_name_core = " ".join(file_name_core.split()) # Extra spaces remove panrom

        if not file_name_core.lower().endswith(f".{ext_str.lower()}"):
            new_filename = f"{file_name_core}.{ext_str}"
        else:
            new_filename = file_name_core

        if "." not in new_filename:
            new_filename = f"{new_filename}.{ext_str}"
            
    print(f"[RENAME-DEBUG] raw={media.file_name!r} -> new={new_filename!r}", flush=True)
    
    file_path = f"Renames/{new_filename}"
    files.append(file_path)
    
    await rkn_processing.edit("`Try To Download....`")
    try:
        dl_path = await bot.download_media(message=file, file_name=file_path, progress=progress_for_pyrogram, progress_args=("**📥 Download Started...**", rkn_processing, time.time(), new_filename))
                        
    except Exception as e:     
        await rkn_processing.edit(f"Download Error: {e}")
        return False
        
    try:
        await file.delete()
    except:
        pass
    
    await rkn_processing.edit("`Adding Metadata...`")
    out_path = f"Renames/meta_{new_filename}"
    files.append(out_path)
    
    custom_metadata_title = script.METADATA_TITLE
    audio_lang = user_data.get('audio_lang', None)
    
    # User set panna audio-ah default ah maathum code
    audio_cmd = ""
    if audio_lang:
        import json
        # FFprobe vechu exact stream index kandupudikkum logic
        probe_cmd = f'ffprobe -v quiet -print_format json -show_streams -select_streams a "{file_path}"'
        try:
            probe_proc = await asyncio.create_subprocess_shell(probe_cmd, stdout=asyncio.subprocess.PIPE)
            stdout, _ = await probe_proc.communicate()
            probe_data = json.loads(stdout)
            for stream in probe_data.get("streams", []):
                tags = stream.get("tags", {})
                lang = tags.get("language", "").lower()
                if not lang:
                    lang = tags.get("LANGUAGE", "").lower()
                if lang == audio_lang.lower():
                    stream_index = stream.get("index")
                    audio_cmd = f'-disposition:a 0 -disposition:{stream_index} default '
                    break
        except Exception as e:
            print(f"FFprobe error: {e}")
        
        # Kandupudikka mudila na pazhaiya method backup
        if not audio_cmd:
            audio_cmd = f'-disposition:a 0 -disposition:a:m:language:{audio_lang} default '
    
    cmd = f'ffmpeg -y -i "{file_path}" -c copy -map 0 {audio_cmd}-metadata title="{custom_metadata_title}" -metadata author="{custom_metadata_title}" -metadata encoder="{custom_metadata_title}" -metadata uploader="{custom_metadata_title}" -metadata website="{custom_metadata_title}" -metadata artist="{custom_metadata_title}" -metadata notes="{custom_metadata_title}" -metadata:s:v title="{custom_metadata_title}" -metadata:s:v encoder="{custom_metadata_title}" -metadata:s:a title="{custom_metadata_title}" -metadata:s:a encoder="{custom_metadata_title}" -metadata:s:s title="{custom_metadata_title}" -metadata:s:s encoder="{custom_metadata_title}" "{out_path}"'
    
    proc = await asyncio.create_subprocess_shell(cmd)
    try:
        await proc.communicate()
    except asyncio.CancelledError:
        # Cancel pannina ffmpeg-um nikkanum
        try:
            proc.kill()
        except Exception:
            pass
        raise
    
    final_file_path = file_path
    if os.path.exists(out_path):
        os.remove(file_path)
        final_clean_path = f"Renames/{new_filename}"
        files.append(final_clean_path)
        os.rename(out_path, final_clean_path)
        final_file_path = final_clean_path

    await rkn_processing.edit("`Try To Uploading....`")        
    duration = 0
    try:
        parser = createParser(final_file_path)
        metadata = extractMetadata(parser)
        if metadata and metadata.has("duration"):
            duration = metadata.get('duration').seconds
        if parser:
            parser.close()
    except Exception as e:
        print(f"Error extracting metadata: {e}")
        pass
        
    ph_path = None
    c_caption = user_data.get('caption', None)
    c_thumb = user_data.get('file_id', None)

    if c_caption:
        try:
            caption = c_caption.format(filename=final_caption_name, filesize=humanbytes(media.file_size), duration=convert(duration))
        except Exception as e:             
            await rkn_processing.edit(text=f"Yᴏᴜʀ Cᴀᴩᴛɪᴏɴ Eʀʀᴏʀ Exᴄᴇᴩᴛ Kᴇyᴡᴏʀᴅ Aʀɢᴜᴍᴇɴᴛ ●> ({e})")             
            return False
    else:
        caption = f"**{final_caption_name}**"
 
    if (media.thumbs or c_thumb):
        try:
            if c_thumb:
                ph_path = await bot.download_media(c_thumb) 
            else:
                ph_path = await bot.download_media(media.thumbs[0].file_id)
            
            if ph_path and os.path.exists(ph_path):
                Image.open(ph_path).convert("RGB").save(ph_path)
                img = Image.open(ph_path)
                img.resize((320, 320))
                img.save(ph_path, "JPEG")
        except Exception as e:
            print(f"Error processing thumbnail: {e}")
            ph_path = None

    if ph_path:
        files.append(ph_path)

    upload_type = update.data.split("#")[1]
    
    dump_id = await goku_stark.get_dump(user_id)
    dump_status = await goku_stark.get_dump_status(user_id)

    # --- POST FORWARD: upload start aagum pothu, file-ku MUNNADI title post-a dump-ku anuppum ---
    post_target = int(dump_id) if (dump_id and dump_status) else update.message.chat.id
    posted, post_note = await send_post_for_title(bot, post_title, post_target, user_id)
    state['post'] = posted
    await announce_post(bot, update.message.chat.id, post_title, posted, post_note)   # bot chat-la 10s notice

    if media.file_size > 2000 * 1024 * 1024:
        filw, error = await upload_files(
            app, Config.LOG_CHANNEL, upload_type, final_file_path, 
            ph_path, caption, duration, rkn_processing
        )
        if error:
            await remove_path(ph_path, final_file_path, dl_path)
            await rkn_processing.edit(f"Upload Error: {error}")
            return False
            
        from_chat = filw.chat.id
        mg_id = filw.id
        await asyncio.sleep(2)
        
        if dump_id and dump_status:
            success_msg = await bot.copy_message(int(dump_id), from_chat, mg_id)
            try:
                await bot.send_sticker(chat_id=int(dump_id), sticker=DUMP_STICKER_ID)
            except:
                pass
        else:
            success_msg = await bot.copy_message(update.from_user.id, from_chat, mg_id)
            
        await bot.delete_messages(from_chat, mg_id)
        
    else:
        target_chat = int(dump_id) if (dump_id and dump_status) else update.message.chat.id
        filw, error = await upload_files(
            bot, target_chat, upload_type, final_file_path, 
            ph_path, caption, duration, rkn_processing
        )
        if error:
            await remove_path(ph_path, final_file_path, dl_path)
            await rkn_processing.edit(f"Upload Error: {error}")
            return False
        success_msg = filw
        if dump_id and dump_status:
            try:
                await bot.send_sticker(chat_id=int(dump_id), sticker=DUMP_STICKER_ID)
            except:
                pass

    await remove_path(ph_path, final_file_path, dl_path)
    
    # Message update with 5 seconds auto-delete
    if dump_id and dump_status:
        await rkn_processing.edit(script.DUMP_SENT_TXT)
    else:
        await rkn_processing.edit(script.UPLOAD_SUCCESS_TXT)
        
    await asyncio.sleep(5)
    try:
        await rkn_processing.delete()
    except:
        pass
        
    return True

async def upload_doc(bot, update):
    """Cancel-support wrapper: Cancel click -> download/upload stop, temp files delete, message close."""
    msg = update.message
    original = msg.reply_to_message
    files = []
    cancelled = False
    result = None
    state = {}
    try:
        result, cancelled = await run_cancellable(msg, _upload_doc_impl(bot, update, files, state))
    finally:
        cleanup_files(*files)
        # Upload cancel / fail aana forward pannina post-a dump-la irunthu eduthidum
        if state.get('post'):
            if cancelled or not result:
                await discard_post(bot, state['post'])
            else:
                await confirm_post(state['post'])

    if cancelled:
        try:
            await msg.edit("❌ **Process Cancelled.**")
            await asyncio.sleep(3)
        except Exception:
            pass
        await safe_delete(msg, original)
        return False
    return result

@Client.on_message(filters.private & filters.command("set_type"))
async def set_media_cmd(client, message):
    user_id = message.from_user.id
    current_type = await goku_stark.get_upload_type(user_id)
    
    if current_type == "doc":
        status = "DOCUMENT"
    elif current_type == "video":
        status = "VIDEO"
    else:
        status = "NOT SET"

    buttons = [
        [
            InlineKeyboardButton("📁 Document", callback_data="set_type_doc"),
            InlineKeyboardButton("🎥 Video", callback_data="set_type_video")
        ],
        [
            InlineKeyboardButton("✖️ Cancel", callback_data="close")
        ]
    ]
    await message.reply_text(
        f"**Current Status:** `{status}`\n\n**Select Default Output Format:**\n\nThe file will be automatically renamed using the format you select here.",
        reply_markup=InlineKeyboardMarkup(buttons),
        reply_to_message_id=message.id
    )

@Client.on_callback_query(filters.regex(r"^set_type_"))
async def set_type_callback(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if data == "set_type_doc":
        await goku_stark.set_upload_type(user_id, "doc")
        await callback_query.answer("✅ Default Output set to: DOCUMENT", show_alert=True)
    elif data == "set_type_video":
        await goku_stark.set_upload_type(user_id, "video")
        await callback_query.answer("✅ Default Output set to: VIDEO", show_alert=True)
        
    try:
        await callback_query.message.delete()
        if callback_query.message.reply_to_message:
            await callback_query.message.reply_to_message.delete()
    except:
        pass

@Client.on_message(filters.private & filters.command("mode"))
async def set_mode_cmd(client, message):
    user_id = message.from_user.id
    current_mode = await goku_stark.get_rename_mode(user_id) 
    
    buttons = [
        [
            InlineKeyboardButton("🤖 Auto Rename", callback_data="rename_mode_auto"),
            InlineKeyboardButton("✍️ Manual Rename", callback_data="rename_mode_manual")
        ],
        [
            InlineKeyboardButton("✖️ Cancel", callback_data="close")
        ]
    ]
    await message.reply_text(
        f"**Select Rename Mode:**\n\n**Current Mode:** `{current_mode.upper()}`\n\n**Auto Rename** - The file will be renamed automatically.\n**Manual Rename** - The bot will wait until you enter a new name.",
        reply_markup=InlineKeyboardMarkup(buttons),
        reply_to_message_id=message.id
    )

@Client.on_callback_query(filters.regex(r"^rename_mode_"))
async def rename_mode_callback(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if data == "rename_mode_auto":
        await goku_stark.set_rename_mode(user_id, "auto")
        await callback_query.answer("✅ Mode set to: AUTO RENAME", show_alert=True)
    elif data == "rename_mode_manual":
        await goku_stark.set_rename_mode(user_id, "manual")
        await callback_query.answer("✅ Mode set to: MANUAL RENAME", show_alert=True)
        
    try:
        await callback_query.message.delete()
        if callback_query.message.reply_to_message:
            await callback_query.message.reply_to_message.delete()
    except:
        pass

# --- Prefix and Suffix Commands ---

@Client.on_message(filters.private & filters.command("set_prefix"))
async def set_prefix_cmd(client, message):
    if len(message.command) == 1:
        msg = await message.reply_text("**Example:** `/set_prefix @Goku_Stark`")
        await asyncio.sleep(5)
        try:
            await message.delete()
            await msg.delete()
        except:
            pass
        return
    prefix = message.text.split(" ", 1)[1]
    await goku_stark.set_prefix(message.from_user.id, prefix)
    msg = await message.reply_text(f"✅ Prefix set to: `{prefix}`")
    await asyncio.sleep(5)
    try:
        await message.delete()
        await msg.delete()
    except:
        pass

@Client.on_message(filters.private & filters.command("del_prefix"))
async def del_prefix_cmd(client, message):
    await goku_stark.set_prefix(message.from_user.id, None)
    msg = await message.reply_text("❌ Prefix deleted.")
    await asyncio.sleep(5)
    try:
        await message.delete()
        await msg.delete()
    except:
        pass

@Client.on_message(filters.private & filters.command("set_suffix"))
async def set_suffix_cmd(client, message):
    if len(message.command) == 1:
        msg = await message.reply_text("**Example:** `/set_suffix @Goku_Stark`")
        await asyncio.sleep(5)
        try:
            await message.delete()
            await msg.delete()
        except:
            pass
        return
    suffix = message.text.split(" ", 1)[1]
    await goku_stark.set_suffix(message.from_user.id, suffix)
    msg = await message.reply_text(f"✅ Suffix set to: `{suffix}`")
    await asyncio.sleep(5)
    try:
        await message.delete()
        await msg.delete()
    except:
        pass

@Client.on_message(filters.private & filters.command("del_suffix"))
async def del_suffix_cmd(client, message):
    await goku_stark.set_suffix(message.from_user.id, None)
    msg = await message.reply_text("❌ Suffix deleted.")
    await asyncio.sleep(5)
    try:
        await message.delete()
        await msg.delete()
    except:
        pass
