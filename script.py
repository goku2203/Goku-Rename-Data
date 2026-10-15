class script(object):
    # part of text configuration
    START_TXT = """<b>{}...</b>

<blockquote><b><i>Welcome to the Advanced Rename Bot! 🚀</i></b></blockquote>

<blockquote><b>What I can do:</b>
• <b>Auto & Manual Rename</b> files 📁
• <b>Custom Thumbnails</b> & <b>Captions</b> 🖼️
• <b>Video ↔️ File</b> converter 🔄
• <b>Prefix, Suffix & Auto Format</b> ✨</blockquote>

<blockquote><i>Created By: <b>@Goku_Stark 💖</i></b></blockquote>"""

    ABOUT_TXT = """<b>🤖 MY NAME : {0}
💻 Dᴇᴠᴇʟᴏᴘᴇʀ : <a href="https://t.me/Goku_Stark">Goku Stark</a>
📚 Lɪʙʀᴀʀʏ : <a href="https://github.com/pyrogram">Pyrogram</a>
✏️ Lᴀɴɢᴜᴀɢᴇ : <a href="https://www.python.org/">Python 3</a>
💾 Dᴀᴛᴀʙᴀsᴇ : <a href="https://cloud.mongodb.com/">MongoDB</a>
👑 Oᴡɴᴇʀ : <a href="https://t.me/Goku_Stark">Goku Stark</a></b>"""

    HELP_TXT = """
✏️ <b><u>Hᴏᴡ Tᴏ Rᴇɴᴀᴍᴇ A Fɪʟᴇ</u></b>
<b>•</b> Sᴇɴᴅ ᴀɴʏ ғɪʟᴇ, ᴇɴᴛᴇʀ ᴀ ɴᴇᴡ ғɪʟᴇ ɴᴀᴍᴇ, ᴀɴᴅ sᴇʟᴇᴄᴛ ᴛʜᴇ ғᴏʀᴍᴀᴛ: **Document, Video, or Audio**."""
    
    THUMBNAIL = """
🌌 <b><u>Hᴏᴡ Tᴏ Sᴇᴛ Tʜᴜᴍʙɴɪʟᴇ</u></b>

<b>•></b> Sᴇɴᴅ Aɴy Pʜᴏᴛᴏ Tᴏ Aᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟy Sᴇᴛ Tʜᴜᴍʙɴɪʟᴇ.
<b>•></b> /del_thumb Uꜱᴇ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Tᴏ Dᴇʟᴇᴛᴇ Yᴏᴜʀ Oʟᴅ Tʜᴜᴍʙɴɪʟᴇ.
<b>•></b> /view_thumb Uꜱᴇ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Tᴏ Vɪᴇᴡ Yᴏᴜʀ Cᴜʀʀᴇɴᴛ Tʜᴜᴍʙɴɪʟᴇ.
"""

    CAPTION= """
📑 <b><u>Hᴏᴡ Tᴏ Sᴇᴛ Cᴜꜱᴛᴏᴍ Cᴀᴩᴛɪᴏɴ</u></b>

<b>•></b> /set_caption - Uꜱᴇ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Tᴏ Sᴇᴛ ᴀ Cᴜꜱᴛᴏᴍ Cᴀᴩᴛɪᴏɴ
<b>•></b> /see_caption - Uꜱᴇ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Tᴏ Vɪᴇᴡ Yᴏᴜʀ Cᴜꜱᴛᴏᴍ Cᴀᴩᴛɪᴏɴ
<b>•></b> /del_caption - Uꜱᴇ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Tᴏ Dᴇʟᴇᴛᴇ Yᴏᴜʀ Cᴜꜱᴛᴏᴍ Cᴀᴩᴛɪᴏɴ

Exᴀᴍᴩʟᴇ:-/n
/set_caption 📕 Fɪʟᴇ Nᴀᴍᴇ: {filename}
💾 Sɪᴢᴇ: {filesize}
⏰ Dᴜʀᴀᴛɪᴏɴ: {duration}`
"""

    STATUS_TXT = """<b>⚡ <u>𝐁𝐎𝐓 & 𝐑𝐄𝐍𝐃𝐄𝐑 𝐒𝐘𝐒𝐓𝐄𝐌 𝐒𝐓𝐀𝐓𝐔𝐒</u> ⚡</b>

<blockquote><b>🌐 <i>Render Free Plan Info:</i></b>
• <b>Render Status:</b> <code>Online [STABLE] 🟢</code>
• <b>Web Port:</b> <code>{port}</code> | <b>Ping:</b> <code>{ping} ms</code>
• <b>Bot Uptime:</b> <code>{uptime}</code>
• <b>Task Queue:</b> <code>{queue_status}</code></blockquote>

<blockquote><b>🧠 <i>Container RAM & CPU (Render):</i></b>
• <b>Container RAM:</b> <code>{ram_used} / {ram_total} ({ram_usage}%)</code>
• <b>Bot + FFmpeg RAM:</b> <code>{bot_ram}</code>
• <b>CPU Load:</b> <code>{cpu_usage}%</code></blockquote>

<blockquote><b>💾 <i>Storage & Temp Files:</i></b>
• <b>Temp Folder (Renames):</b> <code>{temp_size} ({temp_files} Files)</code>
• <b>Server Disk Used:</b> <code>{used_disk} / {total_disk} ({disk_usage}%)</code>
• <b>Server Disk Free:</b> <code>{free_disk}</code></blockquote>

<blockquote><b>📡 <i>Network & Database:</i></b>
• <b>Upload (Sent):</b> <code>{sent}</code> ⬆️ | <b>Download:</b> <code>{recv}</code> ⬇️
• <b>Total Users:</b> <code>{total_users}</code> | <b>Banned:</b> <code>{banned_users}</code></blockquote>

<blockquote><i>👑 Powered By: <b>@Goku_Stark</b></i></blockquote>"""
    
    DEV_TXT = """<b><u>Dᴇᴠᴇʟᴏᴩᴇʀꜱ</b></u>
    
» 𝗦𝗢𝗨𝗥𝗖𝗘 𝗖𝗢𝗗𝗘 : <a href=https://t.me/Goku_Stark>Goku Stark</a>"""

    RKN_PROGRESS = """<b>\n\n🎬 **Output:▼**\n<blockquote><b>{5}</b></blockquote>\n\n📦 Sɪᴢᴇ: {1} / {2}\n 📊 Pʀᴏɢʀᴇss: {0}%\n ⚡ Sᴘᴇᴇᴅ: {3}/s\n ⏱️ Eᴛᴀ: {4}\n\n ────[ Pʟᴇᴀsᴇ Wᴀɪᴛ... ]────\n</b>"""

    # Custom Metadata & Tags
    METADATA_TITLE = "@Goku_Stark"
    CUSTOM_TAG = "@Goku_Stark"

    # Force Sub Message
    FORCE_SUB_TEXT = "**Sᴏʀʀy Dᴜᴅᴇ Yᴏᴜ'ʀᴇ Nᴏᴛ Jᴏɪɴᴇᴅ My Cʜᴀɴɴᴇʟ 😐. Sᴏ Pʟᴇᴀꜱᴇ Jᴏɪɴ Oᴜʀ Uᴩᴅᴀᴛᴇ Cʜᴀɴɴᴇʟ Tᴏ Cᴏɴᴛɪɴᴜᴇ**"
    
    # Manual Mode
    FILE_INFO_TXT = """**Sᴇʟᴇᴄᴛ Tʜᴇ Oᴜᴛᴩᴜᴛ Fɪʟᴇ Tyᴩᴇ**\n\n**__ᴍᴇᴅɪᴀ ɪɴꜰᴏ:\n\n◈ ᴏʟᴅ ꜰɪʟᴇ ɴᴀᴍᴇ: `{}`\n\n◈ ᴇxᴛᴇɴꜱɪᴏɴ: `{}`\n◈ ꜰɪʟᴇ ꜱɪᴢᴇ: `{}`\n◈ ᴍɪᴍᴇ ᴛʏᴇᴩ: `{}`\n◈ ᴅᴄ ɪᴅ: `{}`....__**"""

    MANUAL_RENAME_TXT = """**Sᴇʟᴇᴄᴛ Tʜᴇ Oᴜᴛᴩᴜᴛ Fɪʟᴇ Tyᴩᴇ**\n\n**__ᴍᴇᴅɪᴀ ɪɴꜰᴏ:\n\n◈ ᴏʟᴅ ꜰɪʟᴇ ɴᴀᴍᴇ: `{}`\n\n◈ ᴇxᴛᴇɴꜱɪᴏɴ: `{}`\n◈ ꜰɪʟᴇ ꜱɪᴢᴇ: `{}`\n◈ ᴍɪᴍᴇ ᴛʏᴇᴩ: `{}`\n◈ ᴅᴄ ɪᴅ: `{}`....__**"""

