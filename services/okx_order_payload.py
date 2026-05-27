OKX_ORDER_ID_FIELDS = (
    "id",
    "orderId",
    "adId",
    "advertisementId",
)

OKX_DETAIL_NESTED_FIELDS = (
    "data",
    "order",
    "detail",
    "tradingOrder",
    "advertisement",
    "ad",
)

OKX_DESCRIPTION_FIELDS = (
    "remarks",
    "remark",
    "remarkText",
    "description",
    "desc",
    "orderDesc",
    "adDescription",
    "autoReplyMsg",
    "automatedMessage",
    "tradingTerms",
    "tradingOrderTerms",
    "terms",
    "conditions",
    "condition",
    "instructions",
    "instruction",
    "orderDescription",
    "orderRemark",
    "tradingOrderRemark",
    "publicOrderRemark",
    "publicRemark",
    "advertisementRemark",
    "paymentDescription",
    "paymentInstructions",
    "paymentInfo",
    "paymentRemark",
    "remarkMsg",
    "userRemark",
    "userRemarks",
    "note",
    "memo",
)


def get_okx_order_id(order: dict) -> str | None:
    for field in OKX_ORDER_ID_FIELDS:
        value = order.get(field)

        if value:
            return str(value)

    return None


def get_okx_order_detail(order: dict) -> dict:
    detail = order.get("_detail")

    if not isinstance(detail, dict):
        return {}

    return flatten_okx_detail(detail)


def flatten_okx_detail(detail: dict) -> dict:
    if not isinstance(detail, dict):
        return {}

    flattened = {}

    for field in OKX_DETAIL_NESTED_FIELDS:
        nested = detail.get(field)

        if isinstance(nested, dict):
            flattened.update(nested)

    flattened.update(detail)

    return flattened


def get_okx_order_description_values(order: dict) -> tuple:
    detail = get_okx_order_detail(order)
    raw_detail = order.get("_detail") if isinstance(order.get("_detail"), dict) else {}

    values = [
        order.get("_order_description"),
        *(detail.get(field) for field in OKX_DESCRIPTION_FIELDS),
        *(iter_okx_values_by_key(raw_detail, OKX_DESCRIPTION_FIELDS)),
        *(order.get(field) for field in OKX_DESCRIPTION_FIELDS),
        *(iter_okx_values_by_key(order, OKX_DESCRIPTION_FIELDS)),
    ]

    return tuple(unique_values(values))


def iter_okx_values_by_key(value, fields: tuple[str, ...]):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in fields:
                yield item

            yield from iter_okx_values_by_key(item, fields)

    if isinstance(value, list):
        for item in value:
            yield from iter_okx_values_by_key(item, fields)


def unique_values(values):
    seen = set()

    for value in values:
        if value in (None, ""):
            continue

        key = str(value)

        if key in seen:
            continue

        seen.add(key)
        yield value
