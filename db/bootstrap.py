import logging

from config import Config
from db import models
from db.base import AsyncSessionLocal, Base, engine
from db.migrations import add_p2p_filter_columns
from db.migrations.add_statistics_scope_columns import add_statistics_scope_columns
from db.migrations.add_user_profile_columns import add_user_profile_columns
from db.seeders.reference_data import seed_reference_data
from services.payment_method_service import PaymentMethodService


logger = logging.getLogger(__name__)


async def bootstrap_database():
    if not Config.DB_AUTO_CREATE_TABLES:
        logger.debug("Database bootstrap skipped: DB_AUTO_CREATE_TABLES=false")
        return

    logger.debug("Database bootstrap start")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await add_p2p_filter_columns()
    await add_statistics_scope_columns()
    await add_user_profile_columns()

    if Config.DB_AUTO_SEED_REFERENCE_DATA:
        await seed_reference_data()

    async with AsyncSessionLocal() as session:
        await PaymentMethodService(session).sync_filter_keywords()

    logger.debug("Database bootstrap done")
