"""
POST FORWARD FEATURE
====================
File / URL upload start aagum pothu:
  1. Filename-la prefix kum S01 (any season) kum naduvula irukkura TITLE edukkum
  2. Un POST CHANNEL-la antha title irukkura image+caption post-a thedum
  3. Antha post-a DUMP channel-ku copy pannum  (file-ku MUNNADI)
  4. Appuram thaan file upload aagi dump-ku pogum

Download-la cancel pannina inga varaikkum code varave varaathu -> forward pogaadhu.
Upload-la cancel / error aana forward pannina post-a dump-la irunthu delete pannidum.

POST CHANNEL SET PANNA (permanent, DB-la save aagum, bot-la irunthe maathikalam):
  /post_channel -1001234567890   -> set / change   (admin only)
  /post_channel                  -> ippo enna channel nu paarkka
  /del_post_channel              -> remove (keezha irukkura default-ku povum)
  Bot-a antha channel-la ADMIN-a add pannanum.
"""
import os, re, asyncio, unicodedata
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from helper.database import goku_stark
from config import Config

# =====================================================================
#  SETTINGS  (top-la irukkum)
# =====================================================================
DEFAULT_POST_CHANNEL_ID = 0  # Optional backup id (command-la set pannina adhuve first priority). Example: -1001234567890
POST_FORWARD_ENABLED = True  # False pannina intha feature muzhusa off
LOOKUP_TIMEOUT = 30          # seconds - post thedura time limit (upload stuck aagama irukka)
SCAN_BATCH = 200             # oru thadava ethana message id check pannum
SCAN_MAX_BATCHES = 100       # safety limit (100 x 200 = 20,000 messages)
# =====================================================================

DEFAULT_POST_CHANNEL_ID = int(os.environ.get("POST_CHANNEL_ID", DEFAULT_POST_CHANNEL_ID))

_idx = goku_stark.db["post_index"]   # {_id: message_id, norm, first}
_meta = goku_stark.db["post_meta"]   # {_id: channel_id, last_scanned}
_settings = goku_stark.db["bot_settings"]   # {_id: "post_channel", value: channel_id}
_caches = {}                         # {channel_id: {message_id: (norm_full, norm_first_line)}}
_chan = {"loaded": False, "id": 0}
_lock = asyncio.Lock()


# ---------------------------------------------------------------------
#  POST CHANNEL (permanent setting - DB-la irukkum)
# ---------------------------------------------------------------------
async def get_post_channel() -> int:
    if not _chan["loaded"]:
        d = await _settings.find_one({"_id": "post_channel"})
        _chan["id"] = int(d["value"]) if d and d.get("value") else DEFAULT_POST_CHANNEL_ID
        _chan["loaded"] = True
    return _chan["id"]


async def set_post_channel(value):
    if value:
        await _settings.update_one({"_id": "post_channel"}, {"$set": {"value": int(value)}}, upsert=True)
    else:
        await _settings.delete_one({"_id": "post_channel"})
    _chan["loaded"] = False


# ---------------------------------------------------------------------
#  Text helpers
# ---------------------------------------------------------------------
def _norm(text: str) -> str:
    """lower-case, fancy fonts -> normal, symbols/emoji remove, single spaces."""
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"[^\w\s]|_", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _first_line(text: str) -> str:
    for line in (text or "").splitlines():
        n = _norm(line)
        if n:
            return n
    return ""


def rank_posts(cache: dict, title: str) -> list:
    """
    Title match aagura posts-a best -> worst order-la return pannum (message ids).
    Same score-la ore title-ku rendu post irundha, FIRST (pazhaya) post munnadi varum.
    """
    t = _norm(title)
    if not t:
        return []
    padded = f" {t} "
    scored = []
    for mid, (full, first) in cache.items():
        if first == t:
            score, gap = 4, 0
        elif first.startswith(t + " "):
            score, gap = 3, len(first) - len(t)
        elif padded in f" {first} ":
            score, gap = 2, len(first) - len(t)
        elif padded in f" {full} ":
            score, gap = 1, len(full) - len(t)
        else:
            continue
        scored.append((-score, gap, mid))
    scored.sort()
    return [mid for _, _, mid in scored]


# ---------------------------------------------------------------------
#  Index (Mongo-la save aagum -> Render restart aanaalum poidaathu)
# ---------------------------------------------------------------------
async def _load_cache(chan):
    if chan not in _caches:
        cache = {}
        async for d in _idx.find({"chan": chan}):
            cache[d["mid"]] = (d.get("norm", ""), d.get("first", ""))
        _caches[chan] = cache
    return _caches[chan]


async def _store(msg, chan):
    text = msg.caption or msg.text or ""
    norm, first = _norm(text), _first_line(text)
    if not norm:
        return
    await _idx.update_one(
        {"_id": f"{chan}:{msg.id}"},
        {"$set": {"chan": chan, "mid": msg.id, "norm": norm, "first": first}},
        upsert=True,
    )
    cache = await _load_cache(chan)
    cache[msg.id] = (norm, first)


async def _forget(chan, mid: int):
    await _idx.delete_one({"_id": f"{chan}:{mid}"})
    cache = await _load_cache(chan)
    cache.pop(mid, None)


async def _get_batch(bot, chan, ids):
    for _ in range(3):
        try:
            res = await bot.get_messages(chan, ids)
            return res if isinstance(res, list) else [res]
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
    return []


async def _catch_up(bot, chan):
    """
    Channel-la ippo varaikkum irukkura ellaa posts-um index pannum.
    First time = full scan. Appuram = last_scanned-la irunthu mattum (1 chinna call).
    Bot offline-la irukkum pothu pottta posts-um ithula pidikkum.
    """
    async with _lock:
        await _load_cache(chan)
        meta = await _meta.find_one({"_id": chan})
        first_run = meta is None
        last = (meta or {}).get("last_scanned", 0)
        cursor, empty_batches = last + 1, 0
        need_empty = 2 if first_run else 1

        for _ in range(SCAN_MAX_BATCHES):
            msgs = await _get_batch(bot, chan, list(range(cursor, cursor + SCAN_BATCH)))
            found = [m for m in msgs if m and not getattr(m, "empty", False)]
            if found:
                empty_batches = 0
                for m in found:
                    await _store(m, chan)
                last = max(last, max(m.id for m in found))
            else:
                empty_batches += 1
                if empty_batches >= need_empty:
                    break
            cursor += SCAN_BATCH

        await _meta.update_one({"_id": chan}, {"$set": {"last_scanned": last}}, upsert=True)


# ---------------------------------------------------------------------
#  Live indexing: post channel-la puthu post / edit pottaa udane index aagum
#  (channel maathinaalum auto-va puthu channel-a follow pannum)
# ---------------------------------------------------------------------
async def _is_post_chan(_, __, message):
    chan = await get_post_channel()
    return bool(chan) and message.chat.id == chan


_post_chan_filter = filters.create(_is_post_chan)


@Client.on_message(filters.channel & _post_chan_filter, group=5)
async def _on_new_post(client, message):
    try:
        await _store(message, message.chat.id)
    except Exception as e:
        print(f"[POST-INDEX] new post error: {e}", flush=True)


@Client.on_edited_message(filters.channel & _post_chan_filter, group=5)
async def _on_edited_post(client, message):
    try:
        await _store(message, message.chat.id)
    except Exception as e:
        print(f"[POST-INDEX] edit error: {e}", flush=True)


# ---------------------------------------------------------------------
#  COMMANDS (admin only): /post_channel , /del_post_channel
# ---------------------------------------------------------------------
@Client.on_message(filters.private & filters.command("post_channel") & filters.user(Config.ADMIN))
async def post_channel_cmd(client, message):
    if len(message.command) == 1:
        cur = await get_post_channel()
        return await message.reply_text(
            f"📡 **Post Channel:** `{cur if cur else 'Not Set'}`\n\n"
            "Maathanum na:\n`/post_channel -1001234567890`\n\nRemove: `/del_post_channel`",
            reply_to_message_id=message.id,
        )
    try:
        new_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ **Invalid ID!** Numbers mattum podu.\nExample: `/post_channel -1001234567890`")
    try:
        chat = await client.get_chat(new_id)
    except Exception as e:
        return await message.reply_text(
            f"❌ **Channel access illa:** `{e}`\n\nId correct-aa? Bot-a antha channel-la **admin**-aa add pannitiya?"
        )
    await set_post_channel(new_id)
    # puthu channel-a munnadiye index pannidalam (first upload fast-aa irukkum)
    async def _warm():
        try:
            await _catch_up(client, new_id)
        except Exception as e:
            print(f"[POST-INDEX] warm-up failed: {e}", flush=True)
    asyncio.create_task(_warm())
    await message.reply_text(
        f"✅ **Post Channel Set!**\n\n📡 **{chat.title}**\n🆔 `{new_id}`\n\n"
        "Permanent-aa save aachu. Posts index aaga aarambichiduchu."
    )


@Client.on_message(filters.private & filters.command("del_post_channel") & filters.user(Config.ADMIN))
async def del_post_channel_cmd(client, message):
    await set_post_channel(None)
    cur = await get_post_channel()
    await message.reply_text(
        "🗑️ **Post Channel removed.**" + (f"\nDefault channel `{cur}` use aagum." if cur else "\nAuto Post nikkum (channel illa).")
    )


# ---------------------------------------------------------------------
#  PUBLIC API  (file_rename.py & url_uploader.py use pannum)
# ---------------------------------------------------------------------
async def _copy(bot, chan, target_chat, mid):
    for _ in range(2):
        try:
            return await bot.copy_message(chat_id=target_chat, from_chat_id=chan, message_id=mid)
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
    return None


async def _send(bot, chan, title, target_chat):
    await _catch_up(bot, chan)
    cache = await _load_cache(chan)
    for mid in rank_posts(cache, title)[:3]:
        try:
            sent = await _copy(bot, chan, target_chat, mid)
        except Exception as e:
            # post delete aagirukkum -> index-la irunthu remove pannitu next best-a try pannum
            print(f"[POST-FORWARD] copy failed for {mid}: {e}", flush=True)
            await _forget(chan, mid)
            continue
        if sent:
            return sent, ""
    return None, f"⚠️ Post kedaikkala: `{title}`"


async def send_post_for_title(bot, title, target_chat, user_id=None):
    """
    Return: (copied_message | None, note_text)
    Ethu nadanthaalum exception veliya poogaadhu -> upload ethaiyum break aagaadhu.
    (User cancel pannina mattum CancelledError veliya pogum - adhu correct.)
    """
    if not POST_FORWARD_ENABLED:
        return None, ""
    if user_id is not None and not await goku_stark.get_autopost(user_id):
        return None, ""          # Settings-la Auto Post OFF
    chan = await get_post_channel()
    if not chan:
        return None, "⚠️ Post channel set pannala (`/post_channel -100xxxx`)"
    title = (title or "").strip()
    if not title:
        return None, "⚠️ Title edukka mudiyala - post forward skip"
    try:
        return await asyncio.wait_for(_send(bot, chan, title, target_chat), LOOKUP_TIMEOUT)
    except asyncio.TimeoutError:
        return None, "⚠️ Post search timeout aachu"
    except Exception as e:
        print(f"[POST-FORWARD] error: {e}", flush=True)
        return None, f"⚠️ Post forward error: {e}"


async def discard_post(bot, msg):
    """Upload cancel / fail aana forward pannina post-a dump-la irunthu delete pannum."""
    if not msg:
        return
    try:
        await bot.delete_messages(msg.chat.id, msg.id)
    except Exception as e:
        print(f"[POST-FORWARD] discard failed: {e}", flush=True)
