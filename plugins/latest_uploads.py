# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import re, logging
from pyrogram import Client, filters, enums

from utils import temp, get_size
from database.ia_filterdb import get_recent_files

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------- Tunables ----------------
RECENT_DAYS = 3     # "recently added" window, in days
MAX_FETCH = 300     # max raw docs pulled from DB before movie/series classification
MAX_DISPLAY = 30    # max hyperlinks shown per command (keeps message under Telegram's 4096 char limit)

# Simple season/episode heuristic: if the filename matches this, treat it as a
# "series" file, otherwise treat it as a "movie" file.
SERIES_PATTERN = re.compile(
    r'(S\d{1,2}[\s\.\-_]?E\d{1,3})'      # S01E02, S01.E02, S1E2
    r'|(Season[\s\.\-_]?\d{1,2})'        # Season 1, Season.02
    r'|(\d{1,2}x\d{1,3})'                # 1x01
    r'|(\bEP?[\s\.\-_]?\d{1,3}\b)',      # EP01, E01
    re.IGNORECASE
)


def is_series(file_name: str) -> bool:
    """Return True if the filename looks like a series/episode, else False (movie)."""
    return bool(SERIES_PATTERN.search(file_name or ""))


def clean_title(file_name: str) -> str:
    """Strip promo tags / links that sometimes get embedded in file names."""
    return ' '.join(
        filter(
            lambda x: not x.startswith('@') and not x.startswith('http')
            and not x.startswith('www.') and not x.startswith('t.me'),
            (file_name or "").split()
        )
    )


async def build_list_text(kind: str) -> str:
    """kind = 'movie' or 'series' -> returns the ready-to-send HTML message text."""
    files = await get_recent_files(days=RECENT_DAYS, max_results=MAX_FETCH)

    wanted_series = (kind == "series")
    matched = [f for f in files if is_series(f.get('file_name', '')) == wanted_series]

    total_found = len(matched)
    matched = matched[:MAX_DISPLAY]

    label = "series" if wanted_series else "movies"

    if not matched:
        return f"<b>😔 No {label} indexed in the last {RECENT_DAYS} day(s).</b>"

    heading = "📺 <b>Latest Series</b>" if wanted_series else "🎬 <b>Latest Movies</b>"
    lines = [f"{heading} <i>(Last {RECENT_DAYS} Days)</i>"]

    for f in matched:
        size = get_size(f.get('file_size', 0))
        name = clean_title(f.get('file_name', 'Unknown'))
        link = f"https://telegram.me/{temp.U_NAME}?start=file_{f['file_id']}"
        lines.append(f"📁 <a href='{link}'>[{size}] {name}</a>")

    if total_found > MAX_DISPLAY:
        lines.append(f"<i>...and {total_found - MAX_DISPLAY} more not shown. Showing latest {MAX_DISPLAY}.</i>")

    lines.append(f"<b>Total Found:</b> {total_found}")
    return "\n\n".join(lines)


@Client.on_message(filters.command("movies") & (filters.private | filters.group))
async def latest_movies(client, message):
    text = await build_list_text("movie")
    await message.reply_text(
        text,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True,
        quote=True
    )


@Client.on_message(filters.command("series") & (filters.private | filters.group))
async def latest_series(client, message):
    text = await build_list_text("series")
    await message.reply_text(
        text,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True,
        quote=True
    )
