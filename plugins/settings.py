from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from helper.database import goku_stark
from config import Config

@Client.on_message(filters.private & filters.command("settings"))
async def settings_command(client, message):
    await send_settings_menu(message.from_user.id, message)

@Client.on_callback_query(filters.regex(r"^back_to_settings$"), group=2)
async def back_to_settings_cb(client, query: CallbackQuery):
    await send_settings_menu(query.from_user.id, query.message, is_query=True)

async def send_settings_menu(user_id, message, is_query=False):
    current_audio = await goku_stark.get_audio_lang(user_id)
    lang_names = {"tam": "Tamil", "tel": "Telugu", "hin": "Hindi", "eng": "English", "mal": "Malayalam"}
    audio_status = lang_names.get(current_audio, "Default (Off)") if current_audio else "Default (Off)"

    buttons = [
        [InlineKeyboardButton("⚙️ Audio Settings", callback_data="audio_settings_menu")],
        [
            InlineKeyboardButton("📝 Prefix", callback_data="prefix_menu"),
            InlineKeyboardButton("📝 Suffix", callback_data="suffix_menu")
        ],
        [InlineKeyboardButton("📝 Caption", callback_data="caption_menu")]
    ]

    admin_text = ""
    if user_id in Config.ADMIN:
        buttons[-1].append(InlineKeyboardButton("🗑️ Dump", callback_data="dump_settings_menu"))
        dump_status = await goku_stark.get_dump_status(user_id)
        dump_txt = "ON 🟢" if dump_status else "OFF 🔴"
        admin_text = f"\n**Dump Status:** `{dump_txt}`"

    buttons.append([InlineKeyboardButton("✖️ Close", callback_data="close")])

    text = f"**⚙️ Settings Menu**\n\n**Audio Status:** `{audio_status}`{admin_text}\n\nClick the buttons below to manage your settings."

    if is_query:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), reply_to_message_id=message.id)


# =============== PREFIX MENU ===============
@Client.on_callback_query(filters.regex(r"^prefix_menu$"), group=2)
async def prefix_menu_cb(client, query: CallbackQuery):
    buttons = [
        [
            InlineKeyboardButton("✏️ Set Prefix", callback_data="set_prefix_btn"),
            InlineKeyboardButton("👁️ View Prefix", callback_data="view_prefix_btn")
        ],
        [InlineKeyboardButton("🗑️ Delete Prefix", callback_data="del_prefix_btn")],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back_to_settings"),
            InlineKeyboardButton("✖️ Close", callback_data="close")
        ]
    ]
    await query.message.edit_text("**📝 Prefix Settings:**\n\nSelect an option below:", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^(set|view|del)_prefix_btn$"), group=2)
async def prefix_actions(client, query: CallbackQuery):
    action = query.data.split("_")[0]
    user_id = query.from_user.id
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data="prefix_menu"), InlineKeyboardButton("✖️ Close", callback_data="close")]]

    if action == "set":
        text = "**✏️ To Set Prefix:**\n\nUse this command in chat:\n`/set_prefix YourPrefix`\n\nExample: `/set_prefix @Goku_Stark`"
    elif action == "view":
        prefix = await goku_stark.get_prefix(user_id)
        text = f"**👁️ Current Prefix:** `{prefix if prefix else 'No Prefix Set'}`"
    elif action == "del":
        await goku_stark.set_prefix(user_id, None)
        text = "🗑️ **Prefix deleted successfully!**"

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# =============== SUFFIX MENU ===============
@Client.on_callback_query(filters.regex(r"^suffix_menu$"), group=2)
async def suffix_menu_cb(client, query: CallbackQuery):
    buttons = [
        [
            InlineKeyboardButton("✏️ Set Suffix", callback_data="set_suffix_btn"),
            InlineKeyboardButton("👁️ View Suffix", callback_data="view_suffix_btn")
        ],
        [InlineKeyboardButton("🗑️ Delete Suffix", callback_data="del_suffix_btn")],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back_to_settings"),
            InlineKeyboardButton("✖️ Close", callback_data="close")
        ]
    ]
    await query.message.edit_text("**📝 Suffix Settings:**\n\nSelect an option below:", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^(set|view|del)_suffix_btn$"), group=2)
async def suffix_actions(client, query: CallbackQuery):
    action = query.data.split("_")[0]
    user_id = query.from_user.id
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data="suffix_menu"), InlineKeyboardButton("✖️ Close", callback_data="close")]]

    if action == "set":
        text = "**✏️ To Set Suffix:**\n\nUse this command in chat:\n`/set_suffix YourSuffix`\n\nExample: `/set_suffix @Goku_Stark`"
    elif action == "view":
        suffix = await goku_stark.get_suffix(user_id)
        text = f"**👁️ Current Suffix:** `{suffix if suffix else 'No Suffix Set'}`"
    elif action == "del":
        await goku_stark.set_suffix(user_id, None)
        text = "🗑️ **Suffix deleted successfully!**"

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# =============== CAPTION MENU ===============
@Client.on_callback_query(filters.regex(r"^caption_menu$"), group=2)
async def caption_menu_cb(client, query: CallbackQuery):
    buttons = [
        [
            InlineKeyboardButton("✏️ Set Caption", callback_data="set_caption_btn"),
            InlineKeyboardButton("👁️ View Caption", callback_data="view_caption_btn")
        ],
        [InlineKeyboardButton("🗑️ Delete Caption", callback_data="del_caption_btn")],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back_to_settings"),
            InlineKeyboardButton("✖️ Close", callback_data="close")
        ]
    ]
    await query.message.edit_text("**📝 Caption Settings:**\n\nSelect an option below:", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^(set|view|del)_caption_btn$"), group=2)
async def caption_actions(client, query: CallbackQuery):
    action = query.data.split("_")[0]
    user_id = query.from_user.id
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data="caption_menu"), InlineKeyboardButton("✖️ Close", callback_data="close")]]

    if action == "set":
        text = "**✏️ To Set Caption:**\n\nUse this command in chat:\n`/set_caption YourCaption`\n\nSupported variables: `{filename}`, `{filesize}`, `{duration}`"
    elif action == "view":
        caption = await goku_stark.get_caption(user_id)
        text = f"**👁️ Current Caption:**\n`{caption if caption else 'No Caption Set'}`"
    elif action == "del":
        await goku_stark.set_caption(user_id, None)
        text = "🗑️ **Caption deleted successfully!**"

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# =============== DUMP SETTINGS (Admin Only) ===============
@Client.on_callback_query(filters.regex(r"^dump_settings_menu$") & filters.user(Config.ADMIN), group=2)
async def dump_settings_menu(client, query: CallbackQuery):
    user_id = query.from_user.id
    dump_status = await goku_stark.get_dump_status(user_id)
    status_text = "ON 🟢" if dump_status else "OFF 🔴"

    buttons = [
        [
            InlineKeyboardButton("Turn ON 🟢", callback_data="set_dump_on"),
            InlineKeyboardButton("Turn OFF 🔴", callback_data="set_dump_off")
        ],
        [
            InlineKeyboardButton("✏️ Set Dump", callback_data="set_dump_id_btn"),
            InlineKeyboardButton("👁️ View Dump", callback_data="view_dump_id_btn")
        ],
        [InlineKeyboardButton("🗑️ Delete Dump", callback_data="del_dump_id_btn")],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back_to_settings"),
            InlineKeyboardButton("✖️ Close", callback_data="close")
        ]
    ]
    await query.message.edit_text(
        f"**🗑️ Dump Settings**\n\n**Current Status:** `{status_text}`\n\nTurn ON to send files to the dump channel. Turn OFF to stop.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^set_dump_(on|off)$") & filters.user(Config.ADMIN), group=2)
async def set_dump_status_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    action = query.data.split("_")[2]

    if action == "on":
        await goku_stark.set_dump_status(user_id, True)
        await query.answer("Dump is now ON!")
    else:
        await goku_stark.set_dump_status(user_id, False)
        await query.answer("Dump is now OFF!")
        
    await dump_settings_menu(client, query)

@Client.on_callback_query(filters.regex(r"^(set|view|del)_dump_id_btn$") & filters.user(Config.ADMIN), group=2)
async def dump_id_actions(client, query: CallbackQuery):
    action = query.data.split("_")[0]
    user_id = query.from_user.id
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data="dump_settings_menu"), InlineKeyboardButton("✖️ Close", callback_data="close")]]

    if action == "set":
        text = "**✏️ To Set Dump Channel:**\n\nUse this command in chat:\n`/dump -1001234567890`"
    elif action == "view":
        dump_id = await goku_stark.get_dump(user_id)
        text = f"**👁️ Current Dump ID:** `{dump_id if dump_id else 'Not Set'}`"
    elif action == "del":
        await goku_stark.set_dump(user_id, None)
        text = "🗑️ **Dump ID deleted successfully!**"

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# =============== AUDIO SETTINGS ===============
@Client.on_callback_query(filters.regex(r"^audio_settings_menu$"), group=2)
async def audio_settings_menu_cb(client, query: CallbackQuery):
    buttons = [
        [
            InlineKeyboardButton("🟢 Tamil", callback_data="audio_tam"),
            InlineKeyboardButton("🟢 Telugu", callback_data="audio_tel")
        ],
        [
            InlineKeyboardButton("🟢 Hindi", callback_data="audio_hin"),
            InlineKeyboardButton("🟢 English", callback_data="audio_eng")
        ],
        [
            InlineKeyboardButton("🟢 Malayalam", callback_data="audio_mal"),
            InlineKeyboardButton("🔴 Default (Off)", callback_data="audio_default")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back_to_settings"),
            InlineKeyboardButton("✖️ Close", callback_data="close")
        ]
    ]
    
    current_audio = await goku_stark.get_audio_lang(query.from_user.id)
    lang_names = {"tam": "Tamil", "tel": "Telugu", "hin": "Hindi", "eng": "English", "mal": "Malayalam"}
    current_lang = lang_names.get(current_audio, "Default (Off)") if current_audio else "Default (Off)"
    
    await query.message.edit_text(
        f"**⚙️ Audio Settings**\n\n**Current Status:** `{current_lang}`\n\nPlease select which audio language should play first.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^audio_(tam|tel|hin|eng|mal|default)$"), group=2)
async def audio_selection_cb(client, query: CallbackQuery):
    lang_code = query.data.split("_")[1]
    user_id = query.from_user.id
    
    if lang_code == "default":
        await goku_stark.set_audio_lang(user_id, None)
        await query.answer("Audio set to Default (Off)!")
    else:
        await goku_stark.set_audio_lang(user_id, lang_code)
        lang_names = {"tam": "Tamil", "tel": "Telugu", "hin": "Hindi", "eng": "English", "mal": "Malayalam"}
        selected_lang = lang_names.get(lang_code, lang_code)
        await query.answer(f"Audio set to {selected_lang}!")
        
    await audio_settings_menu_cb(client, query)
