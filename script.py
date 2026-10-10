class script(object):
    # part of text configuration
    START_TXT = """<b>Hi {} 👋\n
    "Welcome to the Advanced Rename Bot! 🚀"
    
    "What I can do:
    • Auto and Manual Rename your files easily 📁
    • Change or add custom thumbnails 🖼️
    • Convert Video to File & File to Video 🔄
    • Set Prefix & Suffix ✨
    • Powerful Auto Rename Format ⚡
    • Set custom captions for your files 📝"

    Created By : @Goku_Stark 💞</b>"""

    ABOUT_TXT = """<b>
⦿ 🤖 ᴍy ɴᴀᴍᴇ : {}
⦿ 🖥️ Dᴇᴠᴇʟᴏᴩᴇʀꜱ : {}
⦿ ✏️ Lᴀɴɢᴜᴀɢᴇ: {}
⦿ 💾 Dᴀᴛᴀ Bᴀꜱᴇ: {}
⦿ 📊 ᴠᴇʀsɪᴏɴ: <a href=https://t.me/Goku_Stark>{}</a></b>"""

    HELP_TXT = """
✏️ <b><u>Hᴏᴡ Tᴏ Rᴇɴᴀᴍᴇ A Fɪʟᴇ</u></b>
<b>•</b> Send any file, enter a new file name, and select the format: **Document, Video, or Audio**."""
    
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

    BOT_STATUS = """
⚡️ ʙᴏᴛ sᴛᴀᴛᴜs ⚡️

⌚️ ʙᴏᴛ ᴜᴩᴛɪᴍᴇ: `{}`
👭 ᴛᴏᴛᴀʟ ᴜsᴇʀꜱ: `{}`
💸 ᴛᴏᴛᴀʟ ᴘʀᴇᴍɪᴜᴍ ᴜsᴇʀs: `{}`
֍ ᴜᴘʟᴏᴀᴅ: `{}`
⊙ ᴅᴏᴡɴʟᴏᴀᴅ: `{}`
"""

    LIVE_STATUS = """
⚡ ʟɪᴠᴇ sᴇʀᴠᴇʀ sᴛᴀᴛᴜs ⚡

ᴜᴘᴛɪᴍᴇ: `{}`
ᴄᴘᴜ: `{}%`
ʀᴀᴍ: `{}%` 
ᴛᴏᴛᴀʟ ᴅɪsᴋ: `{}`
ᴜsᴇᴅ sᴘᴀᴄᴇ: `{} {}%`
ғʀᴇᴇ sᴘᴀᴄᴇ: `{}`
ᴜᴘʟᴏᴀᴅ: `{}`
ᴅᴏᴡɴʟᴏᴀᴅ: `{}`
V𝟹.𝟶.𝟶 [STABLE]
"""
    
    DEV_TXT = """<b><u>Sᴩᴇᴄɪᴀʟ Tʜᴀɴᴋꜱ & Dᴇᴠᴇʟᴏᴩᴇʀꜱ</b></u>
    
» 𝗦𝗢𝗨𝗥𝗖𝗘 𝗖𝗢𝗗𝗘 : <a href=https://github.com/DigitalBotz/Digital-Auto-Rename-Bot>Digital-Auto-Rename-Bot</a>

• ❣️ <a href=https://github.com/RknDeveloper>RknDeveloper</a>
• ❣️ <a href=https://github.com/DigitalBotz>DigitalBotz</a>
• ❣️️ <a href=https://github.com/JayMahakal98>Jay Mahakal</a> """

    RKN_PROGRESS = """<b>\n\n🎬 Output: **{5}** 📦 𝚂𝙸𝚉𝙴: {1} / {2}\n 📊 𝙿𝚁𝙾𝙶𝚁𝙴𝚂𝚂: {0}%\n ⚡ 𝚂𝙿𝙴𝙴𝙳: {3}/s\n ⏱️ 𝙴𝚃𝙰: {4}\n\n ────[ Please wait... ]────</b>"""

    # Custom Metadata & Tags
    METADATA_TITLE = "@Goku_Stark"
    CUSTOM_TAG = "@Goku_Stark"

    # Force Sub Message
    FORCE_SUB_TEXT = "**Sᴏʀʀy Dᴜᴅᴇ Yᴏᴜ'ʀᴇ Nᴏᴛ Jᴏɪɴᴇᴅ My Cʜᴀɴɴᴇʟ 😐. Sᴏ Pʟᴇᴀꜱᴇ Jᴏɪɴ Oᴜʀ Uᴩᴅᴀᴛᴇ Cʜᴀɴɴᴇʟ Tᴏ Cᴏɴᴛɪɴᴜᴇ**"
    
    # Manual Mode
    FILE_INFO_TXT = """**Sᴇʟᴇᴄᴛ Tʜᴇ Oᴜᴛᴩᴜᴛ Fɪʟᴇ Tyᴩᴇ**\n\n**__ᴍᴇᴅɪᴀ ɪɴꜰᴏ:\n\n◈ ᴏʟᴅ ꜰɪʟᴇ ɴᴀᴍᴇ: `{}`\n\n◈ ᴇxᴛᴇɴꜱɪᴏɴ: `{}`\n◈ ꜰɪʟᴇ ꜱɪᴢᴇ: `{}`\n◈ ᴍɪᴍᴇ ᴛʏᴇᴩ: `{}`\n◈ ᴅᴄ ɪᴅ: `{}`....__**"""

    MANUAL_RENAME_TXT = """**Sᴇʟᴇᴄᴛ Tʜᴇ Oᴜᴛᴩᴜᴛ Fɪʟᴇ Tyᴩᴇ**\n\n**__ᴍᴇᴅɪᴀ ɪɴꜰᴏ:\n\n◈ ᴏʟᴅ ꜰɪʟᴇ ɴᴀᴍᴇ: `{}`\n\n◈ ᴇxᴛᴇɴꜱɪᴏɴ: `{}`\n◈ ꜰɪʟᴇ ꜱɪᴢᴇ: `{}`\n◈ ᴍɪᴍᴇ ᴛʏᴇᴩ: `{}`\n◈ ᴅᴄ ɪᴅ: `{}`....__**"""
