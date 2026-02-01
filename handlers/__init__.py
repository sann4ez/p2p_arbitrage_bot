from aiogram import Dispatcher

from handlers.start import router as start_router
from handlers.binance_p2p import router as binance_router

def register_routes(dp: Dispatcher):
    dp.include_router(start_router)
    dp.include_router(binance_router)