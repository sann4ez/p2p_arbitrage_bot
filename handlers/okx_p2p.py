import logging
from html import escape

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from db.base import AsyncSessionLocal
from db.dto import P2PUserPair
from fsm.states import P2PExchange
from keyboards.menu import BTN_UAH_TO_USDT, BTN_USDT_TO_UAH
from services.okx_client import fetch_okx_p2p, fetch_okx_p2p_details
from services.okx_order_payload import get_okx_order_id
from services.p2p_filters import (
    filter_orders_by_payment_methods,
    filter_orders,
    filters_summary,
    get_fetch_order_count,
    get_filters,
    summarize_filter_rejections,
    summarize_payment_method_rejections,
)
from services.payment_method_service import PaymentMethodService
from services.p2p_description_filter import (
    filter_orders_by_description_until,
    needs_description_filtering,
)
from services.p2p_order_formatter import (
    attach_okx_details,
    build_okx_order_blocks,
    build_okx_order_urls,
    count_okx_descriptions,
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


@router.message(StateFilter(P2PExchange.okx), F.text == BTN_UAH_TO_USDT)
async def uah_to_usdt(message: types.Message, state: FSMContext):
    pair = await get_current_pair_from_state(state)

    if not pair:
        await ask_to_choose_pair(message)
        return

    await send_okx_ads(
        message=message,
        pair=pair,
        side="sell",
        title=f"OKX P2P | Купівля {pair.crypto_code} за {pair.fiat_code}",
    )


@router.message(StateFilter(P2PExchange.okx), F.text == BTN_USDT_TO_UAH)
async def usdt_to_uah(message: types.Message, state: FSMContext):
    pair = await get_current_pair_from_state(state)

    if not pair:
        await ask_to_choose_pair(message)
        return

    await send_okx_ads(
        message=message,
        pair=pair,
        side="buy",
        title=f"OKX P2P | Продаж {pair.crypto_code} за {pair.fiat_code}",
    )


async def send_okx_ads(
    *,
    message: types.Message,
    pair: P2PUserPair,
    side: str,
    title: str,
):
    rate_limit = await check_p2p_user_rate_limit(message.from_user.id)

    if not rate_limit.allowed:
        await message.answer(format_rate_limit_message(rate_limit.wait_seconds))
        return

    async with AsyncSessionLocal() as session:
        settings = await get_filters(session, message.from_user.id)
        payment_methods = await PaymentMethodService(
            session
        ).list_user_selected_methods_for_fiat_code(
            message.from_user.id,
            pair.fiat_code,
        )

    fetch_rows = get_fetch_order_count(settings)
    logger.info(
        "P2P OKX flow start: telegram_id=%s side=%s pair=%s fetch_rows=%s display_count=%s desc_mode=%s payment_categories=%s selected_banks=%s max_minutes=%s min_trades=%s min_rating=%s min_completion=%s allow_split=%s allow_third_party=%s allow_monobank_jar=%s",
        message.from_user.id,
        side,
        pair.label,
        fetch_rows,
        settings.display_order_count,
        settings.description_check_mode,
        sorted(settings.payment_categories),
        format_selected_payment_methods(payment_methods),
        settings.max_order_minutes,
        settings.min_trades,
        settings.min_rating,
        settings.min_completion,
        settings.allow_split_payments,
        settings.allow_third_party_payments,
        settings.allow_monobank_jar_payments,
    )

    ads = await fetch_filtered_okx_ads_for_pair(
        pair=pair,
        side=side,
        settings=settings,
        fetch_rows=fetch_rows,
        payment_methods=payment_methods,
    )
    blocks = build_okx_order_blocks(
        ads,
        side,
        asset=pair.crypto_code,
        fiat=pair.fiat_code,
    )
    order_urls = build_okx_order_urls(
        ads,
        side,
        asset=pair.crypto_code,
        fiat=pair.fiat_code,
    )

    if not blocks:
        logger.info(
            "P2P OKX stopped: reason=no_output_orders side=%s pair=%s",
            side,
            pair.label,
        )
        await message.answer(
            "OKX не знайшов ордери за обраною парою або всі вони відсіялись "
            "фільтрами.\n\n"
            f"Пара: {pair.label}\n\n"
            f"{filters_summary(settings)}\n"
            f"• Банки: {escape(format_selected_payment_methods(payment_methods))}"
        )
        return

    logger.info("P2P OKX sending paginated message: blocks=%s", len(blocks))
    await send_paginated_html_blocks(
        message,
        title=title,
        blocks=blocks,
        order_urls=order_urls,
    )


async def fetch_filtered_okx_ads_for_pair(
    *,
    pair,
    side: str,
    settings,
    fetch_rows: int,
    payment_methods,
) -> list[dict]:
    ads = await get_cached_p2p_orders(
        exchange="okx",
        direction=side,
        rows=fetch_rows,
        pair_key=pair.label,
        fetcher=lambda: fetch_okx_p2p(
            side=side,
            asset=pair.crypto_code,
            fiat=pair.fiat_code,
            rows=fetch_rows,
        ),
    )
    logger.info("P2P OKX fetched: side=%s pair=%s rows=%s", side, pair.label, len(ads))

    if not ads:
        logger.warning(
            "P2P OKX pair skipped: reason=no_orders side=%s pair=%s",
            side,
            pair.label,
        )
        return []

    filtered_ads = filter_orders(
        ads,
        "okx",
        settings,
        apply_description_filters=False,
        apply_payment_filters=not needs_description_filtering(settings),
    )
    rejection_summary = summarize_filter_rejections(
        ads,
        "okx",
        settings,
        apply_description_filters=False,
        apply_payment_filters=not needs_description_filtering(settings),
    )
    logger.info(
        "P2P OKX base filters result: pair=%s input=%s output=%s blocked=%s reasons=%s",
        pair.label,
        len(ads),
        len(filtered_ads),
        len(ads) - len(filtered_ads),
        rejection_summary,
    )

    if not filtered_ads:
        logger.info(
            "P2P OKX pair skipped: reason=all_blocked_by_base_filters pair=%s",
            pair.label,
        )
        return []

    if payment_methods:
        payment_filtered_ads = filter_orders_by_payment_methods(
            filtered_ads,
            "okx",
            payment_methods,
        )
        payment_rejection_summary = summarize_payment_method_rejections(
            filtered_ads,
            "okx",
            payment_methods,
        )
        logger.info(
            "P2P OKX user payment filter result: pair=%s selected=%s input=%s output=%s blocked=%s reasons=%s methods=%s",
            pair.label,
            len(payment_methods),
            len(filtered_ads),
            len(payment_filtered_ads),
            len(filtered_ads) - len(payment_filtered_ads),
            payment_rejection_summary,
            format_selected_payment_methods(payment_methods),
        )
        filtered_ads = payment_filtered_ads

        if not filtered_ads:
            logger.info(
                "P2P OKX pair skipped: reason=all_blocked_by_user_payment_methods pair=%s",
                pair.label,
            )
            return []
    else:
        logger.info(
            "P2P OKX user payment filter skipped: pair=%s reason=no_selected_banks",
            pair.label,
        )

    if needs_description_filtering(settings):
        async def prepare_okx_description_batch(candidates: list[dict]):
            details = await get_cached_p2p_details(
                exchange="okx",
                item_ids=[get_okx_order_id(ad) for ad in candidates],
                fetcher=lambda order_ids: fetch_okx_p2p_details(
                    order_ids,
                    side=side,
                    asset=pair.crypto_code,
                    fiat=pair.fiat_code,
                ),
            )
            attach_okx_details(candidates, details)
            logger.info(
                "P2P OKX detail fetch for description filters: pair=%s candidates=%s details=%s descriptions=%s",
                pair.label,
                len(candidates),
                len(details),
                count_okx_descriptions(candidates),
            )

        filtered_ads = await filter_orders_by_description_until(
            filtered_ads,
            "okx",
            settings,
            limit=settings.display_order_count,
            prepare_batch=prepare_okx_description_batch,
        )
        logger.info("P2P OKX description filters result: output=%s", len(filtered_ads))

        if not filtered_ads:
            logger.info(
                "P2P OKX pair skipped: reason=all_blocked_by_description_filters pair=%s",
                pair.label,
            )
            return []

    ads = filtered_ads[: settings.display_order_count]
    details = await get_cached_p2p_details(
        exchange="okx",
        item_ids=[
            get_okx_order_id(ad)
            for ad in ads
            if not isinstance(ad.get("_detail"), dict)
        ],
        fetcher=lambda order_ids: fetch_okx_p2p_details(
            order_ids,
            side=side,
            asset=pair.crypto_code,
            fiat=pair.fiat_code,
        ),
    )
    attach_okx_details(ads, details)
    logger.info(
        "P2P OKX output selected: pair=%s requested=%s selected=%s extra_details=%s descriptions=%s",
        pair.label,
        settings.display_order_count,
        len(ads),
        len(details),
        count_okx_descriptions(ads),
    )

    return ads


async def get_current_pair_from_state(state: FSMContext) -> P2PUserPair | None:
    data = await state.get_data()

    if not data.get("p2p_pair_crypto_code") or not data.get("p2p_pair_fiat_code"):
        return None

    return P2PUserPair(
        crypto_currency_id=int(data.get("p2p_pair_crypto_currency_id") or 0),
        fiat_currency_id=int(data.get("p2p_pair_fiat_currency_id") or 0),
        crypto_code=str(data["p2p_pair_crypto_code"]),
        fiat_code=str(data["p2p_pair_fiat_code"]),
        is_selected=True,
    )


async def ask_to_choose_pair(message: types.Message):
    await message.answer(
        "Спочатку оберіть пару для цієї біржі. Натисніть Назад і виберіть біржу ще раз."
    )


def format_selected_payment_methods(payment_methods) -> str:
    if not payment_methods:
        return "без обмеження"

    return ", ".join(method.name for method in payment_methods)
