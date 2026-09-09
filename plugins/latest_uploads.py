# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import re, sys, hashlib, logging
from pyrogram import Client, filters, enums, StopPropagation

from utils import temp
from database.ia_filterdb import get_recent_files

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# In-memory map: short key -> movie/series title, filled in each time /movies
# or /series builds a list, read back when a numbered title is clicked.
# (Same "temp cache" pattern this bot already uses for temp.SHORT / temp.GETALL.)
if not hasattr(temp, "RECENT_QUERY"):
    temp.RECENT_QUERY = {}

# ---------------- Tunables ----------------
RECENT_DAYS = 3     # "recently added" window, in days
MAX_FETCH = 300     # max raw docs pulled from DB before movie/series classification
MAX_DISPLAY = 30    # max titles listed per command

# Simple season/episode heuristic: if the filename matches this, treat it as a
# "series" file, otherwise treat it as a "movie" file.
SERIES_PATTERN = re.compile(
    r'(S\d{1,2}[\s\.\-_]?E\d{1,3})'      # S01E02, S01.E02, S1E2
    r'|(Season[\s\.\-_]?\d{1,2})'        # Season 1, Season.02
    r'|(\d{1,2}x\d{1,3})'                # 1x01
    r'|(\bEP?[\s\.\-_]?\d{1,3}\b)',      # EP01, E01
    re.IGNORECASE
)

# Marks where the "technical" part of a release filename starts, so we can cut
# it off and keep just the title (+ year) for grouping/de-duplication.
QUALITY_SPLIT = re.compile(r'\b(\d{3,4}p|4K)\b', re.IGNORECASE)

# Same idea for series episodes, but also cuts at the season/episode marker
# (whichever comes first: S01E02, quality tag, etc.) so every episode of the
# same show collapses to just "Title Year" instead of one entry per episode.
SERIES_CUT_PATTERN = re.compile(
    r'(S\d{1,2}[\s\.\-_]?E\d{1,3})'      # S01E02, S01.E02, S1E2
    r'|(Season[\s\.\-_]?\d{1,2})'        # Season 1, Season.02
    r'|(\d{1,2}x\d{1,3})'                # 1x01
    r'|(\bEP?[\s\.\-_]?\d{1,3}\b)'       # EP01, E01
    r'|(\d{3,4}p|4K)',                   # 1080p, 720p, 4K
    re.IGNORECASE
)

# Pulls a trailing "Title Year" apart so it can be redisplayed as "Title (Year)".
YEAR_SPLIT = re.compile(r'^(.*?)\s+((?:19|20)\d{2})$')


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


def normalize_title(file_name: str) -> str:
    """
    Collapse a release filename down to just 'Title Year' by cutting it off at
    the first resolution/quality tag, so different quality files of the same
    movie/episode group under one entry.
    """
    cleaned = clean_title(file_name)
    match = QUALITY_SPLIT.search(cleaned)
    if match:
        cleaned = cleaned[:match.start()]
    cleaned = re.sub(r'[\s\-\.]+$', '', cleaned).strip()
    return cleaned or "Unknown"


def normalize_series_title(file_name: str) -> str:
    """
    Same as normalize_title(), but for series: cuts at the season/episode
    marker OR the quality tag, whichever appears first, so "The Gentlemen
    2024 S02E08 1080p ..." and "The Gentlemen 2024 S02E07 720p ..." both
    normalize to just "The Gentlemen 2024" instead of staying per-episode.
    """
    cleaned = clean_title(file_name)
    match = SERIES_CUT_PATTERN.search(cleaned)
    if match:
        cleaned = cleaned[:match.start()]
    cleaned = re.sub(r'[\s\-\.]+$', '', cleaned).strip()
    return cleaned or "Unknown"


def display_title(normalized: str) -> str:
    """'One Night Only 2026' -> 'One Night Only (2026)' for the numbered list."""
    m = YEAR_SPLIT.match(normalized)
    if m:
        return f"{m.group(1).strip()} ({m.group(2)})"
    return normalized


def make_query_key(title: str) -> str:
    """Short, URL-safe key that maps back to the full title via temp.RECENT_QUERY."""
    key = hashlib.sha1(title.encode('utf-8')).hexdigest()[:10]
    temp.RECENT_QUERY[key] = title
    return key


async def build_list_text(kind: str) -> str:
    """kind = 'movie' or 'series' -> numbered, clickable list like the requested design."""
    files = await get_recent_files(days=RECENT_DAYS, max_results=MAX_FETCH)

    wanted_series = (kind == "series")
    matched = [f for f in files if is_series(f.get('file_name', '')) == wanted_series]

    # De-duplicate to one entry per title, keeping newest-first order.
    # Series use their own normalizer so every episode of a show collapses
    # into one entry; movies keep the exact behavior they already had.
    normalizer = normalize_series_title if wanted_series else normalize_title
    order = []
    seen = set()
    for f in matched:
        title = normalizer(f.get('file_name', ''))
        if title not in seen:
            seen.add(title)
            order.append(title)

    label = "Series" if wanted_series else "Movies"
    if not order:
        return f"<i>😔 No {label.lower()} indexed in the last {RECENT_DAYS} day(s).</i>"

    total_found = len(order)
    order = order[:MAX_DISPLAY]
    icon = "📺" if wanted_series else "🎬"
    noun = "series" if wanted_series else "movie"

    lines = [f"{icon} <b><i>Latest {label} Added to Bot DB</i></b> ⬇️", ""]
    for i, title in enumerate(order, start=1):
        key = make_query_key(title)
        link = f"https://telegram.me/{temp.U_NAME}?start=rq_{key}"
        lines.append(f"{i}. <a href='{link}'>{display_title(title)}</a>")

    if total_found > MAX_DISPLAY:
        lines.append("")
        lines.append(f"<i>...and {total_found - MAX_DISPLAY} more not shown.</i>")

    lines.append("")
    lines.append(f"<i>Click the name of any {noun} to get the files...</i>")

    return "\n".join(lines)


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


class _QueryMessage:
    """
    Thin proxy around the real incoming /start message: forwards every
    attribute/method to it (chat, from_user, id, delete, ...) EXCEPT `.text`,
    which is overridden to the movie/series title.

    Why this is needed: auto_filter() (plugins/pm_filter.py) only reads
    `.text` off its `msg` argument to validate the request (reject anything
    starting with "/", enforce a length limit) — the actual search string
    always comes from its separate `name` argument. Since our trigger is
    literally the message "/start rq_xxxxx", passing it straight through
    would fail that "doesn't start with /" check. This proxy fixes just that
    one attribute while leaving everything else (chat info, user info,
    delete(), etc.) pointing at the real message.
    """
    def __init__(self, real_message, fake_text):
        self._real = real_message
        self._fake_text = fake_text

    @property
    def text(self):
        return self._fake_text

    def __getattr__(self, item):
        return getattr(self._real, item)


# ---------------------------------------------------------------------------
# Handles the "rq_<key>" deep link created above: runs the SAME auto_filter()
# search the bot runs for a normal typed query, giving the identical
# header/buttons/pagination screen a real search produces.
#
# Registered in group=-1 so it runs BEFORE the main /start handler in
# plugins/commands.py. If the payload isn't one of ours, it just returns and
# lets that handler process the message exactly as it always has.
# ---------------------------------------------------------------------------
@Client.on_message(filters.command("start") & filters.incoming, group=-1)
async def open_recent_title(client, message):
    if len(message.command) != 2 or not message.command[1].startswith("rq_"):
        return  # not our payload, let the normal /start handler in commands.py handle it

    if message.from_user and message.from_user.id in temp.BANNED_USERS:
        return

    key = message.command[1][3:]
    title = temp.RECENT_QUERY.get(key)

    if not title:
        await message.reply_text(
            "<i>⚠️ This list has expired (the bot may have restarted).\n\n"
            "Please send /movies or /series again to get a fresh list.</i>"
        )
        raise StopPropagation

    # plugins/pm_filter.py is loaded by bot.py's plugin loader at startup; we look
    # it up at call time (never import it directly) so its handlers only ever get
    # registered once.
    pm_filter = sys.modules.get("plugins.pm_filter")
    if pm_filter is None:
        await message.reply_text("<i>⚠️ Search is temporarily unavailable, please try again shortly.</i>")
        raise StopPropagation

    reply_msg = await client.send_message(
        message.chat.id,
        f"<b><i>Searching For {title} 🔍</i></b>",
        reply_to_message_id=message.id
    )
    fake_message = _QueryMessage(message, title)
    await pm_filter.auto_filter(client, title, fake_message, reply_msg, True)
    raise StopPropagation
