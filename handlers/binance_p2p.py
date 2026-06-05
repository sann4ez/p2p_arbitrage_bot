from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from fsm.states import P2PExchange
from keyboards.menu import BTN_UAH_TO_USDT, BTN_USDT_TO_UAH
from services.p2p_exchange_drivers import (
    P2P_DIRECTION_CRYPTO_TO_FIAT,
    P2P_DIRECTION_FIAT_TO_CRYPTO,
    get_p2p_exchange_driver,
)
from services.p2p_telegram_flow import (
    ask_to_choose_pair,
    get_current_pair_from_state,
    send_p2p_ads,
)


router = Router()
BINANCE_DRIVER = get_p2p_exchange_driver("binance")


@router.message(StateFilter(P2PExchange.binance), F.text == BTN_UAH_TO_USDT)
async def uah_to_usdt(message: types.Message, state: FSMContext):
    await send_binance_direction(
        message,
        state,
        direction=P2P_DIRECTION_FIAT_TO_CRYPTO,
    )


@router.message(StateFilter(P2PExchange.binance), F.text == BTN_USDT_TO_UAH)
async def usdt_to_uah(message: types.Message, state: FSMContext):
    await send_binance_direction(
        message,
        state,
        direction=P2P_DIRECTION_CRYPTO_TO_FIAT,
    )


async def send_binance_direction(
    message: types.Message,
    state: FSMContext,
    *,
    direction: str,
):
    pair = await get_current_pair_from_state(state)

    if not pair:
        await ask_to_choose_pair(message)
        return

    await send_p2p_ads(
        message=message,
        pair=pair,
        driver=BINANCE_DRIVER,
        side=BINANCE_DRIVER.side_for_direction(direction),
        title=BINANCE_DRIVER.title_for_direction(direction, pair),
    )
