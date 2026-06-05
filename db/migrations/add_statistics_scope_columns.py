from sqlalchemy import text

from db.base import engine


async def add_statistics_scope_columns():
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                ALTER TABLE scan_batches
                ADD COLUMN IF NOT EXISTS user_id INTEGER NULL
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE scan_batches
                ADD COLUMN IF NOT EXISTS scope VARCHAR(20) NOT NULL DEFAULT 'legacy'
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE scan_batches
                ADD COLUMN IF NOT EXISTS filter_hash VARCHAR(64) NOT NULL DEFAULT 'legacy'
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE p2p_price_statistics
                ADD COLUMN IF NOT EXISTS scope VARCHAR(20) NOT NULL DEFAULT 'legacy'
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE p2p_price_statistics
                ADD COLUMN IF NOT EXISTS filter_hash VARCHAR(64) NOT NULL DEFAULT 'legacy'
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE p2p_price_statistics
                DROP CONSTRAINT IF EXISTS uq_p2p_price_stat_period
                """
            )
        )
        await conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'uq_p2p_price_stat_scope_period'
                    ) THEN
                        ALTER TABLE p2p_price_statistics
                        ADD CONSTRAINT uq_p2p_price_stat_scope_period UNIQUE (
                            scope,
                            filter_hash,
                            exchange_id,
                            crypto_currency_id,
                            fiat_currency_id,
                            side,
                            period_type,
                            period_started_at
                        );
                    END IF;
                END $$;
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_scan_batches_scope_hash
                ON scan_batches (scope, filter_hash, started_at)
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_p2p_price_stats_scope_lookup
                ON p2p_price_statistics (
                    scope,
                    filter_hash,
                    period_type,
                    period_started_at
                )
                """
            )
        )
