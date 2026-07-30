from sqlalchemy import text

from db.base import engine


async def add_statistics_order_amount_columns():
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                ALTER TABLE statistics_global_settings
                ADD COLUMN IF NOT EXISTS min_order_amount NUMERIC(14, 2)
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE statistics_global_settings
                ADD COLUMN IF NOT EXISTS max_order_amount NUMERIC(14, 2)
                """
            )
        )
