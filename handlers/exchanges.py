from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from fsm.states import P2PExchange
from keyboards.menu import (
    BTN_BACK_EXCHANGES,
    BTN_BINANCE,
    BTN_OKX,
    BTN_UAH_TO_USDT,
    BTN_USDT_TO_UAH,
    exchanges_kb,
    main_menu_kb,
)

router = Router()


@router.message(F.text == BTN_BINANCE)
async def binance_menu(message: types.Message, state: FSMContext):
    await state.set_state(P2PExchange.binance)

    await message.answer(
        "Binance P2P\n\nОберіть напрямок:",
        reply_markup=main_menu_kb(),
    )


@router.message(F.text == BTN_OKX)
async def okx_menu(message: types.Message, state: FSMContext):
    await state.set_state(P2PExchange.okx)

    await message.answer(
        "OKX P2P\n\nОберіть напрямок:",
        reply_markup=main_menu_kb(),
    )


@router.message(F.text == BTN_BACK_EXCHANGES)
async def back_to_exchanges(message: types.Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Оберіть біржу:",
        reply_markup=exchanges_kb(),
    )


@router.message(StateFilter(None), F.text.in_({BTN_UAH_TO_USDT, BTN_USDT_TO_UAH}))
async def choose_exchange_first(message: types.Message):
    await message.answer(
        "Спочатку оберіть біржу:",
        reply_markup=exchanges_kb(),
    )
