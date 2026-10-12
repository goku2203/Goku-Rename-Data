import random, asyncio, datetime, pytz, time, psutil, shutil
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply, CallbackQuery
from helper.database import goku_stark
from config import Config
from script import script
from helper.utils import humanbytes
from plugins import __version__ as _bot_version_, __developer__, __database__, __library__, __language__, __programer__
from plugins.file_rename import upload_doc

@Client.on_message(filters.private & filters.command("start"))
async def start(client, message):
    start_button = [
        [
            InlineKeyboardButton('Hᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('Aʙᴏᴜᴛ', callback_data='about')
        ],
        [
            InlineKeyboardButton('Uᴘᴅᴀᴛᴇs', url='https://t.me/goku_n'),
            InlineKeyboardButton('Sᴜᴘᴘᴏʀᴛ', url='https://t.me/Naruto_Shippuden_tamil_hddd')
        ]
    ]
        
    user = message.from_user
    await goku_stark.add_user(client, message) 
    
    if Config.RKN_PIC:
        await message.reply_photo(
            Config.RKN_PIC, 
            caption=script.START_TXT.format(user.mention), 
            reply_markup=InlineKeyboardMarkup(start_button)
        )    
    else:
        await message.reply_text(
            text=script.START_TXT.format(user.mention), 
            reply_markup=InlineKeyboardMarkup(start_button), 
            disable_web_page_preview=True
        )

@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data 
    
    if data == "start":
        start_button = [
            [
            InlineKeyboardButton('Hᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('Aʙᴏᴜᴛ', callback_data='about')
        ],
        [
            InlineKeyboardButton('Uᴘᴅᴀᴛᴇs', url='https://t.me/goku_n'),
            InlineKeyboardButton('Sᴜᴘᴘᴏʀᴛ', url='https://t.me/Naruto_Shippuden_tamil_hddd')
        ]
    ]
        await query.message.edit_text(
            text=script.START_TXT.format(query.from_user.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(start_button)
        )
        
    elif data == "help":
        help_button = [
            [
                InlineKeyboardButton("Tʜᴜᴍʙɴᴀɪʟ", callback_data="thumbnail"),
                InlineKeyboardButton("Cᴀᴘᴛɪᴏɴ", callback_data="caption")
            ],
            [
                InlineKeyboardButton("Bᴀᴄᴋ", callback_data="start")
            ]
        ]
        await query.message.edit_text(
            text=script.HELP_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(help_button)
        )
        
    elif data == "about":
        about_button = [
            [
                InlineKeyboardButton("Lɪᴠᴇ Sᴛᴀᴛᴜs", callback_data="live_status"),
                InlineKeyboardButton("Bᴏᴛ Sᴛᴀᴛᴜs", callback_data="bot_status")
            ],
            [
                InlineKeyboardButton("Bᴀᴄᴋ", callback_data="start")
            ]
        ]
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(client.mention, __developer__, __programer__, __library__, __language__, __database__, _bot_version_),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(about_button)
        )    

    elif data == "thumbnail":
        await query.message.edit_text(
            text=script.THUMBNAIL,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Bᴀᴄᴋ", callback_data="help")]])
        ) 
      
    elif data == "caption":
        await query.message.edit_text(
            text=script.CAPTION,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Bᴀᴄᴋ", callback_data="help")]])
        ) 
        
    elif data == "bot_status":
        total_users = await goku_stark.total_users_count()
        total_premium_users = "Disabled ✅"
        uptime = time.strftime("%Hh%Mm%Ss", time.gmtime(time.time() - client.uptime))    
        sent = humanbytes(psutil.net_io_counters().bytes_sent)
        recv = humanbytes(psutil.net_io_counters().bytes_recv)
        
        await query.message.edit_text(
            text=script.BOT_STATUS.format(uptime, total_users, total_premium_users, sent, recv),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Bᴀᴄᴋ", callback_data="about")]])
        ) 
      
    elif data == "live_status":
        currentTime = time.strftime("%Hh%Mm%Ss", time.gmtime(time.time() - client.uptime))    
        total, used, free = shutil.disk_usage(".")
        total = humanbytes(total)
        used = humanbytes(used)
        free = humanbytes(free)
        sent = humanbytes(psutil.net_io_counters().bytes_sent)
        recv = humanbytes(psutil.net_io_counters().bytes_recv)
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        
        await query.message.edit_text(
            text=script.LIVE_STATUS.format(currentTime, cpu_usage, ram_usage, total, used, disk_usage, free, sent, recv),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Bᴀᴄᴋ", callback_data="about")]])
        ) 
            
    elif data.startswith("upload"):
        await upload_doc(client, query)
            
    elif data == "close":
        try:
            await query.message.delete()
            await query.message.reply_to_message.delete()
        except:
            await query.message.delete()
