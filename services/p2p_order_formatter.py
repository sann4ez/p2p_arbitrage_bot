from html import escape
from urllib.parse import quote

from db.dto import P2POrderMessage


BINANCE_P2P_AD_URL = "https://c2c.binance.com/en/adv?code={adv_no}"
OKX_P2P_MARKET_URLS = {
    "sell": "https://www.okx.com/p2p-markets/uah/buy-usdt",
    "buy": "https://www.okx.com/p2p-markets/uah/sell-usdt",
}
ORDER_DESCRIPTION_LIMIT = 450


def build_binance_order_blocks(ads: list[dict]) -> list[str]:
    return [format_order_message(build_binance_order_message(ad)) for ad in ads]


def build_okx_order_blocks(ads: list[dict], side: str) -> list[str]:
    return [format_order_message(build_okx_order_message(ad, side)) for ad in ads]


def build_binance_order_message(ad: dict) -> P2POrderMessage:
    adv = ad.get("adv", {})
    advertiser = ad.get("advertiser", {})
    detail = ad.get("_detail") if isinstance(ad.get("_detail"), dict) else {}

    return P2POrderMessage(
        merchant=advertiser.get("nickName", "Невідомий мерчант"),
        price=adv.get("price"),
        min_amount=adv.get("minSingleTransAmount"),
        max_amount=adv.get("dynamicMaxSingleTransAmount"),
        payment_methods=format_binance_payment_methods(adv.get("tradeMethods", [])),
        available=adv.get("tradableQuantity") or adv.get("surplusAmount"),
        orders_count=advertiser.get("monthOrderCount") or advertiser.get("orderCount"),
        rating=format_percent(advertiser.get("positiveRate")),
        completion_rate=format_percent(advertiser.get("monthFinishRate")),
        trade_minutes=adv.get("payTimeLimit"),
        description=format_order_description(
            ad.get("_order_description"),
            detail.get("remarks"),
            detail.get("autoReplyMsg"),
            adv.get("remarks"),
            adv.get("autoReplyMsg"),
        ),
        order_url=build_binance_order_url(ad),
    )


def build_okx_order_message(ad: dict, side: str) -> P2POrderMessage:
    rating = format_okx_rating(ad)
    completion_rate = format_percent(ad.get("completedRate"))

    if completion_rate == rating:
        completion_rate = None

    return P2POrderMessage(
        merchant=ad.get("nickName", "Невідомий мерчант"),
        price=ad.get("price"),
        min_amount=ad.get("quoteMinAmountPerOrder"),
        max_amount=ad.get("quoteMaxAmountPerOrder"),
        payment_methods=", ".join(ad.get("paymentMethods", [])[:3]),
        available=ad.get("availableAmount"),
        orders_count=ad.get("completedOrderQuantity"),
        rating=rating,
        completion_rate=completion_rate,
        trade_minutes=ad.get("paymentTimeoutMinutes"),
        description=format_order_description(
            ad.get("remarks"),
            ad.get("remark"),
            ad.get("description"),
            ad.get("desc"),
            ad.get("autoReplyMsg"),
            ad.get("tradingTerms"),
            ad.get("terms"),
        ),
        order_url=build_okx_order_url(ad, side),
    )


def format_order_message(order: P2POrderMessage) -> str:
    lines = [
        f"👤 {escape(str(order.merchant))}",
        f"💰 Ціна: <b>{order.price} UAH</b>",
        f"📦 Ліміт: {order.min_amount} – {order.max_amount}",
    ]

    if order.payment_methods:
        lines.append(f"🏦 Оплата: {escape(order.payment_methods)}")

    if order.available:
        lines.append(f"💵 Доступно: {order.available} USDT")

    if order.orders_count is not None:
        lines.append(f"📊 Угоди: {order.orders_count}")

    if order.rating:
        lines.append(f"⭐ Оцінка: {order.rating}")

    if order.completion_rate:
        lines.append(f"✅ Виконання: {order.completion_rate}")

    if order.trade_minutes:
        lines.append(f"⏱ Час угоди: {order.trade_minutes} хв")

    lines.append(
        f"📝 Опис: {escape(order.description) if order.description else 'не вказано'}"
    )

    if order.order_url:
        lines.append(
            f'🔗 Ордер: <a href="{escape(order.order_url, quote=True)}">відкрити</a>'
        )

    return "\n".join(lines)


def attach_binance_details(ads: list[dict], details: dict[str, dict]):
    for ad in ads:
        adv_no = ad.get("adv", {}).get("advNo")

        if not adv_no:
            continue

        detail = details.get(str(adv_no))

        if detail:
            ad["_detail"] = detail


def count_binance_descriptions(ads: list[dict]) -> int:
    return sum(1 for ad in ads if build_binance_order_message(ad).description)


def count_okx_descriptions(ads: list[dict]) -> int:
    return sum(1 for ad in ads if build_okx_order_message(ad, "sell").description)


def build_binance_order_url(ad: dict) -> str | None:
    adv_no = ad.get("adv", {}).get("advNo")

    if not adv_no:
        return None

    return BINANCE_P2P_AD_URL.format(adv_no=adv_no)


def build_okx_order_url(ad: dict, side: str) -> str | None:
    base_url = OKX_P2P_MARKET_URLS.get(side)

    if not base_url:
        return None

    order_id = ad.get("id")

    if not order_id:
        return base_url

    return f"{base_url}?id={quote(str(order_id))}"


def format_binance_payment_methods(methods: list[dict]) -> str:
    names = []

    for method in methods[:3]:
        name = (
            method.get("tradeMethodShortName")
            or method.get("tradeMethodName")
            or method.get("identifier")
            or method.get("payType")
        )

        if name:
            names.append(str(name))

    return ", ".join(names)


def format_okx_rating(ad: dict) -> str | None:
    positive_rating = format_percent(ad.get("posReviewPercentage"))

    if positive_rating:
        return positive_rating

    return format_percent(ad.get("completedRate"))


def format_order_description(*values) -> str | None:
    for value in values:
        if not value:
            continue

        lines = [
            line.strip()
            for line in str(value).replace("\r", "\n").split("\n")
            if line.strip()
        ]
        text = "\n".join(lines)

        if not text:
            continue

        if len(text) > ORDER_DESCRIPTION_LIMIT:
            return text[:ORDER_DESCRIPTION_LIMIT].rstrip() + "..."

        return text

    return None


def format_percent(value) -> str | None:
    if value in (None, "", -1, "-1"):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if number <= 1:
        number *= 100

    return f"{number:.2f}".rstrip("0").rstrip(".") + "%"
