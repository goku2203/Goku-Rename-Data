# (c) @RknDeveloperr
# Rkn Developer 
# Don't Remove Credit 😔
# Telegram Channel @RknDeveloper & @Rkn_Botz
# Developer @RknDeveloperr

import re
from pathlib import Path
from typing import Dict
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from helper.database import digital_botz

# ---------------------------------------------------------------
# CONFIG: indha tag mattum filename START-la irukkum. "" na disable.
# ---------------------------------------------------------------
KEEP_TAG = "@anime_love9"

_EXTS = (
    "mkv|mp4|avi|webm|mov|m4v|ts|flv|wmv|mp3|m4a|flac|aac|ogg|wav|"
    "srt|ass|ssa|vtt|zip|rar|7z|pdf|apk|jpg|jpeg|png"
)
_EXT_RE = re.compile(rf"\.({_EXTS})$", re.IGNORECASE)

_TLDS = "com|net|org|in|cc|site|bz|me|tv|xyz|co|info|club|pro|to|ws|ink|cool|vip|wiki|art"
_SEP = r"[\s_\-.|:]"            # separators after a prefix
_END = rf"(?=[\s_\-.|:\]\)]|$)"  # prefix must end at a separator / end

# --- START-only prefix patterns (all anchored with ^) ---
RE_BOX = re.compile(r"^\s*(?:\[[^\]]*\]|\((?!(?:19|20)\d{2}\))[^)]*\)|\{[^}]*\})\s*")
RE_DOMAIN = re.compile(
    rf"^\s*(?:https?://)?(?:www\.)?[A-Za-z0-9][A-Za-z0-9\-]*(?:\.[A-Za-z0-9\-]+)*\.(?:{_TLDS}){_END}{_SEP}*",
    re.IGNORECASE,
)
# already-spaced domain: "HindiAnimeZone com Liar Game"
# already-spaced or underscored domain: "HindiAnimeZone com" or "HindiAnimeZone_com"
RE_DOMAIN_SPACED = re.compile(rf"^\s*[A-Za-z0-9\-]+[\s_]+(?:{_TLDS})(?=[\s_\-.|:\]\)]|$)\s*[\s_\-.|:]*\s*", re.IGNORECASE)
# other @username (space / - | : after it). Underscore-joined names handled below
RE_USER = re.compile(r"^\s*@[A-Za-z0-9_]{2,32}?(?=[\s\-|:]|$)\s*[\-|:]*\s*")

class EnhancedAutoRenamer:
    def __init__(self):
        self.renaming_operations = {}

    @staticmethod
    def _split_ext(filename: str):
        m = _EXT_RE.search(filename.strip())
        if m:
            return filename.strip()[: m.start()], m.group(1).lower()
        return filename.strip(), ""

    @staticmethod
    def _strip_keep_tag(base: str) -> str:
        """Known tag (@anime_love9) + underscore-joined name -> exact strip."""
        if not KEEP_TAG:
            return base
        m = re.match(rf"^\s*{re.escape(KEEP_TAG)}(?={_SEP}|$)\s*[_\-.|:\s]*", base, re.IGNORECASE)
        return base[m.end():] if m else base

    @classmethod
    def _clean_source_filename(cls, filename: str) -> tuple:
        """Remove ONLY the leading [box] / @username / domain. Middle/end untouched."""
        base, extension = cls._split_ext(filename)
        base = re.sub(r"[\u200b-\u200f\u202a-\u202e\ufeff]", "", base)

        for _ in range(8):
            old = base
            base = RE_BOX.sub("", base)
            base = cls._strip_keep_tag(base)
            base = RE_DOMAIN.sub("", base)
            base = RE_DOMAIN_SPACED.sub("", base)

            # other @username: only strip if something is still left after it
            m = RE_USER.match(base)
            if m and base[m.end():].strip():
                base = base[m.end():]
            if base == old:
                break

        # underscores / dots -> spaces (extension already separated)
        base = base.replace("_", " ").replace(".", " ")
        base = re.sub(r"\s+", " ", base).strip(" -|:")
        return base, extension

    def extract_all_info(self, filename: str) -> Dict:
        cleaned, extension = self._clean_source_filename(filename)
        info = dict(title="", year="", season="", episode="", quality="", source="",
                    video_codec="", audio_codec="", language="", bit_depth="", hdr="",
                    release_group="", original_name=cleaned, extension=extension)

        # TITLE = start-la irundhu first S01 / year / 480p varaikkum mattum
        t = re.search(
            r"^(.+?)(?=\s+(?:S\d{1,2}(?:\s?(?:E|EP)\s?\d{1,4})?(?![A-Za-z0-9])|Season\s*\d+|"
            r"(?:19|20)\d{2}(?!\d)|\d{3,4}p(?![A-Za-z0-9])|4K\b)|$)",
            cleaned, re.IGNORECASE)
        info["title"] = re.sub(r"[\s\-–—:|]+$", "", t.group(1)).strip() if t else cleaned

        y = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", cleaned[len(info["title"]):])
        if y: info["year"] = y.group(1)

        se = re.search(r"(?<![A-Za-z0-9])S(\d{1,2})\s?(?:E|EP)\s?(\d{1,4})(?![A-Za-z0-9])", cleaned, re.IGNORECASE)
        if se:
            info["season"], info["episode"] = f"S{se.group(1).zfill(2)}", f"E{se.group(2).zfill(2)}"
        else:
            s = re.search(r"\bSeason\s*(\d{1,2})\b", cleaned, re.IGNORECASE)
            e = re.search(r"\bEp(?:isode)?\s*(\d{1,4})\b", cleaned, re.IGNORECASE)
            if s: info["season"] = f"S{s.group(1).zfill(2)}"
            if e: info["episode"] = f"E{e.group(1).zfill(2)}"

        q = re.search(r"(?<![A-Za-z0-9])(\d{3,4}p|4K)(?![A-Za-z0-9])", cleaned, re.IGNORECASE) \
            or re.search(r"(?<![A-Za-z0-9])(UHD|HD|SD)(?![A-Za-z0-9])", cleaned, re.IGNORECASE)
        if q: info["quality"] = q.group(1).upper()

        c = re.search(r"(x264|x265|HEVC|H 264|H 265|AVC)", cleaned, re.IGNORECASE)
        if c: info["video_codec"] = c.group(1).lower().replace(" ", ".")
        a = re.search(r"(DDP? ?5 ?1|DD\+? ?5 ?1|DD ?2 ?0|AAC|AC3|DTS)", cleaned, re.IGNORECASE)
        if a: info["audio_codec"] = a.group(1).upper()

        for lang in ["Hindi", "English", "Malayalam", "Tamil", "Telugu", "Kannada", "Dual"]:
            if re.search(rf"\b{lang}\b", cleaned[len(info['title']):], re.IGNORECASE):
                info["language"] = lang
                break
        for src in ["BluRay", "WEBRip", "WEB-DL", "WEB DL", "HDRip", "DVDRip", "TVRip", "AMZN", "Netflix", "Hotstar"]:
            if re.search(re.escape(src), cleaned, re.IGNORECASE):
                info["source"] = src.replace(" ", "-")
                break
        if re.search(r"\b10bit\b", cleaned, re.IGNORECASE): info["bit_depth"] = "10bit"
        if re.search(r"\bhdr\b", cleaned, re.IGNORECASE): info["hdr"] = "HDR"
        return info

    @staticmethod
    def _normalize_output_name(filename: str) -> str:
        """Final name: underscores/dots -> spaces, single @KEEP_TAG at start."""
        stem, ext = Path(filename).stem, Path(filename).suffix
        if not _EXT_RE.search(filename):          # fake suffix (e.g. ".S01E03") -> treat as part of name
            stem, ext = filename, ""
        if KEEP_TAG:
            # template-la tag + underscore irundha ("@anime_love9_{title}") -> munnadiye spaces aakku
            stem = re.sub(rf"^\s*{re.escape(KEEP_TAG)}(?=[_.\s\-]|$)", "", stem, flags=re.IGNORECASE)
        stem = stem.replace("_", " ").replace(".", " ")
        stem = re.sub(r"\s+", " ", stem).strip(" -|:")
        if KEEP_TAG:
            stem = f"{KEEP_TAG} {stem}".strip()
        return f"{stem}{ext}"

    def apply_format_template(self, info: Dict, template: str) -> str:
        ph = {"{title}": info["title"], "{year}": info["year"], "{season}": info["season"],
              "{episode}": info["episode"], "{quality}": info["quality"], "{source}": info["source"],
              "{video_codec}": info["video_codec"], "{audio_codec}": info["audio_codec"],
              "{language}": info["language"], "{bit_depth}": info["bit_depth"], "{hdr}": info["hdr"],
              "{original}": info["original_name"], "{filename}": info["original_name"],
              "{ext}": info["extension"]}
        for k, v in ph.items():
            template = template.replace(k, v)
        template = re.sub(r"\(\s*\)|\[\s*\]", "", template)
        template = re.sub(r"\.+$", "", template) if not info["extension"] else template
        return self._normalize_output_name(template)


@Client.on_message(filters.command(["autorename", "setformat"]))
async def set_format_command(client: Client, message: Message):
    """Set auto rename format template"""
    user_id = message.from_user.id
    
    if len(message.command) < 2:
        current_format = await digital_botz.get_format_template(user_id)
        if current_format:
            reply_text = f"📝 **Your Current Format:**\n`{current_format}`\n\n"
        else:
            reply_text = "❌ No format set yet!\n\n"
        
        reply_text += "**Available Placeholders:**\n"
        placeholders = [
            "`{filename}` - Original File Name. ", 
            "`{title}` - Movie/Series title",
            "`{year}` - Release year",
            "`{season}` - Season number (S01)",
            "`{episode}` - Episode number (E01)",
            "`{quality}` - Video quality (1080p, 4K)",
            "`{source}` - Source type (BluRay, WEBRip)",
            "`{video_codec}` - Video codec (x264, x265)",
            "`{audio_codec}` - Audio codec (DD+5.1)",
            "`{language}` - Language (Hindi, English)",
            "`{bit_depth}` - Bit depth (10bit)",
            "`{hdr}` - HDR info",
            "`{ext}` - File extension"
        ]
        
        reply_text += "\n".join(placeholders)
        reply_text += "\n\n**Example Formats:**\n"
        reply_text += "• `{title} ({year}) {quality} {language}.{ext}`\n"
        reply_text += "• `{title} {season}{episode} {quality}.{ext}`\n"
        reply_text += "• `{title} {quality} {source} {video_codec}.{ext}`\n\n"
        reply_text += "**Usage:** `/autorename {title} ({year}) {quality} {language}.{ext}`"
        
        buttons = [
            [
                InlineKeyboardButton("🎬 Movie Format", callback_data="format_movie"),
                InlineKeyboardButton("📺 Series Format", callback_data="format_series")
            ],
            [
                InlineKeyboardButton("🎵 Music Format", callback_data="format_music"),
                InlineKeyboardButton("📄 Document Format", callback_data="format_doc")
            ],
            [
                InlineKeyboardButton("✍️ Custom Format", callback_data="format_custom")
            ]
        ]
        
        await message.reply_text(
            reply_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return
    
    format_template = " ".join(message.command[1:])
    await digital_botz.add_user_format_template(user_id, format_template)
    await message.reply_text(f"✅ Format set successfully!\n\n`{format_template}`")

@Client.on_callback_query(filters.regex(r"^format_"))
async def format_callback(client, callback_query):
    """Handle format selection callback"""
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    formats = {
        "format_movie": "{title} ({year}) {quality} {source} {video_codec} {language}.{ext}",
        "format_series": "{title} {season}{episode} {quality} {source} {video_codec}.{ext}",
        "format_music": "{title} - {language} ({year}).{ext}",
        "format_doc": "{title} ({quality}).{ext}",
        "format_custom": "{title} {quality} {language}.{ext}"
    }
    
    if data in formats:
        await digital_botz.add_user_format_template(user_id, formats[data])
        await callback_query.message.edit_text(
            f"✅ Format set to **{data.split('_')[1].title()}**!\n\n`{formats[data]}`"
        )
    await callback_query.answer()
