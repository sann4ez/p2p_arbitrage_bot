import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from config import Config
from db.base import AsyncSessionLocal
from db.models import P2POrderDetailCache
from services.time_utils import utc_now_naive as utc_now


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PersistedDetailBatch:
    fresh: dict[str, dict]
    stale: dict[str, dict]


async def cleanup_persisted_p2p_details(
    retention_days: int,
    *,
    batch_size: int = 1000,
) -> int:
    if retention_days <= 0 or batch_size <= 0:
        return 0

    cutoff = utc_now() - timedelta(days=retention_days)
    expired_ids = (
        select(P2POrderDetailCache.id)
        .where(P2POrderDetailCache.last_seen_at < cutoff)
        .order_by(P2POrderDetailCache.last_seen_at)
        .limit(batch_size)
    )

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                delete(P2POrderDetailCache).where(
                    P2POrderDetailCache.id.in_(expired_ids)
                )
            )
            await session.commit()
            return max(0, int(result.rowcount or 0))
    except Exception as error:
        logger.warning(
            "Persistent P2P detail cache cleanup failed: error=%s",
            type(error).__name__,
        )
        return 0


async def load_persisted_p2p_details(
    exchange: str,
    item_ids: list[str],
) -> PersistedDetailBatch:
    if not item_ids or get_persistent_detail_ttl_seconds() <= 0:
        return PersistedDetailBatch(fresh={}, stale={})

    now = utc_now()

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(P2POrderDetailCache).where(
                    P2POrderDetailCache.exchange_code == exchange.upper(),
                    P2POrderDetailCache.exchange_offer_id.in_(item_ids),
                )
            )
            rows = list(result.scalars().all())
    except Exception as error:
        logger.warning(
            "Persistent P2P detail cache read failed: exchange=%s error=%s",
            exchange,
            type(error).__name__,
        )
        return PersistedDetailBatch(fresh={}, stale={})

    fresh = {}
    stale = {}

    for row in rows:
        target = fresh if row.next_refresh_at > now else stale
        target[row.exchange_offer_id] = row.detail_payload

    return PersistedDetailBatch(fresh=fresh, stale=stale)


async def store_persisted_p2p_details(
    exchange: str,
    details: dict[str, dict],
):
    ttl_seconds = get_persistent_detail_ttl_seconds()
    prepared = {
        str(item_id): detail
        for item_id, detail in details.items()
        if item_id and isinstance(detail, dict) and detail
    }

    if not prepared or ttl_seconds <= 0:
        return

    now = utc_now()
    next_refresh_at = now + timedelta(seconds=ttl_seconds)
    values = [
        {
            "exchange_code": exchange.upper(),
            "exchange_offer_id": item_id,
            "detail_payload": detail,
            "detail_hash": hash_detail(detail),
            "fetched_at": now,
            "next_refresh_at": next_refresh_at,
            "last_seen_at": now,
            "created_at": now,
            "updated_at": now,
        }
        for item_id, detail in prepared.items()
    ]
    statement = insert(P2POrderDetailCache).values(values)
    statement = statement.on_conflict_do_update(
        constraint="uq_p2p_order_detail_exchange_offer",
        set_={
            "detail_payload": statement.excluded.detail_payload,
            "detail_hash": statement.excluded.detail_hash,
            "fetched_at": statement.excluded.fetched_at,
            "next_refresh_at": statement.excluded.next_refresh_at,
            "last_seen_at": statement.excluded.last_seen_at,
            "updated_at": statement.excluded.updated_at,
        },
    )

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(statement)
            await session.commit()
    except Exception as error:
        logger.warning(
            "Persistent P2P detail cache write failed: exchange=%s items=%s error=%s",
            exchange,
            len(prepared),
            type(error).__name__,
        )


async def defer_persisted_p2p_detail_refresh(
    exchange: str,
    item_ids: list[str],
):
    item_ids = sorted({str(item_id) for item_id in item_ids if item_id})
    retry_seconds = get_detail_failure_retry_seconds()

    if not item_ids or retry_seconds <= 0:
        return

    now = utc_now()
    retry_at = now + timedelta(seconds=retry_seconds)
    empty_payload = {}
    values = [
        {
            "exchange_code": exchange.upper(),
            "exchange_offer_id": item_id,
            "detail_payload": empty_payload,
            "detail_hash": hash_detail(empty_payload),
            "fetched_at": now,
            "next_refresh_at": retry_at,
            "last_seen_at": now,
            "created_at": now,
            "updated_at": now,
        }
        for item_id in item_ids
    ]
    statement = insert(P2POrderDetailCache).values(values)
    statement = statement.on_conflict_do_update(
        constraint="uq_p2p_order_detail_exchange_offer",
        set_={
            "next_refresh_at": statement.excluded.next_refresh_at,
            "last_seen_at": statement.excluded.last_seen_at,
            "updated_at": statement.excluded.updated_at,
        },
    )

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(statement)
            await session.commit()
    except Exception as error:
        logger.warning(
            "Persistent P2P detail retry deferral failed: exchange=%s items=%s error=%s",
            exchange,
            len(item_ids),
            type(error).__name__,
        )


def hash_detail(detail: dict) -> str:
    serialized = json.dumps(
        detail,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_persistent_detail_ttl_seconds() -> int:
    try:
        return max(
            0,
            int(getattr(Config, "P2P_DETAIL_PERSISTENT_TTL_SECONDS", 864000)),
        )
    except (TypeError, ValueError):
        return 864000


def get_detail_failure_retry_seconds() -> int:
    try:
        return max(
            0,
            int(
                getattr(
                    Config,
                    "P2P_DETAIL_REFRESH_FAILURE_RETRY_SECONDS",
                    3600,
                )
            ),
        )
    except (TypeError, ValueError):
        return 3600
