import logging
from collections.abc import Awaitable, Callable

from db.dto import PAYMENT_CATEGORIES, P2PFilterSettings
from services.okx_order_payload import get_okx_order_description_values
from services.p2p_filters import (
    DESCRIPTION_CHECK_GPT,
    DESCRIPTION_CHECK_REGEX_GPT,
    filter_orders,
    get_binance_order_metrics,
    get_okx_order_metrics,
    normalize_description_check_mode,
    normalize_order_description,
)
from services.p2p_gpt_classifier import classify_p2p_descriptions

logger = logging.getLogger(__name__)
MIN_DESCRIPTION_FILTER_BATCH_SIZE = 10
MAX_DESCRIPTION_FILTER_BATCH_SIZE = 50


def needs_description_filtering(settings: P2PFilterSettings) -> bool:
    return (
        not settings.allow_third_party_payments
        or not settings.allow_split_payments
        or not settings.allow_monobank_jar_payments
        or settings.payment_categories != PAYMENT_CATEGORIES
    )


async def filter_orders_by_description(
    orders: list[dict],
    exchange: str,
    settings: P2PFilterSettings,
) -> list[dict]:
    mode = normalize_description_check_mode(settings.description_check_mode)

    logger.info(
        "P2P description filter start: exchange=%s orders=%s mode=%s allow_split=%s allow_third_party=%s allow_monobank_jar=%s",
        exchange,
        len(orders),
        mode,
        settings.allow_split_payments,
        settings.allow_third_party_payments,
        settings.allow_monobank_jar_payments,
    )

    if not needs_description_filtering(settings):
        logger.info(
            "P2P description filter skipped: exchange=%s reason=no_description_filters_enabled orders=%s",
            exchange,
            len(orders),
        )
        return orders

    if mode not in (DESCRIPTION_CHECK_GPT, DESCRIPTION_CHECK_REGEX_GPT):
        filtered_orders = [
            order
            for order in filter_orders(orders, exchange, settings)
            if not should_block_missing_description(order, exchange)
        ]
        logger.info(
            "P2P description filter regex result: exchange=%s input=%s output=%s blocked=%s",
            exchange,
            len(orders),
            len(filtered_orders),
            len(orders) - len(filtered_orders),
        )
        return filtered_orders

    gpt_orders = orders

    if mode == DESCRIPTION_CHECK_GPT:
        gpt_orders = filter_orders(
            orders,
            exchange,
            settings,
            apply_description_filters=False,
        )
        logger.info(
            "P2P description filter detail-aware base result before GPT: exchange=%s input=%s output=%s blocked=%s",
            exchange,
            len(orders),
            len(gpt_orders),
            len(orders) - len(gpt_orders),
        )

        if not gpt_orders:
            return []

    if mode == DESCRIPTION_CHECK_REGEX_GPT:
        gpt_orders = filter_orders(orders, exchange, settings)
        logger.info(
            "P2P description filter regex prefilter result: exchange=%s input=%s output=%s blocked=%s",
            exchange,
            len(orders),
            len(gpt_orders),
            len(orders) - len(gpt_orders),
        )

        if not gpt_orders:
            return []

    descriptions = [get_order_description(order, exchange) for order in gpt_orders]
    descriptions_count = sum(1 for description in descriptions if description)
    logger.info(
        "P2P description filter GPT input: exchange=%s orders=%s descriptions=%s empty_descriptions=%s",
        exchange,
        len(gpt_orders),
        descriptions_count,
        len(gpt_orders) - descriptions_count,
    )
    classifications = await classify_p2p_descriptions(descriptions)

    if not classifications:
        fallback_orders = (
            gpt_orders
            if mode == DESCRIPTION_CHECK_REGEX_GPT
            else filter_orders(orders, exchange, settings)
        )
        filtered_orders = [
            order
            for order in fallback_orders
            if not should_block_missing_description(order, exchange)
        ]
        logger.warning(
            "P2P description filter GPT fallback to regex: exchange=%s input=%s output=%s reason=no_classifications",
            exchange,
            len(gpt_orders),
            len(filtered_orders),
        )
        return filtered_orders

    filtered_orders = []
    blocked_split = 0
    blocked_third_party = 0
    blocked_monobank_jar = 0
    blocked_both = 0
    blocked_multiple_reasons = 0
    missing_classifications = 0
    missing_descriptions_blocked = 0
    regex_safety_blocked = 0

    for index, order in enumerate(gpt_orders):
        if not order_matches_regex_description(order, exchange, settings):
            regex_safety_blocked += 1
            continue

        classification = classifications.get(index)

        if not classification:
            missing_classifications += 1

            if should_block_missing_description(order, exchange):
                missing_descriptions_blocked += 1
                continue

            filtered_orders.append(order)

            continue

        blocked_by_split = (
            not settings.allow_split_payments and classification.split_payments
        )
        blocked_by_third_party = (
            not settings.allow_third_party_payments and classification.third_party_payments
        )
        blocked_by_monobank_jar = (
            not settings.allow_monobank_jar_payments
            and classification.monobank_jar_payments
        )
        blocked_reasons_count = sum(
            (
                blocked_by_split,
                blocked_by_third_party,
                blocked_by_monobank_jar,
            )
        )

        if blocked_reasons_count > 1:
            blocked_multiple_reasons += 1
            if blocked_by_split and blocked_by_third_party and not blocked_by_monobank_jar:
                blocked_both += 1
        elif blocked_by_split:
            blocked_split += 1
        elif blocked_by_third_party:
            blocked_third_party += 1
        elif blocked_by_monobank_jar:
            blocked_monobank_jar += 1

        if blocked_reasons_count == 0:
            filtered_orders.append(order)

    logger.info(
        "P2P description filter GPT result: exchange=%s input=%s output=%s classifications=%s missing=%s missing_descriptions_blocked=%s blocked_split=%s blocked_third_party=%s blocked_monobank_jar=%s blocked_both=%s blocked_multiple_reasons=%s regex_safety_blocked=%s",
        exchange,
        len(gpt_orders),
        len(filtered_orders),
        len(classifications),
        missing_classifications,
        missing_descriptions_blocked,
        blocked_split,
        blocked_third_party,
        blocked_monobank_jar,
        blocked_both,
        blocked_multiple_reasons,
        regex_safety_blocked,
    )

    return filtered_orders


async def filter_orders_by_description_until(
    orders: list[dict],
    exchange: str,
    settings: P2PFilterSettings,
    *,
    limit: int,
    prepare_batch: Callable[[list[dict]], Awaitable[None]],
) -> list[dict]:
    if limit <= 0 or not orders:
        return []

    if not needs_description_filtering(settings):
        return orders[:limit]

    selected_orders = []
    batch_size = get_description_filter_batch_size(limit)

    logger.info(
        "P2P description filter progressive start: exchange=%s input=%s limit=%s batch_size=%s",
        exchange,
        len(orders),
        limit,
        batch_size,
    )

    for start in range(0, len(orders), batch_size):
        batch = orders[start:start + batch_size]
        await prepare_batch(batch)
        filtered_batch = await filter_orders_by_description(batch, exchange, settings)
        selected_orders.extend(filtered_batch)

        logger.info(
            "P2P description filter progressive step: exchange=%s checked=%s/%s batch_input=%s batch_output=%s selected=%s/%s",
            exchange,
            min(start + len(batch), len(orders)),
            len(orders),
            len(batch),
            len(filtered_batch),
            len(selected_orders),
            limit,
        )

        if len(selected_orders) >= limit:
            break

    return selected_orders[:limit]


def get_description_filter_batch_size(limit: int) -> int:
    return min(
        MAX_DESCRIPTION_FILTER_BATCH_SIZE,
        max(MIN_DESCRIPTION_FILTER_BATCH_SIZE, limit * 2),
    )


def order_matches_gpt_classification(classification, settings: P2PFilterSettings) -> bool:
    if not settings.allow_third_party_payments and classification.third_party_payments:
        return False

    if not settings.allow_split_payments and classification.split_payments:
        return False

    if (
        not settings.allow_monobank_jar_payments
        and classification.monobank_jar_payments
    ):
        return False

    return True


def order_matches_regex_description(
    order: dict,
    exchange: str,
    settings: P2PFilterSettings,
) -> bool:
    metrics = (
        get_binance_order_metrics(order)
        if exchange == "binance"
        else get_okx_order_metrics(order)
    )

    if not settings.allow_third_party_payments and metrics["third_party_payments"]:
        return False

    if not settings.allow_split_payments and metrics["split_payments"]:
        return False

    if (
        not settings.allow_monobank_jar_payments
        and metrics["monobank_jar_payments"]
    ):
        return False

    return True


def should_block_missing_description(order: dict, exchange: str) -> bool:
    return exchange == "okx" and not get_order_description(order, exchange)


def get_order_description(order: dict, exchange: str) -> str | None:
    if exchange == "binance":
        adv = order.get("adv", {})
        detail = order.get("_detail") if isinstance(order.get("_detail"), dict) else {}

        return normalize_order_description(
            order.get("_order_description"),
            detail.get("remarks"),
            detail.get("autoReplyMsg"),
            adv.get("remarks"),
            adv.get("autoReplyMsg"),
        )

    return normalize_order_description(*get_okx_order_description_values(order))
