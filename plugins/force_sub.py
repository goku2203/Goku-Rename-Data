# pyrogram imports
from pyrogram import Client, filters, enums 
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserNotParticipant

# extra imports
from config import Config
from script import script
from helper.database import digital_botz
import datetime 

async def not_subscribed(_, client, message):
    await digital_botz.add_user(client, message)
    if not Config.FORCE_SUB:
        return False

    try:
        user = await client.get_chat_member(Config.FORCE_SUB, message.from_user.id)
        return user.status not in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except UserNotParticipant:
        return True
    except Exception as e:
        print(f"Error checking subscription: {e}")
        return False

async def handle_banned_user_status(bot, message):
    await digital_botz.add_user(bot, message) 
    user_id = message.from_user.id
    ban_status = await digital_botz.get_ban_status(user_id)
    if ban_status.get("is_banned", False):
        if ( datetime.date.today() - datetime.date.fromisoformat(ban_status["banned_on"])
        ).days > ban_status["ban_duration"]:
            await digital_botz.remove_ban(user_id)
        else:
            return await message.reply_text("Sorry Sir, 😔 You are Banned!.. Please Contact - @Techgokul") 
    await message.continue_propagation()
    
async def forces_sub(client, message):
    buttons = [[InlineKeyboardButton(text="📢 Join Update Channel 📢", url=f"https://t.me/{Config.FORCE_SUB}")]] 
    text = script.FORCE_SUB_TEXT

    try:
        user = await client.get_chat_member(Config.FORCE_SUB, message.from_user.id)
        if user.status == enums.ChatMemberStatus.BANNED:
            return await message.reply_text("Sᴏʀʀy Yᴏᴜ'ʀᴇ Bᴀɴɴᴇᴅ Tᴏ Uꜱᴇ Mᴇ")
        elif user.status not in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR]:
            return await message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))
    except UserNotParticipant:
        return await message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))
    return await message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))
