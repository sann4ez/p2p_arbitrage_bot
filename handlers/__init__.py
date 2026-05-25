from aiogram import Dispatcher

from handlers.start import router as start_router
from handlers.main_menu import router as main_menu_router
from handlers.exchanges import router as exchanges_router
from handlers.binance_p2p import router as binance_router
from handlers.okx_p2p import router as okx_router

def register_routes(dp: Dispatcher):
    dp.include_router(start_router)
    dp.include_router(main_menu_router)
    dp.include_router(exchanges_router)
    dp.include_router(binance_router)
    dp.include_router(okx_router)
