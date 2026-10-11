from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from helper.database import digital_botz

@Client.on_message(filters.private & filters.command("settings"))
async def settings_command(client, message):
    buttons = [
        [InlineKeyboardButton("⚙️ Dump Settings", callback_data="dump_settings_menu")]
    ]
    await message.reply_text(
        "**⚙️ Settings Menu**\n\nKeezhe ulla button-a click panni settings-a mathikkalam.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^dump_settings_menu$"))
async def dump_settings_menu(client, query: CallbackQuery):
    user_id = query.from_user.id
    dump_status = await digital_botz.get_dump_status(user_id)
    
    # Current status check panni text mathurathu
    status_text = "ON 🟢" if dump_status else "OFF 🔴"
    
    buttons = [
        [
            InlineKeyboardButton("ON 🟢", callback_data="set_dump_on"),
            InlineKeyboardButton("OFF 🔴", callback_data="set_dump_off")
        ],
        [InlineKeyboardButton("🔙 Back to Settings", callback_data="back_to_settings")]
    ]
    
    await query.message.edit_text(
        f"**Dump Settings**\n\nCurrent Status: **{status_text}**\n\nDump file matrum sticker send aaganumna ON pannunga, vendamna OFF pannunga.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^set_dump_(on|off)$"))
async def set_dump_status_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    action = query.data.split("_")[2]
    
    if action == "on":
        await digital_botz.set_dump_status(user_id, True)
        await query.answer("Dump ON aagivittathu!", show_alert=True)
    else:
        await digital_botz.set_dump_status(user_id, False)
        await query.answer("Dump OFF aagivittathu!", show_alert=True)
        
    # Button click pannathum menu-va refresh panna
    await dump_settings_menu(client, query)

@Client.on_callback_query(filters.regex(r"^back_to_settings$"))
async def back_to_settings_cb(client, query: CallbackQuery):
    buttons = [
        [InlineKeyboardButton("⚙️ Dump Settings", callback_data="dump_settings_menu")]
    ]
    await query.message.edit_text(
        "**⚙️ Settings Menu**\n\nKeezhe ulla button-a click panni settings-a mathikkalam.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
