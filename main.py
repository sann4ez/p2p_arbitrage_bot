import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from config import Config

from handlers import register_routes

async def main():
    bot = Bot(token=Config.TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    register_routes(dp)

    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        print('Бот запущено')
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Бот зупинено')