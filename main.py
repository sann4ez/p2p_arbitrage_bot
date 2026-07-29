import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import Config
from db.base import engine
from db.bootstrap import bootstrap_database
from handlers import register_routes
from services.admin_notifier import configure_admin_notifier
from tasks.recommendation_monitor import run_p2p_market_monitor
from tasks.statistics_scanner import cancel_scheduled_global_statistics_scan

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.WARNING),
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
)


async def main():
    await bootstrap_database()

    bot = Bot(
        token=Config.TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    configure_admin_notifier(bot)
    dp = Dispatcher()

    register_routes(dp)

    background_tasks = [
        asyncio.create_task(run_p2p_market_monitor(bot)),
    ]

    try:
        await dp.start_polling(bot)
    finally:
        for task in background_tasks:
            task.cancel()

        await asyncio.gather(*background_tasks, return_exceptions=True)
        await cancel_scheduled_global_statistics_scan()
        await engine.dispose()


if __name__ == "__main__":
    try:
        print("Бот запущено")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот зупинено")
