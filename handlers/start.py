from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from db.base import AsyncSessionLocal
from keyboards.menu import root_menu_kb
from services.user_service import UserService

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    async with AsyncSessionLocal() as session:

        service = UserService(session)

        await service.register_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username
        )

    await message.answer(
        "Бот активовано ✅\n\nОберіть розділ:",
        reply_markup=root_menu_kb(),
    )
