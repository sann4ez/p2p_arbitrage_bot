from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from config import Config


class Base(DeclarativeBase):
    pass

print(Config.DB_URL)

engine = create_async_engine(
    Config.DB_URL,
    echo=False,        # True — для дебагу SQL
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)