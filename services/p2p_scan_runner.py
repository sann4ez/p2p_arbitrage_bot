import logging

from services.p2p_description_filter import (
    filter_orders_by_description_until,
    needs_configurable_description_filtering,
    needs_description_filtering,
)
from services.p2p_exchange_drivers import (
    P2PExchangeDriver,
    get_p2p_exchange_driver,
)
from services.p2p_filters import (
    filter_orders,
    filter_orders_by_payment_methods,
    summarize_filter_rejections,
    summarize_payment_method_rejections,
)
from services.p2p_request_guard import get_cached_p2p_details, get_cached_p2p_orders


logger = logging.getLogger(__name__)


async def fetch_filtered_p2p_orders(
    *,
    exchange_code: str,
    pair,
    side: str,
    settings,
    fetch_rows: int,
    payment_methods,
    output_limit: int | None = None,
    ensure_details: bool = False,
    force_orders_refresh: bool = False,
) -> list[dict]:
    try:
        driver = get_p2p_exchange_driver(exchange_code)
    except ValueError:
        logger.warning("P2P scan skipped: unsupported exchange=%s", exchange_code)
        return []

    limit = output_limit or fetch_rows
    orders = await get_cached_p2p_orders(
        exchange=driver.exchange,
        direction=side,
        rows=fetch_rows,
        pair_key=pair.label,
        fetcher=lambda: driver.fetch_orders(side, pair, fetch_rows),
        force_refresh=force_orders_refresh,
    )
    logger.debug(
        "P2P scan fetched: exchange=%s pair=%s side=%s rows=%s",
        driver.exchange,
        pair.label,
        side,
        len(orders),
    )

    return await apply_common_filters(
        orders,
        driver=driver,
        pair=pair,
        side=side,
        settings=settings,
        limit=limit,
        payment_methods=payment_methods,
        ensure_details=ensure_details,
    )


async def apply_common_filters(
    orders: list[dict],
    *,
    driver: P2PExchangeDriver,
    pair,
    side: str,
    settings,
    limit: int,
    payment_methods,
    ensure_details: bool = False,
) -> list[dict]:
    if not orders:
        logger.debug(
            "P2P scan no orders: exchange=%s pair=%s side=%s",
            driver.exchange,
            pair.label,
            side,
        )
        return []

    apply_payment_filters = not needs_configurable_description_filtering(settings)
    filtered = filter_orders(
        orders,
        driver.exchange,
        settings,
        apply_description_filters=False,
        apply_payment_filters=apply_payment_filters,
    )
    logger.debug(
        "P2P scan base filters: exchange=%s pair=%s side=%s input=%s output=%s reasons=%s",
        driver.exchange,
        pair.label,
        side,
        len(orders),
        len(filtered),
        summarize_filter_rejections(
            orders,
            driver.exchange,
            settings,
            apply_description_filters=False,
            apply_payment_filters=apply_payment_filters,
        ),
    )

    if not filtered:
        return []

    if payment_methods:
        before = filtered
        filtered = filter_orders_by_payment_methods(
            filtered,
            driver.exchange,
            payment_methods,
        )
        logger.debug(
            "P2P scan payment filters: exchange=%s pair=%s side=%s selected=%s input=%s output=%s reasons=%s",
            driver.exchange,
            pair.label,
            side,
            len(payment_methods),
            len(before),
            len(filtered),
            summarize_payment_method_rejections(
                before,
                driver.exchange,
                payment_methods,
            ),
        )
    else:
        logger.debug(
            "P2P scan payment filters skipped: exchange=%s pair=%s side=%s reason=no_selected_banks",
            driver.exchange,
            pair.label,
            side,
        )

    if not filtered:
        return []

    if needs_description_filtering(settings):
        async def prepare_description_batch(candidates: list[dict]):
            await attach_order_details(driver, candidates, side=side, pair=pair)

        filtered = await filter_orders_by_description_until(
            filtered,
            driver.exchange,
            settings,
            limit=limit,
            prepare_batch=prepare_description_batch,
            allow_missing_descriptions=should_allow_missing_descriptions(
                driver,
                side,
            ),
        )

    selected = filtered[:limit]

    if ensure_details:
        await attach_missing_order_details(driver, selected, side=side, pair=pair)

    logger.debug(
        "P2P scan selected: exchange=%s pair=%s side=%s requested=%s selected=%s descriptions=%s",
        driver.exchange,
        pair.label,
        side,
        limit,
        len(selected),
        driver.count_descriptions(selected),
    )
    return selected


def should_allow_missing_descriptions(driver: P2PExchangeDriver, side: str) -> bool:
    return (
        driver.exchange == "okx"
        and str(side).lower() == str(driver.fiat_to_crypto_side).lower()
    )


async def attach_order_details(
    driver: P2PExchangeDriver,
    orders: list[dict],
    *,
    side: str,
    pair,
):
    details = await get_cached_p2p_details(
        exchange=driver.exchange,
        item_ids=[driver.get_order_id(order) for order in orders],
        fetcher=lambda item_ids: driver.fetch_details(item_ids, side, pair),
    )
    driver.attach_details(orders, details)
    logger.debug(
        "P2P scan descriptions: exchange=%s pair=%s side=%s candidates=%s details=%s descriptions=%s",
        driver.exchange,
        pair.label,
        side,
        len(orders),
        len(details),
        driver.count_descriptions(orders),
    )


async def attach_missing_order_details(
    driver: P2PExchangeDriver,
    orders: list[dict],
    *,
    side: str,
    pair,
):
    missing_orders = [
        order
        for order in orders
        if not isinstance(order.get("_detail"), dict)
    ]

    if not missing_orders:
        return

    await attach_order_details(driver, missing_orders, side=side, pair=pair)
