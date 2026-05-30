import logging

from aiogram import F, Router, types
from aiogram.filters import StateFilter

from db.base import AsyncSessionLocal
from fsm.states import P2PExchange
from keyboards.menu import BTN_UAH_TO_USDT, BTN_USDT_TO_UAH
from services.binance_client import fetch_binance_p2p, fetch_binance_p2p_details
from services.p2p_filters import (
    filter_orders,
    filters_summary,
    get_fetch_order_count,
    get_filters,
)
from services.p2p_description_filter import (
    filter_orders_by_description_until,
    needs_description_filtering,
)
from services.p2p_order_formatter import (
    attach_binance_details,
    build_binance_order_blocks,
    build_binance_order_urls,
    count_binance_descriptions,
)
from services.p2p_request_guard import (
    check_p2p_user_rate_limit,
    format_rate_limit_message,
    get_cached_p2p_details,
    get_cached_p2p_orders,
)
from services.telegram_messages import send_paginated_html_blocks

router = Router()
logger = logging.getLogger(__name__)


@router.message(StateFilter(P2PExchange.binance), F.text == BTN_UAH_TO_USDT)
async def uah_to_usdt(message: types.Message):
    await send_binance_ads(
        message=message,
        trade_type="BUY",
        title="Binance P2P | Купівля USDT за UAH",
    )


@router.message(StateFilter(P2PExchange.binance), F.text == BTN_USDT_TO_UAH)
async def usdt_to_uah(message: types.Message):
    await send_binance_ads(
        message=message,
        trade_type="SELL",
        title="Binance P2P | Продаж USDT за UAH",
    )


async def send_binance_ads(
    *,
    message: types.Message,
    trade_type: str,
    title: str,
):
    rate_limit = await check_p2p_user_rate_limit(message.from_user.id)

    if not rate_limit.allowed:
        await message.answer(format_rate_limit_message(rate_limit.wait_seconds))
        return

    async with AsyncSessionLocal() as session:
        settings = await get_filters(session, message.from_user.id)

    fetch_rows = get_fetch_order_count(settings)
    logger.info(
        "P2P Binance flow start: telegram_id=%s trade_type=%s fetch_rows=%s display_count=%s desc_mode=%s payment_categories=%s max_minutes=%s min_trades=%s min_rating=%s min_completion=%s allow_split=%s allow_third_party=%s allow_monobank_jar=%s",
        message.from_user.id,
        trade_type,
        fetch_rows,
        settings.display_order_count,
        settings.description_check_mode,
        sorted(settings.payment_categories),
        settings.max_order_minutes,
        settings.min_trades,
        settings.min_rating,
        settings.min_completion,
        settings.allow_split_payments,
        settings.allow_third_party_payments,
        settings.allow_monobank_jar_payments,
    )

    ads = await get_cached_p2p_orders(
        exchange="binance",
        direction=trade_type,
        rows=fetch_rows,
        fetcher=lambda: fetch_binance_p2p(
            trade_type=trade_type,
            asset="USDT",
            fiat="UAH",
            rows=fetch_rows,
        ),
    )
    logger.info(
        "P2P Binance fetched: trade_type=%s rows=%s",
        trade_type,
        len(ads),
    )

    if not ads:
        logger.warning("P2P Binance stopped: reason=no_orders trade_type=%s", trade_type)
        await message.answer("Binance зараз не повернув ордери. Спробуйте ще раз трохи пізніше.")
        return

    filtered_ads = filter_orders(
        ads,
        "binance",
        settings,
        apply_description_filters=False,
        apply_payment_filters=not needs_description_filtering(settings),
    )
    logger.info(
        "P2P Binance base filters result: input=%s output=%s blocked=%s",
        len(ads),
        len(filtered_ads),
        len(ads) - len(filtered_ads),
    )

    if not filtered_ads:
        logger.info("P2P Binance stopped: reason=all_blocked_by_base_filters")
        await message.answer(
            f"Binance повернув {len(ads)} ордерів, але всі вони відсіялись фільтрами.\n\n"
            f"{filters_summary(settings)}"
        )
        return

    if needs_description_filtering(settings):
        async def prepare_binance_description_batch(candidates: list[dict]):
            details = await get_cached_p2p_details(
                exchange="binance",
                item_ids=[ad.get("adv", {}).get("advNo") for ad in candidates],
                fetcher=fetch_binance_p2p_details,
            )
            attach_binance_details(candidates, details)
            logger.info(
                "P2P Binance detail fetch for description filters: candidates=%s details=%s descriptions=%s",
                len(candidates),
                len(details),
                count_binance_descriptions(candidates),
            )

        filtered_ads = await filter_orders_by_description_until(
            filtered_ads,
            "binance",
            settings,
            limit=settings.display_order_count,
            prepare_batch=prepare_binance_description_batch,
        )
        logger.info(
            "P2P Binance description filters result: output=%s",
            len(filtered_ads),
        )

        if not filtered_ads:
            logger.info("P2P Binance stopped: reason=all_blocked_by_description_filters")
            await message.answer(
                f"Binance повернув {len(ads)} ордерів, але всі вони відсіялись фільтрами.\n\n"
                f"{filters_summary(settings)}"
            )
            return

    ads = filtered_ads[: settings.display_order_count]
    details = await get_cached_p2p_details(
        exchange="binance",
        item_ids=[
            ad.get("adv", {}).get("advNo")
            for ad in ads
            if not isinstance(ad.get("_detail"), dict)
        ],
        fetcher=fetch_binance_p2p_details,
    )
    attach_binance_details(ads, details)
    logger.info(
        "P2P Binance output selected: requested=%s selected=%s extra_details=%s descriptions=%s",
        settings.display_order_count,
        len(ads),
        len(details),
        count_binance_descriptions(ads),
    )
    blocks = build_binance_order_blocks(ads)
    order_urls = build_binance_order_urls(ads)

    logger.info("P2P Binance sending paginated message: blocks=%s", len(blocks))
    await send_paginated_html_blocks(
        message,
        title=title,
        blocks=blocks,
        order_urls=order_urls,
    )
