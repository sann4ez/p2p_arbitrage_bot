from sqlalchemy import text

from db.base import engine


async def add_recommendation_columns():
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                ALTER TABLE user_settings
                ADD COLUMN IF NOT EXISTS is_recommendations_enabled
                BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
        )
