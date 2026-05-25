import logging

from aiogram import F, Router, types
from aiogram.filters import StateFilter

from db.base import AsyncSessionLocal
from fsm.states import P2PExchange
from keyboards.menu import BTN_UAH_TO_USDT, BTN_USDT_TO_UAH
from services.okx_client import fetch_okx_p2p
from services.p2p_filters import (
    filter_orders,
    filters_summary,
    get_fetch_order_count,
    get_filters,
)
from services.p2p_description_filter import filter_orders_by_description
from services.p2p_order_formatter import build_okx_order_blocks, count_okx_descriptions
from services.telegram_messages import send_html_blocks

router = Router()
logger = logging.getLogger(__name__)


@router.message(StateFilter(P2PExchange.okx), F.text == BTN_UAH_TO_USDT)
async def uah_to_usdt(message: types.Message):
    await send_okx_ads(
        message=message,
        side="sell",
        title="OKX P2P | Купівля USDT за UAH",
    )


@router.message(StateFilter(P2PExchange.okx), F.text == BTN_USDT_TO_UAH)
async def usdt_to_uah(message: types.Message):
    await send_okx_ads(
        message=message,
        side="buy",
        title="OKX P2P | Продаж USDT за UAH",
    )


async def send_okx_ads(
    *,
    message: types.Message,
    side: str,
    title: str,
):
    async with AsyncSessionLocal() as session:
        settings = await get_filters(session, message.from_user.id)

    fetch_rows = get_fetch_order_count(settings)
    logger.info(
        "P2P OKX flow start: telegram_id=%s side=%s fetch_rows=%s display_count=%s desc_mode=%s allow_split=%s allow_third_party=%s",
        message.from_user.id,
        side,
        fetch_rows,
        settings.display_order_count,
        settings.description_check_mode,
        settings.allow_split_payments,
        settings.allow_third_party_payments,
    )

    ads = await fetch_okx_p2p(
        side=side,
        asset="USDT",
        fiat="UAH",
        rows=fetch_rows,
    )
    logger.info("P2P OKX fetched: side=%s rows=%s", side, len(ads))

    if not ads:
        logger.warning("P2P OKX stopped: reason=no_orders side=%s", side)
        await message.answer("OKX зараз не повернув ордери. Спробуйте ще раз трохи пізніше.")
        return

    filtered_ads = filter_orders(
        ads,
        "okx",
        settings,
        apply_description_filters=False,
    )
    logger.info(
        "P2P OKX base filters result: input=%s output=%s blocked=%s",
        len(ads),
        len(filtered_ads),
        len(ads) - len(filtered_ads),
    )

    if not filtered_ads:
        logger.info("P2P OKX stopped: reason=all_blocked_by_base_filters")
        await message.answer(
            f"OKX повернув {len(ads)} ордерів, але всі вони відсіялись фільтрами.\n\n"
            f"{filters_summary(settings)}"
        )
        return

    logger.info(
        "P2P OKX descriptions before description filters: candidates=%s descriptions=%s",
        len(filtered_ads),
        count_okx_descriptions(filtered_ads),
    )
    filtered_ads = await filter_orders_by_description(filtered_ads, "okx", settings)
    logger.info("P2P OKX description filters result: output=%s", len(filtered_ads))

    if not filtered_ads:
        logger.info("P2P OKX stopped: reason=all_blocked_by_description_filters")
        await message.answer(
            f"OKX повернув {len(ads)} ордерів, але всі вони відсіялись фільтрами.\n\n"
            f"{filters_summary(settings)}"
        )
        return

    ads = filtered_ads[: settings.display_order_count]
    logger.info(
        "P2P OKX output selected: requested=%s selected=%s descriptions=%s",
        settings.display_order_count,
        len(ads),
        count_okx_descriptions(ads),
    )
    blocks = build_okx_order_blocks(ads, side)

    logger.info("P2P OKX sending messages: blocks=%s", len(blocks))
    await send_html_blocks(message, title=title, blocks=blocks)
