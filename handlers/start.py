from aiogram import Router, types
from aiogram.filters import CommandStart

from keyboards.menu import main_menu_kb

router = Router()

@router.message(CommandStart())
async def start_bot(message: types.Message):
    await message.answer(
        f"Привіт, {message.from_user.full_name}!"
        + "\nЦе бот по P2P Арбітражу"
        + "\nВиберіть необхідний пункт меню:",
        reply_markup=main_menu_kb()
    )