import logging
from html import escape

from aiogram import types
from aiogram.fsm.context import FSMContext

from db.base import AsyncSessionLocal
from db.dto import P2PUserPair
from services.payment_method_service import PaymentMethodService
from services.p2p_exchange_drivers import P2PExchangeDriver
from services.p2p_filters import (
    filters_summary,
    get_fetch_order_count,
    get_filters,
)
from services.p2p_request_guard import (
    check_p2p_user_rate_limit,
    format_rate_limit_message,
)
from services.p2p_scan_runner import fetch_filtered_p2p_orders
from services.p2p_statistics_service import (
    STAT_SCOPE_FILTER,
    build_statistics_filter_hash,
    record_p2p_scan_snapshot,
)
from services.telegram_messages import send_paginated_html_blocks


logger = logging.getLogger(__name__)


async def send_p2p_ads(
    *,
    message: types.Message,
    pair: P2PUserPair,
    driver: P2PExchangeDriver,
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
        "P2P flow start: telegram_id=%s exchange=%s side=%s pair=%s fetch_rows=%s display_count=%s desc_mode=%s payment_categories=%s selected_banks=%s max_minutes=%s min_trades=%s min_rating=%s min_completion=%s allow_split=%s allow_third_party=%s allow_monobank_jar=%s",
        message.from_user.id,
        driver.exchange,
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

    orders = await fetch_filtered_p2p_orders(
        exchange_code=driver.exchange_code,
        pair=pair,
        side=side,
        settings=settings,
        fetch_rows=fetch_rows,
        payment_methods=payment_methods,
        output_limit=settings.display_order_count,
        ensure_details=True,
    )

    if orders:
        await record_p2p_scan_snapshot(
            exchange_code=driver.exchange_code,
            pair=pair,
            side=side,
            orders=orders,
            requested_rows=fetch_rows,
            scope=STAT_SCOPE_FILTER,
            filter_hash=build_statistics_filter_hash(
                exchange_code=driver.exchange_code,
                pair=pair,
                side=side,
                settings=settings,
                payment_methods=payment_methods,
            ),
        )

    blocks = driver.build_order_blocks(orders, side, pair)
    order_urls = driver.build_order_urls(orders, side, pair)

    if not blocks:
        logger.info(
            "P2P flow stopped: reason=no_output_orders exchange=%s side=%s pair=%s",
            driver.exchange,
            side,
            pair.label,
        )
        await message.answer(
            f"{driver.display_name} не знайшов ордери за обраною парою або всі вони відсіялись "
            "фільтрами.\n\n"
            f"Пара: {pair.label}\n\n"
            f"{filters_summary(settings)}\n"
            f"• Банки: {escape(format_selected_payment_methods(payment_methods))}"
        )
        return

    logger.info(
        "P2P flow sending paginated message: exchange=%s blocks=%s",
        driver.exchange,
        len(blocks),
    )
    await send_paginated_html_blocks(
        message,
        title=title,
        blocks=blocks,
        order_urls=order_urls,
    )


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
