"""
SETTINGS EXPORT / IMPORT
------------------------
Export : /settings -> "📤 Export Settings"  (or /export_settings)
         -> Goku_Settings_<id>.json file bot anuppum (prefix, suffix, caption, auto-rename format,
            thumbnail, upload type, rename mode, audio, auto post, post mode, watermark, size)
Import : vera account-la bot-ku antha .json file-a anuppunga  (or /settings -> "📥 Import Settings")
         -> athu antha account-oda settings-a maathidum.
Import eppavum file anuppuravanga OWN settings-a mattum thaan maathum.
"""
import io, json, time, base64, datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from helper.database import goku_stark
from config import Config
from plugins.post_forward import auto_delete

EXPORT_TYPE = "goku_rename_settings"
EXPORT_VERSION = 1
IMPORT_WAIT_SECS = 300            # Import button click panni file anuppa 5 min time
MAX_IMPORT_BYTES = 4 * 1024 * 1024
MAX_THUMB_BYTES = 2 * 1024 * 1024
SCALE_MIN, SCALE_MAX = 0.4, 3.0   # poster.py-la irukkura same limit
NOTICE_SECS = 15                  # import/export notice auto-delete

# user_id -> {"ts", "chat_id", "prompt_id"}   (Import button click pannitu file-ku wait pannura state)
WAIT_IMPORT = {}

TEXT_FIELDS = {"prefix": 200, "suffix": 200, "caption": 2000, "format_template": 500, "watermark": 60}
ENUM_FIELDS = {
    "upload_type": (None, "doc", "video"),
    "rename_mode": ("auto", "manual"),
    "audio_lang": (None, "tam", "tel", "hin", "eng", "mal"),
    "post_mode": ("each", "once"),
}
ENUM_DEFAULTS = {"upload_type": None, "rename_mode": "auto", "audio_lang": None, "post_mode": "each"}


def _is_admin(user_id):
    return user_id in Config.ADMIN


def _is_waiting(user_id):
    st = WAIT_IMPORT.get(user_id)
    if not st:
        return False
    if time.time() - st["ts"] > IMPORT_WAIT_SECS:
        WAIT_IMPORT.pop(user_id, None)
        return False
    return True


# =====================================================================
#  EXPORT
# =====================================================================
def _collect_settings(user_data, is_admin):
    s = {k: user_data.get(k) for k in TEXT_FIELDS}
    s["format_template"] = user_data.get("format_template") or "{filename}"
    for k, default in ENUM_DEFAULTS.items():
        s[k] = user_data.get(k, default)
    s["autopost"] = bool(user_data.get("autopost", True))
    try:
        s["wm_scale"] = float(user_data.get("wm_scale", 1.0))
    except Exception:
        s["wm_scale"] = 1.0
    if is_admin:   # dump channel admin-ku mattum
        s["dump_id"] = user_data.get("dump_id")
        s["dump_status"] = bool(user_data.get("dump_status", False))
    return s


async def do_export(client, user_id, chat_id):
    user_data = await goku_stark.get_user_data(user_id)
    if not user_data:
        raise ValueError("Settings onnum kedaikkala. Munnaadi /start pannunga.")

    payload = {
        "type": EXPORT_TYPE,
        "version": EXPORT_VERSION,
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "settings": _collect_settings(user_data, _is_admin(user_id)),
        "thumbnail": None,
    }

    thumb_id = user_data.get("file_id")
    if thumb_id:
        thumb = {"file_id": thumb_id}
        try:   # image bytes-um serthu vekkrom -> vera bot/account-laiyum thumbnail kedaikkum
            buf = await client.download_media(thumb_id, in_memory=True)
            raw = buf.getvalue()
            if len(raw) <= MAX_THUMB_BYTES:
                thumb["b64"] = base64.b64encode(raw).decode()
        except Exception as e:
            print(f"[EXPORT] thumbnail download failed: {e}", flush=True)
        payload["thumbnail"] = thumb

    bio = io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    bio.name = f"Goku_Settings_{user_id}.json"
    await client.send_document(
        chat_id, bio, file_name=bio.name,
        caption=(
            "📤 **Settings Exported!**\n\n"
            "Intha file-a vera account-la bot-ku anuppunga (illa `/import_settings`) "
            "-> ellaa settings-um apply aagum.\n\n"
            "⚠️ Intha file-a yaarukum share pannaadheenga."
        )
    )


@Client.on_callback_query(filters.regex(r"^export_settings$"), group=2)
async def export_cb(client, query: CallbackQuery):
    await query.answer("📤 Exporting...")
    try:
        await do_export(client, query.from_user.id, query.message.chat.id)
    except Exception as e:
        err = await client.send_message(query.message.chat.id, f"❌ **Export failed:** `{e}`")
        auto_delete(err, delay=NOTICE_SECS)


@Client.on_message(filters.private & filters.command("export_settings"))
async def export_cmd(client, message):
    try:
        await do_export(client, message.from_user.id, message.chat.id)
    except Exception as e:
        err = await message.reply_text(f"❌ **Export failed:** `{e}`")
        auto_delete(err, delay=NOTICE_SECS)
    auto_delete(message, delay=NOTICE_SECS)


# =====================================================================
#  IMPORT
# =====================================================================
def parse_settings(data, is_admin):
    """JSON-la irunthu SAFE-aana fields mattum edukkum. Return: updates(dict), thumb(dict|None|False)"""
    if not isinstance(data, dict) or data.get("type") != EXPORT_TYPE:
        raise ValueError("Idhu Goku settings file illa.")
    src = data.get("settings")
    if not isinstance(src, dict):
        raise ValueError("File-la settings data illa.")

    upd = {}
    for k, max_len in TEXT_FIELDS.items():
        if k in src and (src[k] is None or (isinstance(src[k], str) and len(src[k]) <= max_len)):
            upd[k] = src[k] or None
    if "format_template" in upd and not upd["format_template"]:
        upd["format_template"] = "{filename}"

    for k, allowed in ENUM_FIELDS.items():
        if k in src and src[k] in allowed:
            upd[k] = src[k]

    if isinstance(src.get("autopost"), bool):
        upd["autopost"] = src["autopost"]

    sc = src.get("wm_scale")
    if isinstance(sc, (int, float)) and not isinstance(sc, bool):
        upd["wm_scale"] = round(min(SCALE_MAX, max(SCALE_MIN, float(sc))), 1)

    if is_admin:   # dump channel: importer-um admin-aa irundha mattum
        if isinstance(src.get("dump_id"), int) and not isinstance(src.get("dump_id"), bool):
            upd["dump_id"] = src["dump_id"]
        if isinstance(src.get("dump_status"), bool):
            upd["dump_status"] = src["dump_status"]

    thumb = False                      # False = file-la thumbnail key illa (onnum maathaadhu)
    if "thumbnail" in data:
        thumb = data["thumbnail"] if isinstance(data["thumbnail"], dict) else None   # None = thumbnail clear
    return upd, thumb


async def _restore_thumb(client, chat_id, th):
    """Thumbnail image-a thirumba upload panni puthu file_id vaanguvom. Mudiyala na pazhaya file_id."""
    b64 = th.get("b64")
    if isinstance(b64, str) and b64:
        try:
            raw = base64.b64decode(b64, validate=True)
            if len(raw) <= MAX_THUMB_BYTES:
                bio = io.BytesIO(raw)
                bio.name = "thumb.jpg"
                sent = await client.send_photo(chat_id, bio)
                fid = sent.photo.file_id
                try:
                    await sent.delete()
                except Exception:
                    pass
                return fid
        except Exception as e:
            print(f"[IMPORT] thumbnail restore failed: {e}", flush=True)
    fid = th.get("file_id")
    return fid if isinstance(fid, str) and fid else None


async def do_import(client, doc_msg, user_id, anchor):
    """doc_msg = JSON file irukkura message | anchor = bot reply panna / clean panna vendiya user message"""
    st = WAIT_IMPORT.pop(user_id, None)
    status = await anchor.reply_text("`⏳ Importing settings...`", quote=True)
    notes = []
    try:
        doc = doc_msg.document
        if doc.file_size and doc.file_size > MAX_IMPORT_BYTES:
            raise ValueError("File romba perusa irukku.")
        buf = await client.download_media(doc_msg, in_memory=True)
        try:
            data = json.loads(buf.getvalue().decode("utf-8"))
        except ValueError:
            raise ValueError("Valid settings file illa (JSON padikka mudiyala).")

        updates, thumb = parse_settings(data, _is_admin(user_id))

        thumb_state = "unchanged"
        if thumb is None:
            updates["file_id"] = None
            thumb_state = "cleared"
        elif thumb:
            fid = await _restore_thumb(client, doc_msg.chat.id, thumb)
            if fid:
                updates["file_id"] = fid
                thumb_state = "restored"
            else:
                notes.append("⚠️ Thumbnail restore aagala (pazhaya thumbnail appadiyae irukku)")

        if not updates:
            raise ValueError("Apply panna settings onnum file-la illa.")

        if not await goku_stark.is_user_exist(user_id):          # puthu account (innum /start pannala)
            await goku_stark.col.insert_one(goku_stark.new_user(user_id))
        await goku_stark.col.update_one({"_id": int(user_id)}, {"$set": updates})

        lines = [
            "✅ **Settings Imported!**\n",
            f"📝 **Prefix:** `{updates.get('prefix') or '—'}` | **Suffix:** `{updates.get('suffix') or '—'}`" if ("prefix" in updates or "suffix" in updates) else None,
            f"🤖 **Auto Rename Format:** `{updates['format_template']}`" if "format_template" in updates else None,
            f"🖼 **Thumbnail:** {thumb_state}" if thumb_state != "unchanged" else None,
            f"📦 **Applied:** {len(updates)} settings",
            *notes,
        ]
        await status.edit("\n".join(l for l in lines if l))
    except Exception as e:
        await status.edit(f"❌ **Import failed:** `{e}`")

    if st and st.get("prompt_id"):
        try:
            await client.delete_messages(st["chat_id"], st["prompt_id"])
        except Exception:
            pass
    auto_delete(status, anchor, delay=NOTICE_SECS)


async def _import_filter(_, __, message):
    doc = message.document
    if not (message.from_user and doc):
        return False
    name = (doc.file_name or "").lower()
    if name.startswith("goku_settings") and name.endswith(".json"):
        return True                                   # export panna file -> thaaney import
    if _is_waiting(message.from_user.id):             # Import button click pannitu vera .json anuppina
        return name.endswith(".json") or (doc.mime_type or "") == "application/json"
    return False

import_file_filter = filters.create(_import_filter)


# group=-1 -> file_rename.py-oda "document = rename" handler-ku MUNNADI run aagi, athaiya stop pannum
@Client.on_message(filters.private & import_file_filter, group=-1)
async def import_file_handler(client, message):
    await do_import(client, message, message.from_user.id, message)
    message.stop_propagation()


@Client.on_callback_query(filters.regex(r"^import_settings$"), group=2)
async def import_cb(client, query: CallbackQuery):
    WAIT_IMPORT[query.from_user.id] = {"ts": time.time(), "chat_id": query.message.chat.id, "prompt_id": query.message.id}
    await query.message.edit_text(
        "**📥 Import Settings**\n\n"
        "Export pannina `Goku_Settings_xxx.json` file-a ippo anuppunga.\n"
        "(5 min-kulla anuppunga)",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_settings")]])
    )
    await query.answer()


@Client.on_callback_query(filters.regex(r"^back_to_settings$"), group=1)
async def import_cancel_cb(client, query: CallbackQuery):
    WAIT_IMPORT.pop(query.from_user.id, None)        # Back click -> import wait cancel (menu settings.py kaattum)


@Client.on_message(filters.private & filters.command("import_settings"))
async def import_cmd(client, message):
    user_id = message.from_user.id
    src = message.reply_to_message
    if src and src.document:                          # JSON file-ku reply panni /import_settings
        return await do_import(client, src, user_id, message)
    prompt = await message.reply_text(
        "**📥 Import Settings**\n\nExport pannina `Goku_Settings_xxx.json` file-a ippo anuppunga "
        "(illa antha file-ku reply panni `/import_settings` anuppunga).",
        quote=True
    )
    WAIT_IMPORT[user_id] = {"ts": time.time(), "chat_id": prompt.chat.id, "prompt_id": prompt.id}
