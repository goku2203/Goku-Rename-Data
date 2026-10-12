class script(object):
    # part of text configuration
    START_TXT = """<b>Hi {} 👋</b>

<blockquote><b><i>Welcome to the Advanced Rename Bot! 🚀</i></b>

<b>What I can do:</b>
• <b>Auto & Manual Rename</b> files 📁
• <b>Custom Thumbnails</b> & <b>Captions</b> 🖼️
• <b>Video ↔️ File</b> converter 🔄
• <b>Prefix, Suffix & Auto Format</b> ✨</blockquote>

<i>Created By :</i> <b>@Goku_Stark 💖</b>"""

    ABOUT_TXT = """<b>
⦿ 🤖 Mʏ ɴᴀᴍᴇ : {}
⦿ 🖥️ Dᴇᴠᴇʟᴏᴩᴇʀꜱ : {}
⦿ ✏️ Lᴀɴɢᴜᴀɢᴇ: {}
⦿ 💾 Dᴀᴛᴀ Bᴀꜱᴇ: {}
⦿ 👑 Oᴡɴᴇʀ: <a href=https://t.me/Goku_Stark>{}</a></b>"""

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
    
    DEV_TXT = """<b><u>Dᴇᴠᴇʟᴏᴩᴇʀꜱ</b></u>
    
» 𝗦𝗢𝗨𝗥𝗖𝗘 𝗖𝗢𝗗𝗘 : <a href=https://t.me/Goku_Stark>goku-stark-Auto-Rename-Bot</a>"""

    RKN_PROGRESS = """<b>\n\n🎬 **Output:▼**\n<blockquote><b>{5}</b></blockquote>\n\n📦 Sɪᴢᴇ: {1} / {2}\n 📊 Pʀᴏɢʀᴇss: {0}%\n ⚡ Sᴘᴇᴇᴅ: {3}/s\n ⏱️ Eᴛᴀ: {4}\n\n ────[ Pʟᴇᴀsᴇ Wᴀɪᴛ... ]────\n</b>"""

    # Custom Metadata & Tags
    METADATA_TITLE = "@Goku_Stark"
    CUSTOM_TAG = "@Goku_Stark"

    # Force Sub Message
    FORCE_SUB_TEXT = "**Sᴏʀʀy Dᴜᴅᴇ Yᴏᴜ'ʀᴇ Nᴏᴛ Jᴏɪɴᴇᴅ My Cʜᴀɴɴᴇʟ 😐. Sᴏ Pʟᴇᴀꜱᴇ Jᴏɪɴ Oᴜʀ Uᴩᴅᴀᴛᴇ Cʜᴀɴɴᴇʟ Tᴏ Cᴏɴᴛɪɴᴜᴇ**"
    
    # Manual Mode
    FILE_INFO_TXT = """**Sᴇʟᴇᴄᴛ Tʜᴇ Oᴜᴛᴩᴜᴛ Fɪʟᴇ Tyᴩᴇ**\n\n**__ᴍᴇᴅɪᴀ ɪɴꜰᴏ:\n\n◈ ᴏʟᴅ ꜰɪʟᴇ ɴᴀᴍᴇ: `{}`\n\n◈ ᴇxᴛᴇɴꜱɪᴏɴ: `{}`\n◈ ꜰɪʟᴇ ꜱɪᴢᴇ: `{}`\n◈ ᴍɪᴍᴇ ᴛʏᴇᴩ: `{}`\n◈ ᴅᴄ ɪᴅ: `{}`....__**"""

    MANUAL_RENAME_TXT = """**Sᴇʟᴇᴄᴛ Tʜᴇ Oᴜᴛᴩᴜᴛ Fɪʟᴇ Tyᴩᴇ**\n\n**__ᴍᴇᴅɪᴀ ɪɴꜰᴏ:\n\n◈ ᴏʟᴅ ꜰɪʟᴇ ɴᴀᴍᴇ: `{}`\n\n◈ ᴇxᴛᴇɴꜱɪᴏɴ: `{}`\n◈ ꜰɪʟᴇ ꜱɪᴢᴇ: `{}`\n◈ ᴍɪᴍᴇ ᴛʏᴇᴩ: `{}`\n◈ ᴅᴄ ɪᴅ: `{}`....__**"""
