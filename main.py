import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from config import Config

from db.bootstrap import bootstrap_database
from handlers import register_routes
from services.admin_notifier import configure_admin_notifier
from tasks.statistics_scanner import run_global_statistics_scheduler

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.WARNING),
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
)

async def main():
    await bootstrap_database()

    bot = Bot(token=Config.TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    configure_admin_notifier(bot)
    dp = Dispatcher()

    register_routes(dp)

    statistics_task = asyncio.create_task(run_global_statistics_scheduler())

    try:
        await dp.start_polling(bot)
    finally:
        statistics_task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await statistics_task

if __name__ == "__main__":
    try:
        print('Бот запущено')
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Бот зупинено')
