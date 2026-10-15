import os, random, asyncio, datetime, pytz, time, psutil, shutil
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply, CallbackQuery
from helper.database import goku_stark
from config import Config
from script import script
from helper.utils import humanbytes, file_queue_lock
from plugins import __version__ as _bot_version_, __developer__, __database__, __library__, __language__, __programer__
from plugins.file_rename import upload_doc


def get_render_memory():
    """Render Docker container-oda exact RAM & Bot+FFmpeg RAM-ah kandupudikkum"""
    proc = psutil.Process(os.getpid())
    bot_rss = proc.memory_info().rss
    for child in proc.children(recursive=True):
        try:
            bot_rss += child.memory_info().rss
        except Exception:
            pass

    used_bytes = None
    limit_bytes = None
    try:
        # Cgroup v2 (Render / Docker Linux)
        if os.path.exists("/sys/fs/cgroup/memory.current"):
            with open("/sys/fs/cgroup/memory.current", "r") as f:
                used_bytes = int(f.read().strip())
        if os.path.exists("/sys/fs/cgroup/memory.max"):
            with open("/sys/fs/cgroup/memory.max", "r") as f:
                val = f.read().strip()
                if val.isdigit():
                    limit_bytes = int(val)

        # Cgroup v1 Fallback
        if used_bytes is None and os.path.exists("/sys/fs/cgroup/memory/memory.usage_in_bytes"):
            with open("/sys/fs/cgroup/memory/memory.usage_in_bytes", "r") as f:
                used_bytes = int(f.read().strip())
        if limit_bytes is None and os.path.exists("/sys/fs/cgroup/memory/memory.limit_in_bytes"):
            with open("/sys/fs/cgroup/memory/memory.limit_in_bytes", "r") as f:
                val = int(f.read().strip())
                if val < 1024 ** 4:
                    limit_bytes = val
    except Exception:
        pass

    if used_bytes is None:
        used_bytes = bot_rss

    # Render Free Plan-la cgroup limit varalana default-ah 512 MB eduthukkum
    if not limit_bytes or limit_bytes > 10 * (1024 ** 3):
        limit_bytes = 512 * 1024 * 1024

    ram_percent = round((used_bytes / limit_bytes) * 100, 1)
    return (
        humanbytes(used_bytes) or "0 B",
        humanbytes(limit_bytes) or "512 MB",
        ram_percent,
        humanbytes(bot_rss) or "0 B"
    )


def get_temp_folder_info():
    """Renames folder-la ethana files irukku, evlo size nu check pannum"""
    folder = "Renames"
    if not os.path.exists(folder):
        return "0 B", 0
    total_size = 0
    file_count = 0
    for root, _, files in os.walk(folder):
        for f in files:
            fp = os.path.join(root, f)
            if os.path.exists(fp):
                total_size += os.path.getsize(fp)
                file_count += 1
    return humanbytes(total_size) or "0 B", file_count


async def generate_status_text(client):
    start_t = time.time()
    total_users = await goku_stark.total_users_count()
    banned_users = await goku_stark.col.count_documents({'ban_status.is_banned': True})
    end_t = time.time()
    ping = f"{(end_t - start_t) * 1000:.2f}"

    uptime_sec = int(time.time() - client.uptime)
    days, rem = divmod(uptime_sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    uptime = f"{days}d {hours}h {minutes}m {seconds}s" if days else f"{hours}h {minutes}m {seconds}s"

    queue_status = "Busy (Processing) 🔄" if file_queue_lock.locked() else "Idle (Free) ⚡"

    ram_used, ram_total, ram_usage, bot_ram = get_render_memory()
    temp_size, temp_files = get_temp_folder_info()

    total_d, used_d, free_d = shutil.disk_usage(".")
    total_disk = humanbytes(total_d) or "0 B"
    used_disk = humanbytes(used_d) or "0 B"
    free_disk = humanbytes(free_d) or "0 B"
    disk_usage = psutil.disk_usage('/').percent

    net = psutil.net_io_counters()
    sent = humanbytes(net.bytes_sent) or "0 B"
    recv = humanbytes(net.bytes_recv) or "0 B"

    cpu_usage = psutil.cpu_percent()

    return script.STATUS_TXT.format(
        port=Config.PORT,
        ping=ping,
        uptime=uptime,
        queue_status=queue_status,
        ram_used=ram_used,
        ram_total=ram_total,
        ram_usage=ram_usage,
        bot_ram=bot_ram,
        cpu_usage=cpu_usage,
        temp_size=temp_size,
        temp_files=temp_files,
        total_disk=total_disk,
        used_disk=used_disk,
        disk_usage=disk_usage,
        free_disk=free_disk,
        sent=sent,
        recv=recv,
        total_users=total_users,
        banned_users=banned_users
    )


@Client.on_message(filters.private & filters.command("start"))
async def start(client, message):
    start_button = [
        [
            InlineKeyboardButton('Help', callback_data='help'),
            InlineKeyboardButton('About', callback_data='about')
        ],
        [
            InlineKeyboardButton('Updates', url='https://t.me/goku_n'),
            InlineKeyboardButton('Support', url='https://t.me/Naruto_Shippuden_tamil_hddd')
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
                InlineKeyboardButton('Help', callback_data='help'),
                InlineKeyboardButton('About', callback_data='about')
            ],
            [
                InlineKeyboardButton('Updates', url='https://t.me/goku_n'),
                InlineKeyboardButton('Support', url='https://t.me/Naruto_Shippuden_tamil_hddd')
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
                InlineKeyboardButton("Thumbnail", callback_data="thumbnail"),
                InlineKeyboardButton("Caption", callback_data="caption")
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="start")
            ]
        ]
        await query.message.edit_text(
            text=script.HELP_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(help_button)
        )

    elif data == "about":
        about_button = []
        if query.from_user.id in Config.ADMIN:
            about_button.append([InlineKeyboardButton("📊 Status", callback_data="status_data")])
        about_button.append([InlineKeyboardButton("⬅️ Back", callback_data="start")])

        await query.message.edit_text(
            text=script.ABOUT_TXT.format(client.mention, __developer__, __programer__, __library__, __language__, __database__, _bot_version_),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(about_button)
        )

    elif data in ["status_data", "status_refresh"]:
        if query.from_user.id not in Config.ADMIN:
            return await query.answer("🔒 Admin Only Feature!", show_alert=True)

        status_text = await generate_status_text(client)
        back_btn = InlineKeyboardButton("⬅️ Back", callback_data="about") if data == "status_data" else InlineKeyboardButton("❌ Close", callback_data="close")
        buttons = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=data),
                back_btn
            ]
        ]
        try:
            await query.message.edit_text(
                text=status_text,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await query.answer("⚡ Status Updated!")
        except Exception:
            await query.answer("⚡ Status is already up-to-date!")

    elif data == "thumbnail":
        await query.message.edit_text(
            text=script.THUMBNAIL,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="help")]])
        )

    elif data == "caption":
        await query.message.edit_text(
            text=script.CAPTION,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="help")]])
        )

    elif data.startswith("upload"):
        await upload_doc(client, query)

    elif data == "close":
        try:
            await query.message.delete()
            await query.message.reply_to_message.delete()
        except:
            await query.message.delete()
