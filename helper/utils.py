import math, time, re, datetime, pytz, os, asyncio
from config import Config

# Queue Lock for One-by-One processing
file_queue_lock = asyncio.Lock()
from script import script
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


async def progress_for_pyrogram(current, total, ud_type, message, start, file_name=None):
    now = time.time()
    diff = now - start
    cancel_markup = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ 𝙲𝙰𝙽𝙲𝙴𝙻 ✖️", callback_data="cancel_task")]])

    # Total size theriyala (content-length illa) na downloaded size mattum kaattum
    if not total:
        if diff > 0 and round(diff % 5.00) == 0:
            try:
                await message.edit(
                    text=f"{ud_type}\n\n**Downloaded:** {humanbytes(current)}\n{file_name or ''}",
                    reply_markup=cancel_markup
                )
            except:
                pass
        return

    if diff <= 0 or current <= 0:
        return

    if round(diff % 5.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000
        estimated_total_time = elapsed_time + time_to_completion

        elapsed_time = TimeFormatter(milliseconds=elapsed_time)
        estimated_total_time = TimeFormatter(milliseconds=estimated_total_time)

        progress = "{0}{1}".format(
            ''.join(["▣" for i in range(math.floor(percentage / 5))]),
            ''.join(["▢" for i in range(20 - math.floor(percentage / 5))])
        )
        tmp = progress + script.RKN_PROGRESS.format(
            round(percentage, 2),
            humanbytes(current),
            humanbytes(total),
            humanbytes(speed),
            estimated_total_time if estimated_total_time != '' else "0 s",
            file_name if file_name else ""
        )
        try:
            await message.edit(
                text=f"{ud_type}\n\n{tmp}",
                reply_markup=cancel_markup
            )
        except:
            pass

def humanbytes(size):    
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'ʙ'

def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "ᴅ, ") if days else "") + \
        ((str(hours) + "ʜ, ") if hours else "") + \
        ((str(minutes) + "ᴍ, ") if minutes else "") + \
        ((str(seconds) + "ꜱ, ") if seconds else "") + \
        ((str(milliseconds) + "ᴍꜱ, ") if milliseconds else "")
    return tmp[:-2] 

def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60      
    return "%d:%02d:%02d" % (hour, minutes, seconds)

async def send_log(b, u):
    if Config.LOG_CHANNEL:
        curr = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
        log_message = (
            "**--Nᴇᴡ Uꜱᴇʀ Sᴛᴀʀᴛᴇᴅ Tʜᴇ Bᴏᴛ--**\n\n"
            f"Uꜱᴇʀ: {u.mention}\n"
            f"Iᴅ: `{u.id}`\n"
            f"Uɴ: @{u.username}\n\n"
            f"Dᴀᴛᴇ: {curr.strftime('%d %B, %Y')}\n"
            f"Tɪᴍᴇ: {curr.strftime('%I:%M:%S %p')}\n\n"
            f"By: {b.mention}"
        )
        await b.send_message(Config.LOG_CHANNEL, log_message)

async def get_seconds_first(time_string):
    conversion_factors = {
        's': 1,
        'min': 60,
        'hour': 3600,
        'day': 86400,
        'month': 86400 * 30,
        'year': 86400 * 365
    }
    parts = time_string.split()
    total_seconds = 0
    for i in range(0, len(parts), 2):
        value = int(parts[i])
        unit = parts[i+1].rstrip('s')
        total_seconds += value * conversion_factors.get(unit, 0)
    return total_seconds

async def get_seconds(time_string):
    conversion_factors = {
        's': 1,
        'min': 60,
        'hour': 3600,
        'day': 86400,
        'month': 86400 * 30,
        'year': 86400 * 365
    }
    total_seconds = 0
    pattern = r'(\d+)\s*(\w+)'
    matches = re.findall(pattern, time_string)
    for value, unit in matches:
        total_seconds += int(value) * conversion_factors.get(unit, 0)
    return total_seconds

async def add_prefix_suffix(input_string, prefix='', suffix=''):
    pattern = r'(?P<filename>.*?)(\.\w+)?$'
    match = re.search(pattern, input_string)
    if match:
        filename = match.group('filename')
        extension = match.group(2) or ''
        prefix_str = f"{prefix} " if prefix else ""
        suffix_str = f" {suffix}" if suffix else ""
        return f"{prefix_str}{filename}{suffix_str}{extension}"
    else:
        return input_string

async def remove_path(*paths):
    for path in paths:
        if path and os.path.lexists(path):
            os.remove(path)

async def metadata_text(metadata_text):
    author = None
    title = None
    video_title = None
    audio_title = None
    subtitle_title = None
    flags = [i.strip() for i in metadata_text.split('--')]
    for f in flags:
        if "change-author" in f:
            author = f[len("change-author"):].strip()
        if "change-title" in f:
            title = f[len("change-title"):].strip()
        if "change-video-title" in f:
            video_title = f[len("change-video-title"):].strip()
        if "change-audio-title" in f:
            audio_title = f[len("change-audio-title"):].strip()
        if "change-subtitle-title" in f:
            subtitle_title = f[len("change-subtitle-title"):].strip()
    return author, title, video_title, audio_title, subtitle_title


# =====================================================================
#  CANCEL SUPPORT  (Cancel button click -> running task nijamave stop)
# =====================================================================
# key = (chat_id, progress_message_id)  ->  running asyncio task
ACTIVE_TASKS = {}


def task_key(msg):
    return (msg.chat.id, msg.id)


async def run_cancellable(progress_msg, coro):
    """
    coro-va oru task-a run pannum. Cancel button click pannina task.cancel() aagum.
    Return: (result, cancelled_flag)
    """
    key = task_key(progress_msg)
    task = asyncio.ensure_future(coro)
    ACTIVE_TASKS[key] = task
    try:
        return await task, False
    except asyncio.CancelledError:
        if task.cancelled():
            return None, True      # user Cancel click pannitaaru
        raise                      # bot shutdown maathiri veli cancel
    finally:
        ACTIVE_TASKS.pop(key, None)
        ACTIVE_TASKS.pop(task_key(progress_msg), None)   # queue-la irunthu vandha pin message id maarirukkalaam


async def safe_delete(*msgs):
    """Oru message delete fail aanaalum adutha message delete aagum."""
    for m in msgs:
        if m:
            try:
                await m.delete()
            except Exception:
                pass


def cleanup_files(*paths):
    """Temp / partial files ellathaiyum safe-a remove pannum."""
    for p in paths:
        try:
            if p and os.path.lexists(p):
                os.remove(p)
        except Exception:
            pass


# =====================================================================
#  QUEUE NUMBERING  (ORU single "Queue N" message + queue-la add aana udane user message delete)
# =====================================================================
# Oru neratula ORU link / file mattum process aagum (file_queue_lock).
# Line-la position: ippo run aagura job = Queue 1, adutha = Queue 2, adutha = Queue 3 ...
# Waiting irukkuravanga ellarukkum serthu ORE message (banner) - adhula number thaan maarum:
#   2nd anuppina -> "Queue 2",  3rd anuppina -> same message "Queue 3",  job mudinja -> "Queue 2" ... (waiting illa-na message delete)
QUEUE_WAITING = []                 # waiting irukkura QueueSlot-gal (anuppina order-padi)
QUEUE_BANNERS = {}                 # chat_id -> {"msg": single queue message, "shown": N}
_queue_state = {"busy": False}     # oru job ippo run aagitu irukka?
QUEUE_CANCEL_MARKUP = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ 𝙲𝙰𝙽𝙲𝙴𝙻 ✖️", callback_data="cancel_task")]])
QUEUE_BANNER_MARKUP = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ 𝙲𝙰𝙽𝙲𝙴𝙻 𝙻𝙰𝚂𝚃 ✖️", callback_data="cancel_queue")]])
QUEUE_TURN_HOLD = 1.0              # "Queue 1" message-a user paarkka (seconds) - processing start aagura munnadi

_refresh_lock = asyncio.Lock()     # oru neratula oru refresh mattum -> numbers order thappi / pazhaya number varaadhu
_bg_tasks = set()


def _banner_text(n):
    return f"`⏳ Added to Queue {n}`\n`Please wait your turn...`"


async def _refresh_queue_numbers():
    """Ovvoru chat-kum ORE queue message-a create / edit / delete pannum."""
    async with _refresh_lock:
        running = 1 if _queue_state["busy"] else 0       # run aagitu irukkura job = Queue 1
        last, sample = {}, {}
        for i, slot in enumerate(list(QUEUE_WAITING)):
            last[slot.chat_id] = i + 1 + running           # antha chat-oda kadaisi waiting job-oda number
            sample.setdefault(slot.chat_id, slot)

        for chat_id, n in last.items():
            banner = QUEUE_BANNERS.get(chat_id)
            if banner is None:
                try:
                    m = await sample[chat_id].msg._client.send_message(
                        chat_id, _banner_text(n), reply_markup=QUEUE_BANNER_MARKUP)
                    QUEUE_BANNERS[chat_id] = {"msg": m, "shown": n}
                except Exception:
                    pass
            elif banner["shown"] != n:
                try:
                    await banner["msg"].edit(_banner_text(n), reply_markup=QUEUE_BANNER_MARKUP)
                    banner["shown"] = n
                except Exception as e:
                    if "MESSAGE_NOT_MODIFIED" in str(e).upper():
                        banner["shown"] = n
                    elif "FLOOD" not in str(e).upper():
                        QUEUE_BANNERS.pop(chat_id, None)   # message poiduchu -> next refresh-la thirumba create

        # Waiting yaarum illa -> queue message-a delete
        for chat_id in [c for c in QUEUE_BANNERS if c not in last]:
            banner = QUEUE_BANNERS.pop(chat_id, None)
            if banner:
                try:
                    await banner["msg"].delete()
                except Exception:
                    pass


def _kick_refresh():
    """Numbers refresh-a background-la run pannum (queue-la join aagura job-a block pannaadhu)."""
    t = asyncio.ensure_future(_refresh_queue_numbers())
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)


class QueueSlot:
    """
    async with QueueSlot(msg, "Link", markup, on_queued=..., order=(msg_id, idx), registered=event):
        ... download / upload work ...

    - Vera job run aagitu irundha: user anuppina link / file MUDHAL-la delete (on_queued), appuram
      antha chat-ku ORE "Queue N" message varum. Adutha link / file vandha ADHE message-la number maarum.
    - Munnadi irukkura job mudinja / cancel aana number thaaney kuraiyum (Queue 3 -> 2 -> 1 -> processing).
    - Namma turn vandha: "Queue 1" kaattitu processing start (progress message thaniya varum).
    - order: user anuppina message id (link-na (message_id, line_no)). Anuppina order-padiye queue-la nikkum.
    - registered: asyncio.Event - queue-la serndhathum (illa udane run aanathum) set aagum.
    """
    def __init__(self, msg, label, markup=None, on_queued=None, order=None, registered=None):
        self.msg, self.label, self.markup, self.on_queued = msg, label, markup, on_queued
        self.chat_id = msg.chat.id
        self.order = order if order is not None else (float("inf"), 0)
        self.registered = registered
        self.waiting = False
        self._msg_deleted = False   # waiting-la irukkum pothu namma thani message delete pannitom

    def _add_waiting(self):
        # anuppina order-padi sorted-a insert pannum; same order na pinnadi
        idx = len(QUEUE_WAITING)
        for i, other in enumerate(QUEUE_WAITING):
            if other.order > self.order:
                idx = i
                break
        QUEUE_WAITING.insert(idx, self)

    async def _show_turn(self):
        """Namma turn: "Queue 1" kaattitu konjam neram (user paarkka)."""
        text = f"`⏳ {self.label} Added to Queue 1`\n`Starting now...`"
        try:
            if self._msg_deleted:
                # thani message delete aagiduchu -> pudhusa oru message anuppi, adhe message object-a use pannuvom
                old_key = task_key(self.msg)
                new = await self.msg._client.send_message(self.chat_id, text, reply_markup=self.markup)
                self.msg.id = new.id
                task = ACTIVE_TASKS.pop(old_key, None)
                if task is not None:
                    ACTIVE_TASKS[task_key(self.msg)] = task      # Cancel button puthu message-ku velai seiyum
                self._msg_deleted = False
            else:
                await self.msg.edit(text, reply_markup=self.markup)
        except Exception:
            pass
        await asyncio.sleep(QUEUE_TURN_HOLD)

    async def __aenter__(self):
        self.waiting = _queue_state["busy"] or bool(QUEUE_WAITING)
        if self.waiting:
            self._add_waiting()
            if self.registered is not None:
                self.registered.set()
            # 1) user anuppina link / file MUDHAL-la delete   2) namma "Please wait" message delete
            # 3) appuram ORE Queue message-la number
            if self.on_queued:
                try:
                    await self.on_queued()
                except Exception:
                    pass
            try:
                await self.msg.delete()
                self._msg_deleted = True
            except Exception:
                pass
            _kick_refresh()
        elif self.registered is not None:
            self.registered.set()
        try:
            await file_queue_lock.acquire()
        except BaseException:
            # queue-la irukkum pothe cancel -> list-la irunthu remove, matha numbers update
            if self in QUEUE_WAITING:
                QUEUE_WAITING.remove(self)
            _kick_refresh()
            raise
        if self in QUEUE_WAITING:
            QUEUE_WAITING.remove(self)
        _queue_state["busy"] = True
        _kick_refresh()                          # pinnadi irukkuravanga number kuraiyum (Queue 3 -> 2 ...)
        try:
            await self._show_turn()
        except BaseException:
            _queue_state["busy"] = False
            file_queue_lock.release()
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb):
        _queue_state["busy"] = False
        file_queue_lock.release()
        _kick_refresh()                          # waiting yaarum illa-na queue message delete aagum
        return False
