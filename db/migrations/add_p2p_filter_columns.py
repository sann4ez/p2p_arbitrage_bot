from sqlalchemy import text

from db.base import engine


async def add_p2p_filter_columns():
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                ALTER TABLE user_settings
                ADD COLUMN IF NOT EXISTS allow_third_party_payments BOOLEAN NOT NULL DEFAULT TRUE
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE user_settings
                ADD COLUMN IF NOT EXISTS allow_split_payments BOOLEAN NOT NULL DEFAULT TRUE
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE user_settings
                ADD COLUMN IF NOT EXISTS display_order_count INTEGER NOT NULL DEFAULT 5
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE user_settings
                ADD COLUMN IF NOT EXISTS candidate_order_count INTEGER NOT NULL DEFAULT 20
                """
            )
        )
        await conn.execute(
            text(
                """
                UPDATE user_settings
                SET candidate_order_count = 20
                WHERE candidate_order_count IS NULL
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE user_settings
                ADD COLUMN IF NOT EXISTS description_check_mode VARCHAR(20) NOT NULL DEFAULT 'regex'
                """
            )
        )
