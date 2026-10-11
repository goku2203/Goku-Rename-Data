from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from helper.database import digital_botz

@Client.on_message(filters.private & filters.command("set_audio"))
async def set_audio_command(client, message):
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
        ]
    ]
    await message.reply_text(
        "**Audio Settings**\n\nPlease select which audio language should play first in the video player. This will be saved permanently:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^audio_"))
async def audio_callback(client, query: CallbackQuery):
    lang_code = query.data.split("_")[1]
    user_id = query.from_user.id
    
    if lang_code == "default":
        await digital_botz.set_audio_lang(user_id, None)
        await query.answer("Audio set to Default!", show_alert=True)
        await query.message.edit_text("Audio language preference removed. Normal default audio will play.")
    else:
        await digital_botz.set_audio_lang(user_id, lang_code)
        lang_names = {"tam": "Tamil", "tel": "Telugu", "hin": "Hindi", "eng": "English", "mal": "Malayalam"}
        selected_lang = lang_names.get(lang_code, lang_code)
        await query.answer(f"Audio set to {selected_lang}!", show_alert=True)
        await query.message.edit_text(f"  **Success!**\n\nNow, when you open the video player, the **{selected_lang}** audio will play first automatically.")
