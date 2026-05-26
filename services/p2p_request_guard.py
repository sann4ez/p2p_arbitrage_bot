import asyncio
import copy
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    allowed: bool
    wait_seconds: int = 0


@dataclass
class CacheEntry:
    value: object
    expires_at: float


_user_last_requests: dict[int, float] = {}
_global_last_requests: dict[str, float] = {}
_cache: dict[str, CacheEntry] = {}
_cache_locks: dict[str, asyncio.Lock] = {}
_guard_lock = asyncio.Lock()


async def check_p2p_user_rate_limit(telegram_id: int) -> RateLimitResult:
    cooldown = get_user_cooldown_seconds()

    if cooldown <= 0:
        return RateLimitResult(allowed=True)

    now = time.monotonic()

    async with _guard_lock:
        last_request_at = _user_last_requests.get(telegram_id, 0.0)
        wait_seconds = cooldown - (now - last_request_at)

        if wait_seconds > 0:
            return RateLimitResult(
                allowed=False,
                wait_seconds=math.ceil(wait_seconds),
            )

        _user_last_requests[telegram_id] = now

    return RateLimitResult(allowed=True)


async def get_cached_p2p_orders(
    *,
    exchange: str,
    direction: str,
    rows: int,
    fetcher: Callable[[], Awaitable[list[dict]]],
) -> list[dict]:
    cache_key = f"p2p-orders:{exchange}:{direction}:{rows}"

    return await get_or_fetch_cache(
        cache_key=cache_key,
        exchange=exchange,
        ttl_seconds=get_orders_cache_ttl_seconds(),
        fetcher=fetcher,
    )


async def get_cached_p2p_details(
    *,
    exchange: str,
    item_ids: list[object],
    fetcher: Callable[[list[object]], Awaitable[dict[str, dict]]],
) -> dict[str, dict]:
    unique_item_ids = normalize_unique_ids(item_ids)

    if not unique_item_ids:
        return {}

    now = time.monotonic()
    ttl_seconds = get_details_cache_ttl_seconds()
    details = {}
    missing_item_ids = []

    async with _guard_lock:
        for item_id in unique_item_ids:
            cache_key = get_detail_cache_key(exchange, item_id)
            cached = _cache.get(cache_key)

            if cached and cached.expires_at > now:
                details[item_id] = copy.deepcopy(cached.value)
            else:
                missing_item_ids.append(item_id)

    if not missing_item_ids:
        logger.info(
            "P2P detail cache hit: exchange=%s items=%s",
            exchange,
            len(unique_item_ids),
        )
        return details

    fresh_details = await get_or_fetch_cache(
        cache_key=f"p2p-detail-batch:{exchange}:{','.join(missing_item_ids)}",
        exchange=exchange,
        ttl_seconds=ttl_seconds,
        fetcher=lambda: fetcher(missing_item_ids),
    )

    now = time.monotonic()

    fetched_count = len(fresh_details)
    empty_count = len(missing_item_ids) - fetched_count

    logger.info(
        "P2P detail cache result: exchange=%s requested=%s cached=%s fetched=%s empty=%s",
        exchange,
        len(unique_item_ids),
        len(details),
        fetched_count,
        empty_count,
    )

    async with _guard_lock:
        for item_id in missing_item_ids:
            detail = (
                fresh_details.get(item_id)
                or fresh_details.get(str(item_id))
                or {}
            )

            details[str(item_id)] = copy.deepcopy(detail)
            _cache[get_detail_cache_key(exchange, item_id)] = CacheEntry(
                value=copy.deepcopy(detail),
                expires_at=now + ttl_seconds,
            )

    return details


async def get_or_fetch_cache(
    *,
    cache_key: str,
    exchange: str,
    ttl_seconds: float,
    fetcher: Callable[[], Awaitable],
):
    cached_value = await get_cached_value(cache_key)

    if cached_value is not None:
        logger.info("P2P cache hit: key=%s", cache_key)
        return cached_value

    lock = await get_cache_lock(cache_key)

    async with lock:
        cached_value = await get_cached_value(cache_key)

        if cached_value is not None:
            logger.info("P2P cache hit after lock: key=%s", cache_key)
            return cached_value

        logger.info(
            "P2P cache miss: key=%s ttl=%ss",
            cache_key,
            ttl_seconds,
        )
        await wait_for_global_cooldown(exchange)
        value = await fetcher()
        await set_cached_value(cache_key, value, ttl_seconds)

        return copy.deepcopy(value)


async def get_cached_value(cache_key: str):
    now = time.monotonic()

    async with _guard_lock:
        cached = _cache.get(cache_key)

        if not cached:
            return None

        if cached.expires_at <= now:
            _cache.pop(cache_key, None)
            return None

        return copy.deepcopy(cached.value)


async def set_cached_value(cache_key: str, value, ttl_seconds: float):
    if ttl_seconds <= 0:
        return

    async with _guard_lock:
        _cache[cache_key] = CacheEntry(
            value=copy.deepcopy(value),
            expires_at=time.monotonic() + ttl_seconds,
        )

    logger.info("P2P cache stored: key=%s ttl=%ss", cache_key, ttl_seconds)


async def get_cache_lock(cache_key: str) -> asyncio.Lock:
    async with _guard_lock:
        lock = _cache_locks.get(cache_key)

        if not lock:
            lock = asyncio.Lock()
            _cache_locks[cache_key] = lock

        return lock


async def wait_for_global_cooldown(exchange: str):
    cooldown = get_global_cooldown_seconds()

    if cooldown <= 0:
        return

    while True:
        async with _guard_lock:
            now = time.monotonic()
            last_request_at = _global_last_requests.get(exchange, 0.0)
            wait_seconds = cooldown - (now - last_request_at)

            if wait_seconds <= 0:
                _global_last_requests[exchange] = now
                return

        await asyncio.sleep(min(wait_seconds, cooldown))


def normalize_unique_ids(item_ids: list[object]) -> list[str]:
    unique_item_ids = []
    seen = set()

    for item_id in item_ids:
        if not item_id:
            continue

        item_id = str(item_id)

        if item_id in seen:
            continue

        unique_item_ids.append(item_id)
        seen.add(item_id)

    return unique_item_ids


def get_detail_cache_key(exchange: str, item_id: object) -> str:
    return f"p2p-detail:{exchange}:{item_id}"


def format_rate_limit_message(wait_seconds: int) -> str:
    return (
        "Трохи зачекайте перед наступним P2P-запитом.\n\n"
        f"Можна повторити приблизно через {wait_seconds} сек."
    )


def get_user_cooldown_seconds() -> float:
    return max(0.0, float(getattr(Config, "P2P_USER_COOLDOWN_SECONDS", 8)))


def get_global_cooldown_seconds() -> float:
    return max(0.0, float(getattr(Config, "P2P_GLOBAL_COOLDOWN_SECONDS", 2)))


def get_orders_cache_ttl_seconds() -> float:
    return max(0.0, float(getattr(Config, "P2P_CACHE_TTL_SECONDS", 30)))


def get_details_cache_ttl_seconds() -> float:
    return max(0.0, float(getattr(Config, "P2P_DETAILS_CACHE_TTL_SECONDS", 90)))
