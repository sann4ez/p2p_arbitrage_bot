from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from db.base import AsyncSessionLocal
from fsm.states import AppMenu, P2PExchange
from keyboards.menu import (
    BTN_BACK,
    BTN_BINANCE,
    BTN_OKX,
    CB_P2P_PAIR_SELECT_BACK_PREFIX,
    CB_P2P_PAIR_SELECT_CRYPTO_PREFIX,
    CB_P2P_PAIR_SELECT_PREFIX,
    BTN_UAH_TO_USDT,
    BTN_USDT_TO_UAH,
    exchanges_kb,
    p2p_directions_kb,
    p2p_pair_select_cryptos_inline_kb,
    p2p_pair_select_fiats_inline_kb,
)
from services.p2p_pair_service import P2PPairService

router = Router()

EXCHANGE_STATES = {
    "binance": P2PExchange.binance,
    "okx": P2PExchange.okx,
}
EXCHANGE_LABELS = {
    "binance": "Binance",
    "okx": "OKX",
}


@router.message(F.text == BTN_BINANCE)
async def binance_menu(message: types.Message, state: FSMContext):
    await show_exchange_pair_selector(message, state, "binance")


@router.message(F.text == BTN_OKX)
async def okx_menu(message: types.Message, state: FSMContext):
    await show_exchange_pair_selector(message, state, "okx")


@router.callback_query(F.data.startswith(CB_P2P_PAIR_SELECT_PREFIX))
async def select_exchange_pair(callback: types.CallbackQuery, state: FSMContext):
    exchange, crypto_currency_id, fiat_currency_id = parse_pair_select_callback(
        callback.data or ""
    )

    if not exchange or not crypto_currency_id or not fiat_currency_id:
        await callback.answer("Не вдалося прочитати пару", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        service = P2PPairService(session)
        selected_pairs = await service.list_selected_pairs(callback.from_user.id)

    pair = find_pair(selected_pairs, crypto_currency_id, fiat_currency_id)

    if not pair:
        await callback.answer("Ця пара не обрана або вже недоступна", show_alert=True)
        return

    await set_current_pair(state, exchange, pair)
    await callback.answer(pair.label)

    if callback.message:
        await callback.message.edit_text(
            f"{EXCHANGE_LABELS[exchange]} P2P\n\nПара: <b>{pair.label}</b>"
        )
        await callback.message.answer(
            "Оберіть напрямок:",
            reply_markup=p2p_directions_kb(),
        )


@router.callback_query(F.data.startswith(CB_P2P_PAIR_SELECT_CRYPTO_PREFIX))
async def select_exchange_pair_crypto(callback: types.CallbackQuery):
    exchange, crypto_currency_id = parse_pair_select_crypto_callback(callback.data or "")

    if not exchange or not crypto_currency_id:
        await callback.answer("Не вдалося прочитати стейбл", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        service = P2PPairService(session)
        selected_pairs = await service.list_selected_pairs(callback.from_user.id)

    crypto_pairs = filter_pairs_by_crypto(selected_pairs, crypto_currency_id)

    if not crypto_pairs:
        await callback.answer("Для цього стейбла немає обраних фіатів", show_alert=True)
        return

    await callback.answer(crypto_pairs[0].crypto_code)

    if callback.message:
        await callback.message.edit_text(
            f"{EXCHANGE_LABELS[exchange]} P2P\n\n"
            f"Стейбл: <b>{crypto_pairs[0].crypto_code}</b>\n\n"
            "Оберіть фіат:",
            reply_markup=p2p_pair_select_fiats_inline_kb(
                selected_pairs,
                exchange,
                crypto_currency_id,
            ),
        )


@router.callback_query(F.data.startswith(CB_P2P_PAIR_SELECT_BACK_PREFIX))
async def back_to_exchange_pair_cryptos(callback: types.CallbackQuery):
    exchange = parse_pair_select_back_callback(callback.data or "")

    if not exchange:
        await callback.answer("Не вдалося прочитати біржу", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        service = P2PPairService(session)
        selected_pairs = await service.list_selected_pairs(callback.from_user.id)

    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            f"{EXCHANGE_LABELS[exchange]} P2P\n\n"
            "Оберіть стейбл для цього запиту:",
            reply_markup=p2p_pair_select_cryptos_inline_kb(selected_pairs, exchange),
        )


async def show_exchange_pair_selector(
    message: types.Message,
    state: FSMContext,
    exchange: str,
):
    await state.set_state(EXCHANGE_STATES[exchange])
    await clear_current_pair(state, exchange)

    async with AsyncSessionLocal() as session:
        service = P2PPairService(session)
        selected_pairs = await service.list_selected_pairs(message.from_user.id)

    exchange_label = EXCHANGE_LABELS[exchange]

    if not selected_pairs:
        await message.answer(
            "Немає обраних P2P пар. Відкрийте Особистий кабінет -> Мої P2P пари."
        )
        return

    if len(selected_pairs) == 1:
        pair = selected_pairs[0]
        await set_current_pair(state, exchange, pair)

        await message.answer(
            f"{exchange_label} P2P\n\n"
            f"Пара: <b>{pair.label}</b>\n\n"
            "Оберіть напрямок:",
            reply_markup=p2p_directions_kb(),
        )
        return

    await message.answer(
        f"{exchange_label} P2P\n\n"
        "Оберіть стейбл для цього запиту:",
        reply_markup=p2p_pair_select_cryptos_inline_kb(selected_pairs, exchange),
    )


@router.message(StateFilter(P2PExchange.binance, P2PExchange.okx), F.text == BTN_BACK)
async def back_to_exchanges(message: types.Message, state: FSMContext):
    await state.set_state(AppMenu.p2p_exchanges)
    await clear_current_pair(state)

    await message.answer(
        "Оберіть біржу:",
        reply_markup=exchanges_kb(),
    )


@router.message(StateFilter(None), F.text.in_({BTN_UAH_TO_USDT, BTN_USDT_TO_UAH}))
async def choose_exchange_first(message: types.Message, state: FSMContext):
    await state.set_state(AppMenu.p2p_exchanges)

    await message.answer(
        "Спочатку оберіть біржу:",
        reply_markup=exchanges_kb(),
    )


async def set_current_pair(state: FSMContext, exchange: str, pair):
    await state.set_state(EXCHANGE_STATES[exchange])
    await state.update_data(
        p2p_exchange=exchange,
        p2p_pair_crypto_currency_id=pair.crypto_currency_id,
        p2p_pair_fiat_currency_id=pair.fiat_currency_id,
        p2p_pair_crypto_code=pair.crypto_code,
        p2p_pair_fiat_code=pair.fiat_code,
    )


async def clear_current_pair(state: FSMContext, exchange: str | None = None):
    await state.update_data(
        p2p_exchange=exchange,
        p2p_pair_crypto_currency_id=None,
        p2p_pair_fiat_currency_id=None,
        p2p_pair_crypto_code=None,
        p2p_pair_fiat_code=None,
    )


def parse_pair_select_callback(
    callback_data: str,
) -> tuple[str | None, int | None, int | None]:
    payload = callback_data[len(CB_P2P_PAIR_SELECT_PREFIX):]
    parts = payload.split(":")

    if len(parts) != 3:
        return None, None, None

    exchange = parts[0]

    if exchange not in EXCHANGE_STATES:
        return None, None, None

    try:
        return exchange, int(parts[1]), int(parts[2])
    except ValueError:
        return None, None, None


def parse_pair_select_crypto_callback(
    callback_data: str,
) -> tuple[str | None, int | None]:
    payload = callback_data[len(CB_P2P_PAIR_SELECT_CRYPTO_PREFIX):]
    parts = payload.split(":")

    if len(parts) != 2:
        return None, None

    exchange = parts[0]

    if exchange not in EXCHANGE_STATES:
        return None, None

    try:
        return exchange, int(parts[1])
    except ValueError:
        return None, None


def parse_pair_select_back_callback(callback_data: str) -> str | None:
    exchange = callback_data[len(CB_P2P_PAIR_SELECT_BACK_PREFIX):]

    if exchange not in EXCHANGE_STATES:
        return None

    return exchange


def find_pair(pairs, crypto_currency_id: int, fiat_currency_id: int):
    return next(
        (
            pair
            for pair in pairs
            if pair.crypto_currency_id == crypto_currency_id
            and pair.fiat_currency_id == fiat_currency_id
        ),
        None,
    )


def filter_pairs_by_crypto(pairs, crypto_currency_id: int):
    return [
        pair
        for pair in pairs
        if pair.crypto_currency_id == crypto_currency_id
    ]
