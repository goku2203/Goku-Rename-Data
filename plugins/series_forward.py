"""
series_forward.py
=================
URL link / File  ->  DUMP channel  ->  (NEW channel poster post + file)  ->  Target channel

Flow
----
1. Admin bot PM-la URL (direct link) allathu file anuppuvaanga.
2. Bot file name-la irundhu  [prefix]  <NAME>  S01 / Season 2 / E05 ...  -> NAME-a edukkum.
3. NEW_CHANNEL (image + caption posts) la antha NAME irukkira post-a kandupidikkum.
   (post illana -> download pannaama udane stop)
4. URL na download. Upload start aagumbodhu -> (1) NEW channel post DUMP-ku, (2) file DUMP-ku.
   File na rendum DUMP-ku copy (download/upload thevai illa).
5. Dump-la save aanathum AUTOMATIC-a dump-la irukkira (1) post (2) file rendum
   DEFAULT target channel-ku pogum  (/targets-la mudhal channel = default).
6. Name thappaa irundha download/upload nadakkum pothu (allathu FORWARD_DELAY second-kulla) "Cancel" click pannunga
   -> edhuvum forward aagaadhu, dump copy delete aagum.  Correct-na edhuvum touch panna vendaam.

Commands (ADMINS only)
----------------------
/fwdmode            - feature ON/OFF (OFF-la irundha bot pazhaya maadhiri velai seiyum)
/addtarget <id>     - target channel add (mudhal channel = default, automatic forward idhukku dhaan pogum)
/settarget <id>     - indha channel-a default-a maathum
/deltarget <id>     - remove
/targets            - list
/scanposts          - NEW channel-la ippo irukkira ella posts-um index panna (oru dhadava run pannunga)
"""
import os
import re
import html
import time
import uuid
import shutil
import asyncio
import logging
import mimetypes
import unicodedata
from os import environ
from urllib.parse import urlparse, unquote

import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import ADMINS
from database.channel_db import db as mdb

logger = logging.getLogger(__name__)

# ======================================================================
#                         ⚙️  CONFIG  (TOP)
# ======================================================================
# 👇 INGA unga NEW channel ID podunga  (image + caption posts irukkira channel). Bot antha channel-la ADMIN-a irukkanum.
NEW_CHANNEL = int(environ.get("NEW_CHANNEL", "0"))      # e.g. -1001234567890

# 👇 Dump channel ID. Already bot-la irukkira dump id-a inga podunga (allathu Render env-la DUMP_ID nu kudunga).
DUMP_ID = int(environ.get("DUMP_ID", "0"))              # e.g. -1009876543210

# Filename-la prefix-a (site/channel peru) remove panna: [Tag], (Tag), @handle, www.site.com auto-va pogum.
# Bracket illaadha prefix irundha inga serunga.  e.g. ["TamilMV", "Goku Stark"]
PREFIXES = []

USE_FORWARD_TAG = False    # False = "Forwarded from" tag illama copy.  True = normal forward (tag-oda)
FORWARD_DELAY = 5          # dump-la save aanadhum idhana second-la automatic forward (idhukkulla Cancel click pannalaam). 0 = udane
MAX_FILE_MB = 1990         # Telegram bot upload limit ~2GB
DOWNLOAD_DIR = "downloads" # temp folder (upload mudinja udane file delete aagum)
# ======================================================================

POSTS = "sfwd_posts"
SETTINGS = "sfwd_cfg"

JOBS = {}
URL_SEM = asyncio.Semaphore(1)   # Render free: oru neram oru download mattum (RAM/CPU kammi)

# ---------------------------------------------------------------- regex
ZW_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
EXT_RE = re.compile(r"(?i)\.(mkv|mp4|avi|webm|mov|m4v|ts|flv|zip|rar|7z)$")
SEASON_RE = re.compile(
    r"(?i)(?<![a-z0-9])(?:"
    r"s\d{1,2}[\s._-]*e(?:p(?:isode)?)?[\s._-]*\d{1,4}"
    r"|s(?:eason)?[\s._-]*\d{1,2}(?![a-z0-9])"
    r"|e(?:p(?:isode)?)?[\s._-]*\d{1,4}(?![a-z0-9])"
    r")"
)
YEAR_RE = re.compile(r"(?<![a-z0-9])\(?(?:19|20)\d{2}\)?(?![a-z0-9])", re.I)
QUALITY_RE = re.compile(
    r"(?i)(?<![a-z0-9])(?:(?:19|20)\d{2}|\d{3,4}p|4k|uhd|hd-?rip|web-?dl|web-?rip|blu-?ray|brrip|bdrip|"
    r"dvdrip|dvdscr|hdtv|x26[45]|h\.?26[45]|hevc|aac|esubs?|multi|dual|complete|combined)(?![a-z0-9])"
)
TLD = r"(?:com|net|org|xyz|io|me|in|cc|tv|club|pro|co|link|site|fun|icu|live|vip|top|uk|app|info|one|cam|lol|ws)"


GENERIC_WORDS = {"the", "and", "show", "shows", "series", "movie", "movies", "season", "tamil", "telugu",
                 "hindi", "english", "dubbed", "web", "hd", "new", "latest", "anime"}


class JobError(Exception):
    pass


class Cancelled(Exception):
    pass


# ====================================================================
#                      NAME  PARSING / MATCHING
# ====================================================================
def norm(s: str) -> str:
    """Caption & file name rendayum onnaa maathura normalizer (zero-width, fancy fonts, symbols ellam clean)."""
    s = unicodedata.normalize("NFKC", s or "")
    s = ZW_RE.sub("", s).lower()
    out = [ch if (ch.isalnum() or unicodedata.category(ch) in ("Mn", "Mc")) else " " for ch in s]
    return " ".join("".join(out).split())


def _strip_prefix(s: str, strong: bool) -> str:
    s = s.strip()
    while True:
        s = s.lstrip(" \t-–—_|:~·•.,")
        low = s.lower()
        hit = None
        for p in PREFIXES:
            if p and low.startswith(p.lower()):
                hit = len(p)
                break
        if hit is None:
            m = (
                re.match(r"^\[[^\]]*\]", s)
                or re.match(r"^\([^)]*\)", s)
                or re.match(r"^\{[^}]*\}", s)
                or re.match(r"(?i)^(?:https?://)?www\.[^\s/\]]+?(?=[\s\-_|\]]|$)", s)
                or re.match(r"(?i)^[a-z0-9-]+\." + TLD + r"(?=[\s\-_|\]]|$)", s)
                or (re.match(r"^@\w+", s) if strong else None)
            )
            if m:
                hit = m.end()
        if not hit:
            return s
        s = s[hit:]


def _extract(base: str, strong: bool):
    s = _strip_prefix(base, strong)
    season = None
    m = SEASON_RE.search(s)
    if m:
        cut = m.start()
        sm = re.match(r"(?i)s(?:eason)?[\s._-]*0*(\d{1,2})", m.group(0))
        season = int(sm.group(1)) if sm else None
        ym = YEAR_RE.search(s[:cut])
        if ym:
            cut = ym.start()
    else:
        qm = QUALITY_RE.search(s)
        cut = qm.start() if qm else len(s)
    t = s[:cut]
    t = re.sub(r"[\[\]\(\)\{\}@]", " ", t)
    t = re.sub(r"[._\-–—|:~]+", " ", t)
    return " ".join(t.split()), season


def parse_name(raw: str):
    """-> (title, season)   title = prefix-kum S01-kum naduvula irukkura name"""
    base = EXT_RE.sub("", unquote(raw or "").strip())
    for strong in (True, False):
        title, season = _extract(base, strong)
        if norm(title):
            return title, season
    return "", None


async def find_post(title: str, season):
    """NEW channel index-la title irukkira post-a thedum. -> (doc, matched_phrase) / None"""
    toks = norm(title).split()
    if not toks:
        return None
    for start in range(0, min(len(toks), 6)):
        part = toks[start:]
        if start > 0 and len(part) == 1 and (len(part[0]) < 3 or part[0] in GENERIC_WORDS):
            break  # prefix word-a thookina aprm "show"/"the" maadhiri generic word-a match panna koodathu
        phrase = " ".join(part)
        docs = await mdb[POSTS].find({"norm": {"$regex": r"(?:^| )" + phrase + r"(?: |$)"}}).to_list(length=50)
        if not docs:
            continue

        def key(d):
            n = d["norm"]
            has_season = bool(season) and bool(
                re.search(r"(?<![a-z0-9])(?:s0*%d|season 0*%d)(?![a-z0-9])" % (season, season), n)
            )
            pos = n.find(phrase)
            return (0 if has_season else 1, pos if pos >= 0 else 10 ** 6, -d["_id"])

        return min(docs, key=key), phrase
    return None


# ====================================================================
#                           DB  HELPERS
# ====================================================================
async def _cfg():
    d = await mdb[SETTINGS].find_one({"_id": "cfg"}) or {}
    return d.get("enabled", True), d.get("targets", [])


async def _set_cfg(**kw):
    await mdb[SETTINGS].update_one({"_id": "cfg"}, {"$set": kw}, upsert=True)


async def _index_msg(m) -> bool:
    text = m.caption or m.text or ""
    if not text.strip():
        return False
    await mdb[POSTS].update_one(
        {"_id": m.id}, {"$set": {"caption": text[:500], "norm": norm(text)}}, upsert=True
    )
    return True


# ====================================================================
#                        LIVE  INDEX  (NEW channel)
# ====================================================================
@Client.on_message(filters.channel, group=31)
async def _live_index(client, m):
    if NEW_CHANNEL and m.chat and m.chat.id == NEW_CHANNEL:
        try:
            await _index_msg(m)
        except Exception as e:
            logger.error(f"sfwd live index: {e}")


@Client.on_edited_message(filters.channel, group=31)
async def _live_index_edit(client, m):
    if NEW_CHANNEL and m.chat and m.chat.id == NEW_CHANNEL:
        try:
            await _index_msg(m)
        except Exception as e:
            logger.error(f"sfwd live index edit: {e}")


@Client.on_deleted_messages(filters.channel, group=31)
async def _live_index_del(client, messages):
    try:
        ids = [m.id for m in messages if m.chat and m.chat.id == NEW_CHANNEL]
        if ids:
            await mdb[POSTS].delete_many({"_id": {"$in": ids}})
    except Exception as e:
        logger.error(f"sfwd live index del: {e}")


# ====================================================================
#                         ADMIN  COMMANDS
# ====================================================================
@Client.on_message(filters.private & filters.user(ADMINS) & filters.command("fwdmode"))
async def cmd_fwdmode(client, message):
    enabled, targets = await _cfg()
    if len(message.command) > 1 and message.command[1].lower() in ("on", "off"):
        enabled = message.command[1].lower() == "on"
    else:
        enabled = not enabled
    await _set_cfg(enabled=enabled)
    n = await mdb[POSTS].count_documents({})
    await message.reply(
        f"<b>Series Forward: {'ON ✅' if enabled else 'OFF ❌'}</b>\n\n"
        f"📚 Indexed posts: <code>{n}</code>\n"
        f"🎯 Targets: <code>{len(targets)}</code>\n"
        f"🗂 NEW channel: <code>{NEW_CHANNEL or 'set pannala'}</code>\n"
        f"📦 Dump: <code>{DUMP_ID or 'set pannala'}</code>\n\n"
        "ON-la irukkum pothu admin anuppura <b>file / direct URL</b> ellam inga process aagum.\n"
        "Index (forward-la channel index) use panna /fwdmode off pannunga.\n\n"
        "/addtarget · /settarget · /deltarget · /targets · /scanposts",
        parse_mode=enums.ParseMode.HTML,
    )


@Client.on_message(filters.private & filters.user(ADMINS) & filters.command("addtarget"))
async def cmd_addtarget(client, message):
    if len(message.command) < 2:
        return await message.reply("Use: <code>/addtarget -100xxxxxxxxxx</code>", parse_mode=enums.ParseMode.HTML)
    try:
        cid = int(message.command[1])
        chat = await client.get_chat(cid)
    except Exception as e:
        return await message.reply(f"❌ Channel kidaikkala / bot admin illa:\n<code>{html.escape(str(e))}</code>",
                                   parse_mode=enums.ParseMode.HTML)
    _, targets = await _cfg()
    targets = [t for t in targets if t["id"] != cid] + [{"id": cid, "title": chat.title or str(cid)}]
    await _set_cfg(targets=targets)
    await message.reply(f"✅ Target add aachu: <b>{html.escape(chat.title or str(cid))}</b>",
                        parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.private & filters.user(ADMINS) & filters.command("settarget"))
async def cmd_settarget(client, message):
    if len(message.command) < 2:
        return await message.reply("Use: <code>/settarget -100xxxxxxxxxx</code>", parse_mode=enums.ParseMode.HTML)
    try:
        cid = int(message.command[1])
        chat = await client.get_chat(cid)
    except Exception as e:
        return await message.reply(f"❌ Channel kidaikkala / bot admin illa:\n<code>{html.escape(str(e))}</code>",
                                   parse_mode=enums.ParseMode.HTML)
    _, targets = await _cfg()
    targets = [{"id": cid, "title": chat.title or str(cid)}] + [t for t in targets if t["id"] != cid]
    await _set_cfg(targets=targets)
    await message.reply(f"🎯 Default target: <b>{html.escape(chat.title or str(cid))}</b>", parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.private & filters.user(ADMINS) & filters.command("deltarget"))
async def cmd_deltarget(client, message):
    if len(message.command) < 2:
        return await message.reply("Use: <code>/deltarget -100xxxxxxxxxx</code>", parse_mode=enums.ParseMode.HTML)
    try:
        cid = int(message.command[1])
    except ValueError:
        return await message.reply("ID number-a irukkanum.")
    _, targets = await _cfg()
    await _set_cfg(targets=[t for t in targets if t["id"] != cid])
    await message.reply("🗑 Removed.")


@Client.on_message(filters.private & filters.user(ADMINS) & filters.command("targets"))
async def cmd_targets(client, message):
    _, targets = await _cfg()
    if not targets:
        return await message.reply("Targets illa. <code>/addtarget -100xxxxxxxxxx</code>", parse_mode=enums.ParseMode.HTML)
    txt = "<b>🎯 Targets</b>  (mudhal = default)\n\n" + "\n".join(
        f"{'⭐' if i == 0 else '•'} {html.escape(t.get('title') or '')} — <code>{t['id']}</code>"
        for i, t in enumerate(targets)
    )
    await message.reply(txt, parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.private & filters.user(ADMINS) & filters.command("scanposts"))
async def cmd_scanposts(client, message):
    if not NEW_CHANNEL:
        return await message.reply("❌ NEW_CHANNEL set pannala (plugins/series_forward.py top).")
    st = await message.reply("🔍 NEW channel scan aagudhu...")
    mid, empty_run, found = 1, 0, 0
    while empty_run < 400 and mid < 300000:
        try:
            msgs = await client.get_messages(NEW_CHANNEL, list(range(mid, mid + 100)))
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            continue
        except Exception as e:
            return await st.edit_text(f"❌ Scan error: <code>{html.escape(str(e))}</code>\nBot channel-la admin-a?",
                                      parse_mode=enums.ParseMode.HTML)
        for m in msgs:
            if not m or m.empty:
                empty_run += 1
                continue
            empty_run = 0
            if await _index_msg(m):
                found += 1
        mid += 100
        if (mid // 100) % 10 == 0:
            await _safe_edit(st, f"🔍 Scanning... ID {mid}  |  Indexed: {found}")
        await asyncio.sleep(1)
    await _safe_edit(st, f"✅ Scan mudinjuchu. <b>{found}</b> posts index aachu.")


# ====================================================================
#                              JOBS
# ====================================================================
class Job:
    def __init__(self, client, message, kind, url=None, custom=None):
        self.id = uuid.uuid4().hex[:8]
        self.client = client
        self.message = message
        self.chat_id = message.chat.id
        self.kind = kind            # "file" | "url"
        self.url = url
        self.custom = custom
        self.cancelled = False
        self.state = "new"          # new/running/ready/forwarding/done/cancelled/failed
        self.status = None
        self.preview = None
        self.name = None
        self.title = None
        self.season = None
        self.post_id = None
        self.dump_msg = None        # dump-la file message id
        self.dump_post = None       # dump-la post message id
        self.head = ""
        self.target = None
        self.targets = []
        self.tmp = None
        self.ts = time.time()

    def check(self):
        if self.cancelled:
            raise Cancelled()


def _cancel_kb(job):
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"sfwd:x:{job.id}")]])


async def _safe_edit(msg, text, markup=None):
    try:
        await msg.edit_text(text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
    except MessageNotModified:
        pass
    except FloodWait as e:
        await asyncio.sleep(min(e.value, 10))
    except Exception as e:
        logger.debug(f"sfwd edit: {e}")


def _extract_url(text):
    for u in URL_RE.findall(text or ""):
        host = (urlparse(u).hostname or "").lower()
        if host in ("t.me", "telegram.me", "telegram.dog"):
            continue
        return u.rstrip(").,]")
    return None


def _size(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024


def _name_from_response(resp, url):
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*\s*=\s*[^']*''([^;]+)", cd, re.I)
    if m:
        return unquote(m.group(1)).strip('" ')
    m = re.search(r'filename\s*=\s*"?([^";]+)"?', cd, re.I)
    if m:
        return unquote(m.group(1)).strip()
    for u in (str(resp.url), url):
        base = os.path.basename(unquote(urlparse(u).path).rstrip("/"))
        if base and "." in base:
            return base
    base = os.path.basename(unquote(urlparse(url).path).rstrip("/")) or "file"
    ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    ext = {"video/x-matroska": ".mkv", "video/mp4": ".mp4"}.get(ctype) or mimetypes.guess_extension(ctype) or ".mkv"
    return base + ext


_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


async def _probe(job):
    """Download pannaama header mattum paathu name/size/type kandupidikkum (link sariya nu fail-fast check)."""
    timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=60)
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=_HEADERS) as s:
            async with s.get(job.url, allow_redirects=True) as r:
                if r.status not in (200, 206):
                    raise JobError(f"Link work aagala (HTTP {r.status}).")
                if "text/html" in (r.headers.get("Content-Type") or "").lower():
                    raise JobError("Idhu direct file link illa (web page). Direct download link anuppunga.")
                size = int(r.headers.get("Content-Length") or 0)
                name = job.custom or _name_from_response(r, job.url)
    except JobError:
        raise
    except Exception as e:
        raise JobError(f"Link open aagala: {e}")
    if size and size > MAX_FILE_MB * 1024 * 1024:
        raise JobError(f"File romba periyadhu ({_size(size)}). Max {MAX_FILE_MB} MB.")
    return name, size


async def _download(job, name, size):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|]+', "_", name)[-150:]
    job.tmp = os.path.join(DOWNLOAD_DIR, f"{job.id}_{safe}")
    if size and shutil.disk_usage(DOWNLOAD_DIR).free < size * 1.05:
        raise JobError("Server-la disk space illa. Chinna file try pannunga.")
    limit = MAX_FILE_MB * 1024 * 1024
    timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=90)
    done, t0, last = 0, time.time(), 0.0
    async with aiohttp.ClientSession(timeout=timeout, headers=_HEADERS) as s:
        async with s.get(job.url, allow_redirects=True) as r:
            if r.status not in (200, 206):
                raise JobError(f"Download fail (HTTP {r.status}).")
            with open(job.tmp, "wb") as f:
                async for chunk in r.content.iter_chunked(1024 * 1024):
                    job.check()
                    f.write(chunk)
                    done += len(chunk)
                    if done > limit:
                        raise JobError(f"File {MAX_FILE_MB} MB-a thaandiduchu.")
                    now = time.time()
                    if now - last >= 6:
                        last = now
                        pct = f"{done * 100 // size}%" if size else "..."
                        spd = done / max(now - t0, 1) / 1024 / 1024
                        await _safe_edit(
                            job.status,
                            job.head + f"⬇️ <b>Downloading</b> {pct}\n"
                            f"{_size(done)}{' / ' + _size(size) if size else ''}  •  {spd:.1f} MB/s",
                            _cancel_kb(job),
                        )
    return done


async def _upload(job, name):
    client, last = job.client, [0.0]

    async def progress(cur, total):
        if job.cancelled:
            client.stop_transmission()
        now = time.time()
        if now - last[0] >= 6:
            last[0] = now
            await _safe_edit(
                job.status,
                job.head + f"⬆️ <b>Uploading to Dump</b> {cur * 100 // max(total, 1)}%\n"
                f"{_size(cur)} / {_size(total)}",
                _cancel_kb(job),
            )

    sent = await client.send_document(
        DUMP_ID, document=job.tmp, file_name=name, force_document=True,
        caption=f"<code>{html.escape(name)}</code>", parse_mode=enums.ParseMode.HTML, progress=progress,
    )
    if sent is None:
        raise Cancelled()
    return sent


async def _post_to_dump(job):
    """Upload start aagumbodhu: NEW channel post-a DUMP-ku mudhalla anuppum."""
    sent = await job.client.copy_message(DUMP_ID, NEW_CHANNEL, job.post_id)
    job.dump_post = sent.id


async def _delete_dump(job):
    for mid in (job.dump_post, job.dump_msg):
        if mid:
            try:
                await job.client.delete_messages(DUMP_ID, mid)
            except Exception:
                pass


def _post_link(post_id):
    s = str(NEW_CHANNEL)
    return f"https://t.me/c/{s[4:]}/{post_id}" if s.startswith("-100") else None


async def _do_forward(job):
    """Dump-la irukkira post, appuram file -> target channel."""
    client, target = job.client, job.target
    job.state = "forwarding"
    await _safe_edit(job.status, job.head + f"📤 <b>{html.escape(target['title'])}</b>-ku forward aagudhu...")
    step = "post"
    try:
        send = client.forward_messages if USE_FORWARD_TAG else client.copy_message
        await send(target["id"], DUMP_ID, job.dump_post)     # 1) post (dump-lendhu)
        step = "file"
        await send(target["id"], DUMP_ID, job.dump_msg)      # 2) file (dump-lendhu)
    except Exception as e:
        job.state = "fwd_failed"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Retry", callback_data=f"sfwd:rt:{job.id}"),
                                    InlineKeyboardButton("❌ Cancel", callback_data=f"sfwd:x:{job.id}")]])
        await _safe_edit(job.status, job.head + f"❌ Forward fail ({step}): <code>{html.escape(str(e))[:250]}</code>\n"
                                                 "Bot target channel-la admin-a? Check pannitu 🔁 Retry.", kb)
        return
    job.state = "done"
    if job.preview:
        try:
            await job.preview.delete()
        except Exception:
            pass
    await _safe_edit(job.status, job.head + f"✅ <b>Forward aachu!</b> → <b>{html.escape(target['title'])}</b>")


async def _auto_forward(job):
    job.state = "ready"
    if FORWARD_DELAY > 0:
        await _safe_edit(
            job.status,
            job.head + f"✅ Dump-la save aachu.\n⏳ {FORWARD_DELAY}s-la <b>{html.escape(job.target['title'])}</b>-ku "
                       "automatic-a forward aagum. Name thappaa irundha Cancel 👇",
            _cancel_kb(job),
        )
        for _ in range(FORWARD_DELAY):
            await asyncio.sleep(1)
            if job.cancelled or job.state != "ready":
                return          # Cancel callback already cleanup pannidum
    if job.cancelled or job.state != "ready":
        return
    await _do_forward(job)


async def _cleanup_cancel(job, note="❌ <b>Cancel aachu</b> — edhuvum forward aagala."):
    job.state = "cancelled"
    await _delete_dump(job)
    if job.preview:
        try:
            await job.preview.delete()
        except Exception:
            pass
    await _safe_edit(job.status, note)


async def process(job):
    client = job.client
    try:
        job.state = "running"
        if not NEW_CHANNEL or not DUMP_ID:
            raise JobError("NEW_CHANNEL / DUMP_ID set pannala. <code>plugins/series_forward.py</code> top-la podunga.")

        _, targets = await _cfg()
        if not targets:
            raise JobError("Target channel illa. Mudhalla <code>/addtarget -100xxxxxxxxxx</code> pannunga.")
        job.target = targets[0]

        # ---------- 1. NAME
        size = 0
        if job.kind == "url":
            job.name, size = await _probe(job)
        else:
            media = job.message.document or job.message.video or job.message.audio
            cap = (job.message.caption or "").strip().splitlines()
            job.name = job.custom or media.file_name or (cap[0] if cap else None)
            if not job.name:
                raise JobError("File name kidaikkala. Caption-la name type panni anuppunga.")
        job.check()

        job.title, job.season = parse_name(job.name)
        if not norm(job.title):
            raise JobError(f"Name kandupidikka mudiyala:\n<code>{html.escape(job.name)}</code>")

        # ---------- 2. POST in NEW channel
        found = await find_post(job.title, job.season)
        if not found:
            n = await mdb[POSTS].count_documents({})
            raise JobError(
                f"🖼 <b>{html.escape(job.title)}</b> post NEW channel-la kidaikkala.\n"
                f"(Index-la {n} posts irukku{' — /scanposts run pannunga' if n == 0 else ''})\n\n"
                "Post podunga (auto index aagum) allathu name check panni thirumba anuppunga."
            )
        doc, phrase = found
        job.post_id = doc["_id"]
        job.check()

        season = f" • S{job.season:02d}" if job.season else ""
        job.head = (f"🎬 <b>{html.escape(job.title)}</b>{season}\n📁 <code>{html.escape(job.name)}</code>\n"
                    f"🖼 Post: #{job.post_id}  •  🎯 {html.escape(job.target['title'])}\n\n")
        head = job.head

        # post preview neenga PM-la paakka (name correct-a nu check panna)
        try:
            job.preview = await client.copy_message(job.chat_id, NEW_CHANNEL, job.post_id)
        except Exception as e:
            logger.error(f"sfwd preview: {e}")

        # ---------- 3. DUMP
        if job.kind == "url":
            if URL_SEM.locked():
                await _safe_edit(job.status, head + "⏳ Queue-la irukku (munnaadi oru download odudhu)...", _cancel_kb(job))
            async with URL_SEM:
                job.check()
                await _safe_edit(job.status, head + "⬇️ Download start...", _cancel_kb(job))
                await _download(job, job.name, size)
                job.check()
                await _post_to_dump(job)          # 1) post -> dump (upload start)
                job.check()
                sent = await _upload(job, job.name)   # 2) file -> dump
        else:
            await _safe_edit(job.status, head + "📦 Dump-ku post + file copy aagudhu...", _cancel_kb(job))
            await _post_to_dump(job)              # 1) post -> dump
            job.check()
            sent = await job.message.copy(DUMP_ID)    # 2) file -> dump
        job.dump_msg = sent.id
        job.check()

        # ---------- 4. AUTO FORWARD  (dump -> target)
        await _auto_forward(job)

    except Cancelled:
        await _cleanup_cancel(job)
    except JobError as e:
        job.state = "failed"
        await _safe_edit(job.status, f"⚠️ {e}")
    except Exception as e:
        job.state = "failed"
        logger.exception("sfwd process error")
        await _safe_edit(job.status, f"❌ Error: <code>{html.escape(str(e))[:300]}</code>")
        await _delete_dump(job)
    finally:
        if job.tmp and os.path.exists(job.tmp):
            try:
                os.remove(job.tmp)
            except Exception:
                pass


# ====================================================================
#                      INCOMING  (file / URL)
# ====================================================================
async def _job_filter_func(_, __, m):
    if m.media:
        if not (m.document or m.video or m.audio):
            return False
    else:
        txt = m.text or ""
        if not txt or txt.startswith("/") or not _extract_url(txt):
            return False
    enabled, _t = await _cfg()
    return enabled


job_filter = filters.create(_job_filter_func)


@Client.on_message(filters.private & filters.incoming & filters.user(ADMINS) & job_filter, group=-3)
async def new_job(client, message):
    try:
        for k, j in list(JOBS.items()):
            if time.time() - j.ts > 6 * 3600:
                JOBS.pop(k, None)

        if message.media:
            job = Job(client, message, "file")
            job.custom = None
        else:
            url = _extract_url(message.text)
            after = message.text.split(url, 1)[1].strip(" \t|\n") if url in message.text else ""
            custom = after.splitlines()[0].strip() if after else None
            job = Job(client, message, "url", url=url, custom=custom)

        JOBS[job.id] = job
        job.status = await message.reply("🔎 Name check pannitu irukken...", quote=True, reply_markup=_cancel_kb(job))
        asyncio.create_task(process(job))
    except Exception:
        logger.exception("sfwd new_job")
    message.stop_propagation()   # pm_filter (search) / index.py-ku pogaama thadukkum


# ====================================================================
#                           BUTTONS
# ====================================================================
@Client.on_callback_query(filters.regex(r"^sfwd:") & filters.user(ADMINS), group=-2)
async def sfwd_cb(client, q):
    parts = q.data.split(":")
    action, job = parts[1], JOBS.get(parts[2])
    if not job:
        return await q.answer("Idhu expire aayiduchu. File/link-a thirumba anuppunga.", show_alert=True)

    if action == "x":
        if job.state in ("done", "forwarding", "cancelled"):
            return await q.answer("Already mudinjuduchu.", show_alert=True)
        job.cancelled = True
        if job.state in ("ready", "fwd_failed"):
            await _cleanup_cancel(job)
        await q.answer("Cancel pannitten ✅")

    elif action == "rt":
        if job.state != "fwd_failed":
            return await q.answer("Idhu already process aachu / cancel aachu.", show_alert=True)
        await q.answer("Retry...")
        await _do_forward(job)
