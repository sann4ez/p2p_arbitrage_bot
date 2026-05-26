from sqlalchemy.ext.asyncio import AsyncSession

from db.base import AsyncSessionLocal


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session