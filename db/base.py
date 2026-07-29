from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from config import Config


class Base(DeclarativeBase):
    pass

engine = create_async_engine(
    Config.DB_URL,
    echo=False,
    pool_size=Config.DB_POOL_SIZE,
    max_overflow=Config.DB_MAX_OVERFLOW,
    pool_timeout=Config.DB_POOL_TIMEOUT_SECONDS,
    pool_recycle=Config.DB_POOL_RECYCLE_SECONDS,
    pool_use_lifo=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)
