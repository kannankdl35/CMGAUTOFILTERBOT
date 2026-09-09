# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import logging
from pyrogram import Client
from pyrogram.types import InlineQuery, InlineQueryResultCachedDocument

from info import CACHE_TIME, CUSTOM_FILE_CAPTION
from utils import get_size, temp
from database.ia_filterdb import get_search_results

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Telegram allows up to 50 inline results per answer; keep it modest so each
# page loads fast and pagination (scrolling) still works via next_offset.
RESULTS_PER_PAGE = 20


def _clean_name(file_name: str) -> str:
    """Strip promo tags / links that sometimes get embedded in file names."""
    return ' '.join(
        filter(
            lambda x: not x.startswith('@') and not x.startswith('http')
            and not x.startswith('www.') and not x.startswith('t.me'),
            (file_name or "Unknown").split()
        )
    )


def _build_caption(name: str, size: str) -> str:
    if CUSTOM_FILE_CAPTION:
        try:
            return CUSTOM_FILE_CAPTION.format(file_name=name, file_size=size, file_caption='')
        except Exception:
            pass
    return f"<code>{name}</code>"


@Client.on_inline_query()
async def answer_inline_query(client, inline_query: InlineQuery):
    if inline_query.from_user and inline_query.from_user.id in temp.BANNED_USERS:
        return

    query = inline_query.query.strip()

    try:
        offset = int(inline_query.offset or 0)
    except ValueError:
        offset = 0

    if not query:
        await inline_query.answer(
            results=[],
            cache_time=0,
            switch_pm_text="Type a movie or series name to search 🔎",
            switch_pm_parameter="start",
        )
        return

    user_id = inline_query.from_user.id if inline_query.from_user else 0
    files, next_offset, total_results = await get_search_results(
        user_id, query, offset=offset, max_results=RESULTS_PER_PAGE
    )

    if not files:
        await inline_query.answer(
            results=[],
            cache_time=0,
            switch_pm_text=f"😔 No results for '{query}'",
            switch_pm_parameter="start",
        )
        return

    results = []
    for f in files:
        name = _clean_name(f.get('file_name'))
        size = get_size(f.get('file_size', 0))
        results.append(
            InlineQueryResultCachedDocument(
                title=name,
                description=f"Size: {size}",
                document_file_id=f['file_id'],
                caption=_build_caption(name, size),
            )
        )

    await inline_query.answer(
        results=results,
        cache_time=CACHE_TIME,
        next_offset=str(next_offset) if next_offset != "" else "",
        switch_pm_text=f"🔎 {total_results} result(s) found for '{query}'",
        switch_pm_parameter="start",
    )
