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
from helper.utils import progress_for_pyrogram, convert, humanbytes, add_prefix_suffix, remove_path
from helper.database import digital_botz
from config import Config
from script import script
from plugins.auto_rename import EnhancedAutoRenamer

# extra imports
from asyncio import sleep
import os, time, asyncio

UPLOAD_TEXT = """Uploading Started...."""
DOWNLOAD_TEXT = """Download Started..."""

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
    
    upload_type = await digital_botz.get_upload_type(user_id)
    rename_mode = await digital_botz.get_rename_mode(user_id)
    
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
        text=script.MANUAL_RENAME_TXT.format(filename, filesize),
        reply_to_message_id=message.id,
        reply_markup=ForceReply(True)
    )

@Client.on_message(filters.private & filters.text & filters.reply)
async def custom_rename_handler(client, message):
    prompt_msg = message.reply_to_message
    
    # 1. Reply pandrathu namma bot oda prompt msg thana nu text ah vachu check pandrom
    if not prompt_msg.text or "ᴇɴᴛᴇʀ ɴᴇᴡ ꜰɪʟᴇ ɴᴀᴍᴇ" not in prompt_msg.text:
        return
    
    # 2. Original file msg ah edukurom
    file_msg = prompt_msg.reply_to_message
    if not file_msg or not file_msg.media:
        # Oruvela telegram cache la illana API moolama edukurom
        file_msg = await client.get_messages(message.chat.id, prompt_msg.reply_to_message_id)
        if not file_msg or not file_msg.media:
            return await message.reply_text("❌ Original file kedaikala! Marubadiyum file ah anuppunga.")
            
    custom_name = message.text
    user_id = message.from_user.id
    
    # 3. User set_type pannirukkangala nu check pandrom
    upload_type = await digital_botz.get_upload_type(user_id)
    if not upload_type:
        return await message.reply_text("❌ Default Output Format set aagala!\n\nFirst `/set_type` command use panni Document or Video select pannunga, appuram file anuppunga.")
        
    processing_msg = await message.reply("`Please Wait...`", reply_to_message_id=message.id)
    
    # File ah link pandrom upload_doc kku
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
                progress_args=(UPLOAD_TEXT, rkn_processing, time.time()))
        
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

async def upload_doc(bot, update):
    rkn_processing = await update.message.edit("`Processing...`")
        
    user_id = int(update.message.chat.id) 

    file = update.message.reply_to_message
    if not file:
        return await rkn_processing.edit("Error: Original file message is missing or deleted! Please resend the file.")
    media = getattr(file, file.media.value)
    
    # Custom name irukka nu check pandrom
    custom_name = getattr(update, "custom_name", None)
    user_data = await digital_botz.get_user_data(user_id)
    
    if custom_name:
        new_name = custom_name
        # Oruvela neenga extension (.mkv) poda marantha automatic ah add pannum
        if "." not in new_name:
            info = renamer.extract_all_info(media.file_name)
            new_name += f".{info['extension']}"
    else:
        info = renamer.extract_all_info(media.file_name)
        format_template = user_data.get('format_template', "{filename}")
        if format_template is None:
            format_template = "{filename}"
        new_name = renamer.apply_format_template(info, format_template)
        if not new_name.endswith(f".{info['extension']}"):
            new_name += f".{info['extension']}"
        
    new_filename = new_name
    print(f"[RENAME-DEBUG] raw={media.file_name!r} -> new={new_filename!r}")
        
    file_path = f"Renames/{new_filename}"
    
    # Ithukku keela irukka code (Try To Download...) apdiye thodarum...
    await rkn_processing.edit("`Try To Download....`")
    try:            
        dl_path = await bot.download_media(message=file, file_name=file_path, progress=progress_for_pyrogram, progress_args=(DOWNLOAD_TEXT, rkn_processing, time.time()))                    
    except Exception as e:        
        return await rkn_processing.edit(f"Download Error: {e}")
    
    await rkn_processing.edit("`Adding Metadata...`")
    out_path = f"Renames/meta_{new_filename}"
    
    # Using specific username from script for ALL metadata titles instead of the full filename
    custom_metadata_title = script.METADATA_TITLE
    
    cmd = f'ffmpeg -y -i "{file_path}" -c copy -map 0 -metadata title="{custom_metadata_title}" -metadata:s:v title="{custom_metadata_title}" -metadata:s:a title="{custom_metadata_title}" -metadata:s:s title="{custom_metadata_title}" "{out_path}"'
    
    proc = await asyncio.create_subprocess_shell(cmd)
    await proc.communicate()
    
    if os.path.exists(out_path):
        os.remove(file_path)
        final_clean_path = f"Renames/{new_filename}"
        os.rename(out_path, final_clean_path)
        final_file_path = final_clean_path

    await rkn_processing.edit("`Try To Uploading....`")        
    duration = 0
    try:
        parser = createParser(file_path)
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
             caption = c_caption.format(filename=new_filename, filesize=humanbytes(media.file_size), duration=convert(duration))
         except Exception as e:             
             return await rkn_processing.edit(text=f"Yᴏᴜʀ Cᴀᴩᴛɪᴏɴ Eʀʀᴏʀ Exᴄᴇᴩᴛ Kᴇyᴡᴏʀᴅ Aʀɢᴜᴍᴇɴᴛ ●> ({e})")             
    else:
         caption = f"**{new_filename}**"
 
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

    upload_type = update.data.split("#")[1]
    
    final_file_path = file_path    
    if media.file_size > 2000 * 1024 * 1024:
        filw, error = await upload_files(
            app, Config.LOG_CHANNEL, upload_type, final_file_path, 
            ph_path, caption, duration, rkn_processing
        )

        if error:            
            await remove_path(ph_path, file_path, dl_path)
            return await rkn_processing.edit(f"Upload Error: {error}")
        
        from_chat = filw.chat.id
        mg_id = filw.id
        await asyncio.sleep(2)
        await bot.copy_message(update.from_user.id, from_chat, mg_id)
        await bot.delete_messages(from_chat, mg_id)        
    else:
        filw, error = await upload_files(
            bot, update.message.chat.id, upload_type, final_file_path, 
            ph_path, caption, duration, rkn_processing
        )
                   
        if error:            
            await remove_path(ph_path, file_path, dl_path)
            return await rkn_processing.edit(f"Upload Error: {error}")        

    await remove_path(ph_path, file_path, dl_path)
    return await rkn_processing.edit("Uploaded Successfully....")

@Client.on_message(filters.private & filters.command("set_type"))
async def set_media_cmd(client, message):
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
        "**Select Default Output Format:**\n\nIthula neenga select pandra format la thaan ini automatic ah file veliya varum.",
        reply_markup=InlineKeyboardMarkup(buttons),
        reply_to_message_id=message.id # Ithu command ah track panna
    )

@Client.on_callback_query(filters.regex(r"^set_type_"))
async def set_type_callback(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if data == "set_type_doc":
        await digital_botz.set_upload_type(user_id, "doc")
        await callback_query.answer("✅ Default Output set to: DOCUMENT", show_alert=True)
    elif data == "set_type_video":
        await digital_botz.set_upload_type(user_id, "video")
        await callback_query.answer("✅ Default Output set to: VIDEO", show_alert=True)
        
    # User anupina command um, bot reply um delete aagum
    try:
        await callback_query.message.delete()
        if callback_query.message.reply_to_message:
            await callback_query.message.reply_to_message.delete()
    except:
        pass

@Client.on_message(filters.private & filters.command("mode"))
async def set_mode_cmd(client, message):
    user_id = message.from_user.id
    # Database la irunthu current mode ah edukurom
    current_mode = await digital_botz.get_rename_mode(user_id) 
    
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
        f"**Select Rename Mode:**\n\n**Current Mode:** `{current_mode.upper()}`\n\n**Auto Rename** - Automatic ah file rename aagum.\n**Manual Rename** - Neenga name type pandra varai wait pannum.",
        reply_markup=InlineKeyboardMarkup(buttons),
        reply_to_message_id=message.id
    )

@Client.on_callback_query(filters.regex(r"^rename_mode_"))
async def rename_mode_callback(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if data == "rename_mode_auto":
        await digital_botz.set_rename_mode(user_id, "auto")
        await callback_query.answer("✅ Mode set to: AUTO RENAME", show_alert=True)
    elif data == "rename_mode_manual":
        await digital_botz.set_rename_mode(user_id, "manual")
        await callback_query.answer("✅ Mode set to: MANUAL RENAME", show_alert=True)
        
    # User anupina command um, bot reply um delete aagum
    try:
        await callback_query.message.delete()
        if callback_query.message.reply_to_message:
            await callback_query.message.reply_to_message.delete()
    except:
        pass
