import logging

from config import Config
from db import models
from db.base import Base, engine
from db.migrations import add_p2p_filter_columns
from db.seeders.reference_data import seed_reference_data


logger = logging.getLogger(__name__)


async def bootstrap_database():
    if not Config.DB_AUTO_CREATE_TABLES:
        logger.info("Database bootstrap skipped: DB_AUTO_CREATE_TABLES=false")
        return

    logger.info("Database bootstrap start")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await add_p2p_filter_columns()

    if Config.DB_AUTO_SEED_REFERENCE_DATA:
        await seed_reference_data()

    logger.info("Database bootstrap done")
