from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from helper.database import digital_botz
from config import Config

@Client.on_message(filters.private & filters.command("settings"))
async def settings_command(client, message):
    user_id = message.from_user.id
    
    # Current Audio Status Edukka
    current_audio = await digital_botz.get_audio_lang(user_id)
    lang_names = {"tam": "Tamil", "tel": "Telugu", "hin": "Hindi", "eng": "English", "mal": "Malayalam"}
    audio_status = lang_names.get(current_audio, "Default (Off)") if current_audio else "Default (Off)"

    buttons = [
        [InlineKeyboardButton("  Audio Settings", callback_data="audio_settings_menu")]
    ]
    
    admin_text = ""
    # Admin mattum Dump Settings paaka mudiyum
    if user_id in Config.ADMIN:
        buttons.append([InlineKeyboardButton("  Dump Settings", callback_data="dump_settings_menu")])
        dump_status = await digital_botz.get_dump_status(user_id)
        dump_txt = "ON  " if dump_status else "OFF  "
        admin_text = f"\n**Dump Status:** `{dump_txt}`"
        
    # Last-la close button
    buttons.append([InlineKeyboardButton("  Close", callback_data="close")])

    await message.reply_text(
        f"**  Settings Menu**\n\n**Audio Status:** `{audio_status}`{admin_text}\n\nClick the button below to change your settings.",
        reply_markup=InlineKeyboardMarkup(buttons),
        reply_to_message_id=message.id 
    )

# Mukkuyamana Maatram: group=2 add pannirukkom
@Client.on_callback_query(filters.regex(r"^back_to_settings$"), group=2)
async def back_to_settings_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    
    # Current Audio Status Edukka
    current_audio = await digital_botz.get_audio_lang(user_id)
    lang_names = {"tam": "Tamil", "tel": "Telugu", "hin": "Hindi", "eng": "English", "mal": "Malayalam"}
    audio_status = lang_names.get(current_audio, "Default (Off)") if current_audio else "Default (Off)"

    buttons = [
        [InlineKeyboardButton("  Audio Settings", callback_data="audio_settings_menu")]
    ]
    
    admin_text = ""
    if user_id in Config.ADMIN:
        buttons.append([InlineKeyboardButton("  Dump Settings", callback_data="dump_settings_menu")])
        dump_status = await digital_botz.get_dump_status(user_id)
        dump_txt = "ON  " if dump_status else "OFF  "
        admin_text = f"\n**Dump Status:** `{dump_txt}`"
        
    buttons.append([InlineKeyboardButton("  Close", callback_data="close")])

    await query.message.edit_text(
        f"**  Settings Menu**\n\n**Audio Status:** `{audio_status}`{admin_text}\n\nClick the button below to change your settings.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# =============== AUDIO SETTINGS ===============
@Client.on_callback_query(filters.regex(r"^audio_settings_menu$"), group=2)
async def audio_settings_menu_cb(client, query: CallbackQuery):
    buttons = [
        [
            InlineKeyboardButton("  Tamil", callback_data="audio_tam"),
            InlineKeyboardButton("  Telugu", callback_data="audio_tel")
        ],
        [
            InlineKeyboardButton("  Hindi", callback_data="audio_hin"),
            InlineKeyboardButton("  English", callback_data="audio_eng")
        ],
        [
            InlineKeyboardButton("  Malayalam", callback_data="audio_mal"),
            InlineKeyboardButton("  Default (Off)", callback_data="audio_default")
        ],
        [
            InlineKeyboardButton("  Back", callback_data="back_to_settings"),
            InlineKeyboardButton("  Close", callback_data="close")
        ]
    ]
    
    current_audio = await digital_botz.get_audio_lang(query.from_user.id)
    lang_names = {"tam": "Tamil", "tel": "Telugu", "hin": "Hindi", "eng": "English", "mal": "Malayalam"}
    current_lang = lang_names.get(current_audio, "Default (Off)") if current_audio else "Default (Off)"
    
    await query.message.edit_text(
        f"**Audio Settings**\n\n**Current Status:** `{current_lang}`\n\nPlease select which audio language should play first in the video player. This will be saved permanently.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^audio_(tam|tel|hin|eng|mal|default)$"), group=2)
async def audio_selection_cb(client, query: CallbackQuery):
    lang_code = query.data.split("_")[1]
    user_id = query.from_user.id
    
    if lang_code == "default":
        await digital_botz.set_audio_lang(user_id, None)
        await query.answer("Audio set to Default (Off)!", show_alert=True)
    else:
        await digital_botz.set_audio_lang(user_id, lang_code)
        lang_names = {"tam": "Tamil", "tel": "Telugu", "hin": "Hindi", "eng": "English", "mal": "Malayalam"}
        selected_lang = lang_names.get(lang_code, lang_code)
        await query.answer(f"Audio set to {selected_lang}!", show_alert=True)
        
    await audio_settings_menu_cb(client, query)


# =============== DUMP SETTINGS (Admin Only) ===============
@Client.on_callback_query(filters.regex(r"^dump_settings_menu$") & filters.user(Config.ADMIN), group=2)
async def dump_settings_menu(client, query: CallbackQuery):
    user_id = query.from_user.id
    dump_status = await digital_botz.get_dump_status(user_id)
    
    status_text = "ON  " if dump_status else "OFF  "
    
    buttons = [
        [
            InlineKeyboardButton("ON  ", callback_data="set_dump_on"),
            InlineKeyboardButton("OFF  ", callback_data="set_dump_off")
        ],
        [
            InlineKeyboardButton("  Back", callback_data="back_to_settings"),
            InlineKeyboardButton("  Close", callback_data="close")
        ]
    ]
    
    await query.message.edit_text(
        f"**Dump Settings**\n\n**Current Status:** `{status_text}`\n\nTurn ON to send files and stickers to the dump channel. Turn OFF to stop.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^set_dump_(on|off)$") & filters.user(Config.ADMIN), group=2)
async def set_dump_status_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    action = query.data.split("_")[2]
    
    if action == "on":
        await digital_botz.set_dump_status(user_id, True)
        await query.answer("Dump is now ON!", show_alert=True)
    else:
        await digital_botz.set_dump_status(user_id, False)
        await query.answer("Dump is now OFF!", show_alert=True)
        
    await dump_settings_menu(client, query)
