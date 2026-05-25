import logging

from db.dto import P2PFilterSettings
from services.p2p_filters import (
    DESCRIPTION_CHECK_GPT,
    filter_orders,
    get_binance_order_metrics,
    get_okx_order_metrics,
    normalize_description_check_mode,
    normalize_order_description,
)
from services.p2p_gpt_classifier import classify_p2p_descriptions

logger = logging.getLogger(__name__)


def needs_description_filtering(settings: P2PFilterSettings) -> bool:
    return not settings.allow_third_party_payments or not settings.allow_split_payments


async def filter_orders_by_description(
    orders: list[dict],
    exchange: str,
    settings: P2PFilterSettings,
) -> list[dict]:
    logger.info(
        "P2P description filter start: exchange=%s orders=%s mode=%s allow_split=%s allow_third_party=%s",
        exchange,
        len(orders),
        normalize_description_check_mode(settings.description_check_mode),
        settings.allow_split_payments,
        settings.allow_third_party_payments,
    )

    if not needs_description_filtering(settings):
        logger.info(
            "P2P description filter skipped: exchange=%s reason=no_description_filters_enabled orders=%s",
            exchange,
            len(orders),
        )
        return orders

    if normalize_description_check_mode(settings.description_check_mode) != DESCRIPTION_CHECK_GPT:
        filtered_orders = filter_orders(orders, exchange, settings)
        logger.info(
            "P2P description filter regex result: exchange=%s input=%s output=%s blocked=%s",
            exchange,
            len(orders),
            len(filtered_orders),
            len(orders) - len(filtered_orders),
        )
        return filtered_orders

    descriptions = [get_order_description(order, exchange) for order in orders]
    descriptions_count = sum(1 for description in descriptions if description)
    logger.info(
        "P2P description filter GPT input: exchange=%s orders=%s descriptions=%s empty_descriptions=%s",
        exchange,
        len(orders),
        descriptions_count,
        len(orders) - descriptions_count,
    )
    classifications = await classify_p2p_descriptions(descriptions)

    if not classifications:
        filtered_orders = filter_orders(orders, exchange, settings)
        logger.warning(
            "P2P description filter GPT fallback to regex: exchange=%s input=%s output=%s reason=no_classifications",
            exchange,
            len(orders),
            len(filtered_orders),
        )
        return filtered_orders

    filtered_orders = []
    blocked_split = 0
    blocked_third_party = 0
    blocked_both = 0
    missing_classifications = 0
    regex_fallback_blocked = 0
    confidence_sum = 0.0

    for index, order in enumerate(orders):
        classification = classifications.get(index)

        if not classification:
            missing_classifications += 1

            if order_matches_regex_description(order, exchange, settings):
                filtered_orders.append(order)
            else:
                regex_fallback_blocked += 1

            continue

        confidence_sum += classification.confidence
        blocked_by_split = (
            not settings.allow_split_payments and classification.split_payments
        )
        blocked_by_third_party = (
            not settings.allow_third_party_payments and classification.third_party_payments
        )

        if blocked_by_split and blocked_by_third_party:
            blocked_both += 1
        elif blocked_by_split:
            blocked_split += 1
        elif blocked_by_third_party:
            blocked_third_party += 1

        if not blocked_by_split and not blocked_by_third_party:
            filtered_orders.append(order)

    avg_confidence = (
        confidence_sum / len(classifications)
        if classifications
        else 0.0
    )
    logger.info(
        "P2P description filter GPT result: exchange=%s input=%s output=%s classifications=%s missing=%s blocked_split=%s blocked_third_party=%s blocked_both=%s regex_fallback_blocked=%s avg_confidence=%.2f",
        exchange,
        len(orders),
        len(filtered_orders),
        len(classifications),
        missing_classifications,
        blocked_split,
        blocked_third_party,
        blocked_both,
        regex_fallback_blocked,
        avg_confidence,
    )

    return filtered_orders


def order_matches_gpt_classification(classification, settings: P2PFilterSettings) -> bool:
    if not settings.allow_third_party_payments and classification.third_party_payments:
        return False

    if not settings.allow_split_payments and classification.split_payments:
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

    return True


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

    return normalize_order_description(
        order.get("_order_description"),
        order.get("remarks"),
        order.get("remark"),
        order.get("description"),
        order.get("desc"),
        order.get("autoReplyMsg"),
        order.get("tradingTerms"),
        order.get("terms"),
    )
