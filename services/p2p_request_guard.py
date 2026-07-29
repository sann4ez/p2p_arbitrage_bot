import asyncio
import copy
import logging
import math
import time
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass

from config import Config
from services.p2p_detail_cache import (
    defer_persisted_p2p_detail_refresh,
    load_persisted_p2p_details,
    store_persisted_p2p_details,
)

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    allowed: bool
    wait_seconds: int = 0


@dataclass
class CacheEntry:
    value: object
    expires_at: float


@dataclass
class CacheLockEntry:
    lock: asyncio.Lock
    last_used_at: float


_user_last_requests: dict[int, float] = {}
_global_last_requests: dict[str, float] = {}
_cache: dict[str, CacheEntry] = {}
_cache_locks: dict[str, CacheLockEntry] = {}
_guard_lock = asyncio.Lock()
_last_cache_cleanup_at = 0.0


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
    pair_key: str | None = None,
    fetcher: Callable[[], Awaitable[list[dict]]],
    on_fresh: Callable[[list[dict]], Awaitable[None]] | None = None,
    force_refresh: bool = False,
) -> list[dict]:
    pair_part = pair_key or "default"
    cache_key = f"p2p-orders:{exchange}:{direction}:{pair_part}:{rows}"

    orders = await get_or_fetch_cache(
        cache_key=cache_key,
        exchange=exchange,
        ttl_seconds=get_orders_cache_ttl_seconds(),
        fetcher=fetcher,
        on_fresh=on_fresh,
        force_refresh=force_refresh,
    )

    logger.debug(
        "P2P orders cache result: exchange=%s direction=%s pair=%s requested=%s returned=%s",
        exchange,
        direction,
        pair_part,
        rows,
        len(orders) if isinstance(orders, list) else "unknown",
    )

    return orders


async def get_cached_p2p_details(
    *,
    exchange: str,
    item_ids: list[object],
    fetcher: Callable[[list[object]], Awaitable[dict[str, dict]]],
) -> dict[str, dict]:
    unique_item_ids = normalize_unique_ids(item_ids)

    if not unique_item_ids:
        return {}

    ttl_seconds = get_details_cache_ttl_seconds()
    details, missing_item_ids = await load_memory_cached_details(
        exchange,
        unique_item_ids,
    )

    async with AsyncExitStack() as lock_stack:
        for item_id in sorted(missing_item_ids):
            lock = await get_cache_lock(get_detail_cache_key(exchange, item_id))
            await lock_stack.enter_async_context(lock)

        # Another overlapping request may have populated the cache while these
        # per-order locks were being acquired.
        locked_cached, missing_item_ids = await load_memory_cached_details(
            exchange,
            missing_item_ids,
        )
        details.update(locked_cached)

        if not missing_item_ids:
            return details

        persisted = await load_persisted_p2p_details(exchange, missing_item_ids)
        details.update(copy.deepcopy(persisted.fresh))
        await store_memory_cached_details(
            exchange,
            persisted.fresh,
            ttl_seconds,
        )
        missing_item_ids = [
            item_id
            for item_id in missing_item_ids
            if item_id not in persisted.fresh
        ]

        if not missing_item_ids:
            return details

        await wait_for_global_cooldown(exchange)
        fetched = await fetcher(missing_item_ids) or {}
        fresh_details = {
            str(item_id): detail
            for item_id, detail in fetched.items()
            if item_id and isinstance(detail, dict) and detail
        }
        await store_persisted_p2p_details(exchange, fresh_details)
        fetched_ids = set(fresh_details)
        not_fetched_ids = [
            item_id
            for item_id in missing_item_ids
            if item_id not in fetched_ids
        ]
        await defer_persisted_p2p_detail_refresh(
            exchange,
            not_fetched_ids,
        )

        resolved_details = {
            item_id: (
                fresh_details.get(item_id)
                or persisted.stale.get(item_id)
                or {}
            )
            for item_id in missing_item_ids
        }
        details.update(copy.deepcopy(resolved_details))
        await store_memory_cached_details(
            exchange,
            resolved_details,
            ttl_seconds,
        )

    return details


async def load_memory_cached_details(
    exchange: str,
    item_ids: list[str],
) -> tuple[dict[str, dict], list[str]]:
    now = time.monotonic()
    details = {}
    missing_item_ids = []

    async with _guard_lock:
        for item_id in item_ids:
            cached = _cache.get(get_detail_cache_key(exchange, item_id))

            if cached and cached.expires_at > now:
                details[item_id] = copy.deepcopy(cached.value)
            else:
                missing_item_ids.append(item_id)

    return details, missing_item_ids


async def store_memory_cached_details(
    exchange: str,
    details: dict[str, dict],
    ttl_seconds: float,
):
    if not details or ttl_seconds <= 0:
        return

    expires_at = time.monotonic() + ttl_seconds

    async with _guard_lock:
        for item_id, detail in details.items():
            _cache[get_detail_cache_key(exchange, item_id)] = CacheEntry(
                value=copy.deepcopy(detail),
                expires_at=expires_at,
            )
        prune_cache_size_locked()


async def get_or_fetch_cache(
    *,
    cache_key: str,
    exchange: str,
    ttl_seconds: float,
    fetcher: Callable[[], Awaitable],
    cache_empty: bool = True,
    store_value: bool = True,
    on_fresh: Callable[[object], Awaitable[None]] | None = None,
    force_refresh: bool = False,
):
    cached_value = None
    if not force_refresh:
        cached_value = await get_cached_value(cache_key)

    if cached_value is not None:
        logger.debug("P2P cache hit: key=%s", cache_key)
        return cached_value

    lock = await get_cache_lock(cache_key)

    async with lock:
        cached_value = None
        if not force_refresh:
            cached_value = await get_cached_value(cache_key)

        if cached_value is not None:
            logger.debug("P2P cache hit after lock: key=%s", cache_key)
            return cached_value

        logger.debug(
            "P2P cache %s: key=%s ttl=%ss",
            "refresh" if force_refresh else "miss",
            cache_key,
            ttl_seconds,
        )
        await wait_for_global_cooldown(exchange)
        value = await fetcher()

        if on_fresh and value:
            await on_fresh(copy.deepcopy(value))

        if store_value and (cache_empty or value):
            await set_cached_value(cache_key, value, ttl_seconds)

        return copy.deepcopy(value)


async def get_cached_value(cache_key: str):
    now = time.monotonic()

    async with _guard_lock:
        cleanup_cache_state_locked(now)
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
        cleanup_cache_state_locked()
        prune_cache_size_locked()

    logger.debug("P2P cache stored: key=%s ttl=%ss", cache_key, ttl_seconds)


async def get_cache_lock(cache_key: str) -> asyncio.Lock:
    async with _guard_lock:
        now = time.monotonic()
        cleanup_cache_state_locked(now)
        lock_entry = _cache_locks.get(cache_key)

        if not lock_entry:
            lock_entry = CacheLockEntry(
                lock=asyncio.Lock(),
                last_used_at=now,
            )
            _cache_locks[cache_key] = lock_entry
        else:
            lock_entry.last_used_at = now

        return lock_entry.lock


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


def cleanup_cache_state_locked(now: float | None = None):
    global _last_cache_cleanup_at

    now = now or time.monotonic()
    cleanup_interval = get_cache_cleanup_interval_seconds()

    if cleanup_interval > 0 and now - _last_cache_cleanup_at < cleanup_interval:
        return

    _last_cache_cleanup_at = now
    expired_cache_keys = [
        cache_key
        for cache_key, entry in _cache.items()
        if entry.expires_at <= now
    ]

    for cache_key in expired_cache_keys:
        _cache.pop(cache_key, None)

    prune_cache_size_locked()
    cleanup_cache_locks_locked(now)
    cleanup_user_rate_limit_state_locked(now)


def prune_cache_size_locked():
    max_entries = get_cache_max_entries()

    if max_entries <= 0 or len(_cache) <= max_entries:
        return

    overflow = len(_cache) - max_entries
    keys_by_expiration = sorted(
        _cache,
        key=lambda cache_key: _cache[cache_key].expires_at,
    )

    for cache_key in keys_by_expiration[:overflow]:
        _cache.pop(cache_key, None)

    logger.debug(
        "P2P cache pruned: removed=%s remaining=%s max_entries=%s",
        overflow,
        len(_cache),
        max_entries,
    )


def cleanup_cache_locks_locked(now: float):
    lock_ttl = max(
        get_orders_cache_ttl_seconds(),
        get_details_cache_ttl_seconds(),
        300.0,
    )
    expired_lock_keys = [
        cache_key
        for cache_key, lock_entry in _cache_locks.items()
        if (
            not lock_entry.lock.locked()
            and now - lock_entry.last_used_at > lock_ttl
        )
    ]

    for cache_key in expired_lock_keys:
        _cache_locks.pop(cache_key, None)


def cleanup_user_rate_limit_state_locked(now: float):
    cooldown = max(get_user_cooldown_seconds(), 60.0)
    expired_user_ids = [
        telegram_id
        for telegram_id, last_request_at in _user_last_requests.items()
        if now - last_request_at > cooldown * 10
    ]

    for telegram_id in expired_user_ids:
        _user_last_requests.pop(telegram_id, None)


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


def get_cache_max_entries() -> int:
    try:
        return max(0, int(getattr(Config, "P2P_CACHE_MAX_ENTRIES", 1000)))
    except (TypeError, ValueError):
        return 1000


def get_cache_cleanup_interval_seconds() -> float:
    try:
        return max(
            0.0,
            float(getattr(Config, "P2P_CACHE_CLEANUP_INTERVAL_SECONDS", 60)),
        )
    except (TypeError, ValueError):
        return 60.0
