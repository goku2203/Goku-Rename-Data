# (c) @RknDeveloperr
# Rkn Developer 
# Don't Remove Credit 😔
# Telegram Channel @RknDeveloper & @Rkn_Botz
# Developer @RknDeveloperr
# Special Thanks To @ReshamOwner
# Update Channel @Digital_Botz & @DigitalBotz_Support
"""
Apache License 2.0
Copyright (c) 2025 @Digital_Botz

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Telegram Link : https://t.me/Digital_Botz 
Repo Link : https://github.com/DigitalBotz/Digital-Auto-Rename-Bot
License Link : https://github.com/DigitalBotz/Digital-Auto-Rename-Bot/blob/main/LICENSE
"""

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

    button = [[InlineKeyboardButton("📁 Dᴏᴄᴜᴍᴇɴᴛ",callback_data = "upload#document")]]
    if message.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
        button.append([InlineKeyboardButton("🎥 Vɪᴅᴇᴏ", callback_data = "upload#video")])
    elif message.media == MessageMediaType.AUDIO:
        button.append([InlineKeyboardButton("🎵 Aᴜᴅɪᴏ", callback_data = "upload#audio")])
        
    await message.reply(
            text=f"**Sᴇʟᴇᴄᴛ Tʜᴇ Oᴜᴛᴩᴜᴛ Fɪʟᴇ Tyᴩᴇ**\n\n**__ᴍᴇᴅɪᴀ ɪɴꜰᴏ:\n\n◈ ᴏʟᴅ ꜰɪʟᴇ ɴᴀᴍᴇ: `{filename}`\n\n◈ ᴇxᴛᴇɴꜱɪᴏɴ: `{extension_type.upper()}`\n◈ ꜰɪʟᴇ ꜱɪᴢᴇ: `{filesize}`\n◈ ᴍɪᴍᴇ ᴛʏᴇᴩ: `{mime_type}`\n◈ ᴅᴄ ɪᴅ: `{dcid}`....__**",        
            reply_to_message_id=message.id,
            reply_markup=InlineKeyboardMarkup(button)
        )

async def upload_files(bot, sender_id, upload_type, file_path, ph_path, caption, duration, rkn_processing):
    """
    Unified function to upload files based on type
    - Supports both 2GB and 4GB files
    - Uses same function for all file sizes
    - Handles document, video, and audio files
    """
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
        # Return error if upload fails
        return None, str(e)

renamer = EnhancedAutoRenamer()

async def upload_doc(bot, update):
    rkn_processing = await update.message.edit("`Processing...`")
        
    user_id = int(update.message.chat.id) 
    new_name = update.message.text

    # msg file location 
    file = update.message.reply_to_message
    if not file:
        return await rkn_processing.edit("Error: Original file message is missing or deleted! Please resend the file.")
    media = getattr(file, file.media.value)

    
    # Extract information
    info = renamer.extract_all_info(media.file_name)

    user_data = await digital_botz.get_user_data(user_id)
    format_template = user_data.get('format_template', "{filename}")
    if format_template is None:
        format_template = "{filename}"
    
    # Apply user's format template
    new_name = renamer.apply_format_template(info, format_template)
    
    # Add extension if not present
    if not new_name.endswith(f".{info['extension']}"):
        new_name += f".{info['extension']}"
        
    new_filename = new_name
    print(f"[RENAME-DEBUG] raw={media.file_name!r} -> new={new_filename!r}")
        
    # File paths for download
    file_path = f"Renames/{new_filename}"
    
    await rkn_processing.edit("`Try To Download....`")    
    try:            
        dl_path = await bot.download_media(message=file, file_name=file_path, progress=progress_for_pyrogram, progress_args=(DOWNLOAD_TEXT, rkn_processing, time.time()))                    
    except Exception as e:        
        return await rkn_processing.edit(f"Download Error: {e}")
    
    await rkn_processing.edit("`Adding Metadata...`")
    out_path = f"Renames/meta_{new_filename}"
    
    # Using your specific username for ALL metadata titles instead of the full filename
    custom_metadata_title = "@anime_love9"
    
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
             # adding custom caption 
             caption = c_caption.format(filename=new_filename, filesize=humanbytes(media.file_size), duration=convert(duration))
         except Exception as e:             
             return await rkn_processing.edit(text=f"Yᴏᴜʀ Cᴀᴩᴛɪᴏɴ Eʀʀᴏʀ Exᴄᴇᴩᴛ Kᴇyᴡᴏʀᴅ Aʀɢᴜᴍᴇɴᴛ ●> ({e})")             
    else:
         caption = f"**{new_filename}**"
 
    if (media.thumbs or c_thumb):
         # downloading thumbnail path
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
    
    # Use the correct file path based on metadata mode
    final_file_path = file_path    
    if media.file_size > 2000 * 1024 * 1024:
        # Upload file using unified function for large files
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
        # Upload file using unified function for regular files
        filw, error = await upload_files(
            bot, update.message.chat.id, upload_type, final_file_path, 
            ph_path, caption, duration, rkn_processing
        )
                   
        if error:            
            await remove_path(ph_path, file_path, dl_path)
            return await rkn_processing.edit(f"Upload Error: {error}")        

    # Clean up files
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
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^set_type_"))
async def set_type_callback(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if data == "set_type_doc":
        await digital_botz.set_upload_type(user_id, "doc")
        await callback_query.message.edit_text("✅ Default Output set to: **DOCUMENT**\n\nIni automatic ah file Document ah convert aagum!")
    elif data == "set_type_video":
        await digital_botz.set_upload_type(user_id, "video")
        await callback_query.message.edit_text("✅ Default Output set to: **VIDEO**\n\nIni automatic ah file Video ah convert aagum!")

# @RknDeveloper
# ✅ Team-RknDeveloper
# Rkn Developer 
# Don't Remove Credit 😔
# Telegram Channel @RknDeveloper & @Rkn_Botz
# Developer @RknDeveloperr
# Special Thanks To @ReshamOwner
# Update Channel @Digital_Botz & @DigitalBotz_Support
