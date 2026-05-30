import logging
import secrets
import time
from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config


logger = logging.getLogger(__name__)

TELEGRAM_SAFE_MESSAGE_LIMIT = 3800
CB_P2P_PAGE_PREFIX = "p2pp:"
CB_P2P_PAGE_NOOP = "p2pp:noop"


@dataclass
class P2PPage:
    text: str
    reply_markup: InlineKeyboardMarkup | None = None


@dataclass
class P2PPaginationSession:
    owner_telegram_id: int
    title: str
    page_groups: list[list[str]]
    page_url_groups: list[list[str | None]]
    page_starts: list[int]
    total_orders: int
    expires_at: float


_pagination_sessions: dict[str, P2PPaginationSession] = {}


def create_pagination_session(
    *,
    owner_telegram_id: int,
    title: str,
    blocks: list[str],
    order_urls: list[str | None] | None = None,
    page_size: int | None = None,
) -> str:
    cleanup_expired_sessions()
    effective_page_size = page_size or get_orders_per_page()

    page_groups, page_url_groups = build_page_groups(
        title=title,
        blocks=blocks,
        order_urls=order_urls,
        page_size=effective_page_size,
    )
    session_id = secrets.token_urlsafe(8)
    ttl_seconds = get_pagination_ttl_seconds()

    _pagination_sessions[session_id] = P2PPaginationSession(
        owner_telegram_id=owner_telegram_id,
        title=title,
        page_groups=page_groups,
        page_url_groups=page_url_groups,
        page_starts=build_page_starts(page_groups),
        total_orders=len(blocks),
        expires_at=time.monotonic() + ttl_seconds,
    )

    logger.info(
        "P2P pagination session created: session=%s owner=%s pages=%s orders=%s page_size=%s ttl=%ss",
        session_id,
        owner_telegram_id,
        len(page_groups),
        len(blocks),
        effective_page_size,
        ttl_seconds,
    )

    return session_id


def get_pagination_page(
    *,
    session_id: str,
    page_index: int,
    telegram_id: int,
) -> P2PPage | None:
    cleanup_expired_sessions()
    session = _pagination_sessions.get(session_id)

    if not session:
        return None

    if session.owner_telegram_id != telegram_id:
        return None

    page_index = clamp_page_index(page_index, len(session.page_groups))
    return build_pagination_page(session_id, session, page_index)


def get_pagination_page_from_callback(
    callback_data: str,
    telegram_id: int,
) -> P2PPage | None:
    parsed = parse_page_callback(callback_data)

    if not parsed:
        return None

    session_id, page_index = parsed

    return get_pagination_page(
        session_id=session_id,
        page_index=page_index,
        telegram_id=telegram_id,
    )


def build_page_groups(
    *,
    title: str,
    blocks: list[str],
    order_urls: list[str | None] | None = None,
    page_size: int,
) -> tuple[list[list[str]], list[list[str | None]]]:
    if not blocks:
        return [[]], [[]]

    page_size = max(1, page_size)
    normalized_urls = normalize_order_urls(order_urls, len(blocks))
    groups = []
    url_groups = []
    current_group: list[str] = []
    current_url_group: list[str | None] = []

    for block, order_url in zip(blocks, normalized_urls):
        candidate_group = [*current_group, block]
        candidate_text = format_page_text(
            title=title,
            blocks=candidate_group,
            page_number=999,
            total_pages=999,
            start_order=999,
            total_orders=999,
        )

        if (
            current_group
            and (
                len(current_group) >= page_size
                or len(candidate_text) > TELEGRAM_SAFE_MESSAGE_LIMIT
            )
        ):
            groups.append(current_group)
            url_groups.append(current_url_group)
            current_group = [block]
            current_url_group = [order_url]
            continue

        current_group = candidate_group
        current_url_group = [*current_url_group, order_url]

    if current_group:
        groups.append(current_group)
        url_groups.append(current_url_group)

    return groups or [[]], url_groups or [[]]


def normalize_order_urls(
    order_urls: list[str | None] | None,
    blocks_count: int,
) -> list[str | None]:
    urls = list(order_urls or [])

    if len(urls) < blocks_count:
        urls.extend([None] * (blocks_count - len(urls)))

    return urls[:blocks_count]


def build_page_starts(page_groups: list[list[str]]) -> list[int]:
    starts = []
    current_start = 1

    for group in page_groups:
        starts.append(current_start)
        current_start += len(group)

    return starts


def build_pagination_page(
    session_id: str,
    session: P2PPaginationSession,
    page_index: int,
) -> P2PPage:
    total_pages = len(session.page_groups)
    blocks = session.page_groups[page_index]
    order_urls = session.page_url_groups[page_index]
    start_order = session.page_starts[page_index]

    return P2PPage(
        text=format_page_text(
            title=session.title,
            blocks=blocks,
            page_number=page_index + 1,
            total_pages=total_pages,
            start_order=start_order,
            total_orders=session.total_orders,
        ),
        reply_markup=build_pagination_keyboard(
            session_id,
            page_index,
            total_pages,
            order_urls=order_urls,
            start_order=start_order,
        ),
    )


def format_page_text(
    *,
    title: str,
    blocks: list[str],
    page_number: int,
    total_pages: int,
    start_order: int,
    total_orders: int,
) -> str:
    text = f"<b>{title}</b>"

    if blocks:
        text = f"{text}\n\n" + "\n\n".join(blocks)

    if total_pages > 1:
        end_order = start_order + len(blocks) - 1
        text = (
            f"{text}\n\n"
            f"<i>Сторінка {page_number}/{total_pages} "
            f"• Ордери {start_order}-{end_order} з {total_orders}</i>"
        )

    return text


def build_pagination_keyboard(
    session_id: str,
    page_index: int,
    total_pages: int,
    *,
    order_urls: list[str | None],
    start_order: int,
) -> InlineKeyboardMarkup | None:
    rows = build_order_url_rows(order_urls, start_order)

    if total_pages > 1:
        row = []

        if page_index > 0:
            row.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=build_page_callback(session_id, page_index - 1),
                )
            )

        row.append(
            InlineKeyboardButton(
                text=f"{page_index + 1}/{total_pages}",
                callback_data=CB_P2P_PAGE_NOOP,
            )
        )

        if page_index < total_pages - 1:
            row.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=build_page_callback(session_id, page_index + 1),
                )
            )

        rows.append(row)

    if not rows:
        return None

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_order_url_rows(
    order_urls: list[str | None],
    start_order: int,
) -> list[list[InlineKeyboardButton]]:
    valid_urls = [
        (index, order_url)
        for index, order_url in enumerate(order_urls, start=start_order)
        if is_supported_url(order_url)
    ]

    if not valid_urls:
        return []

    rows = []
    show_numbers = len(valid_urls) > 1

    for order_number, order_url in valid_urls:
        text = "🔗 Відкрити ордер"

        if show_numbers:
            text = f"{text} {order_number}"

        rows.append(
            [
                InlineKeyboardButton(
                    text=text,
                    url=order_url,
                )
            ]
        )

    return rows


def is_supported_url(url: str | None) -> bool:
    return bool(url and url.startswith(("https://", "http://")))


def parse_page_callback(callback_data: str) -> tuple[str, int] | None:
    if not callback_data.startswith(CB_P2P_PAGE_PREFIX):
        return None

    parts = callback_data.split(":")

    if len(parts) != 3:
        return None

    _, session_id, raw_page = parts

    try:
        page_index = int(raw_page)
    except ValueError:
        return None

    return session_id, page_index


def build_page_callback(session_id: str, page_index: int) -> str:
    return f"{CB_P2P_PAGE_PREFIX}{session_id}:{page_index}"


def cleanup_expired_sessions():
    now = time.monotonic()
    expired_session_ids = [
        session_id
        for session_id, session in _pagination_sessions.items()
        if session.expires_at <= now
    ]

    for session_id in expired_session_ids:
        _pagination_sessions.pop(session_id, None)


def clamp_page_index(page_index: int, total_pages: int) -> int:
    if total_pages <= 1:
        return 0

    return max(0, min(page_index, total_pages - 1))


def get_orders_per_page() -> int:
    try:
        return max(1, int(getattr(Config, "P2P_ORDERS_PER_PAGE", 3)))
    except (TypeError, ValueError):
        return 3


def get_pagination_ttl_seconds() -> float:
    try:
        return max(0.0, float(getattr(Config, "P2P_PAGINATION_TTL_SECONDS", 600)))
    except (TypeError, ValueError):
        return 600
