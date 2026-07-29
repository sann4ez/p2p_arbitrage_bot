from sqlalchemy import text

from db.base import engine


async def add_performance_indexes():
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_scan_batches_started_at
                ON scan_batches (started_at)
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_scan_batches_scope_status_started
                ON scan_batches (scope, status, started_at)
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_p2p_order_detail_cache_last_seen_at
                ON p2p_order_detail_cache (last_seen_at)
                """
            )
        )
