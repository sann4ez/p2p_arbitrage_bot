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
    "description",
    "desc",
    "autoReplyMsg",
    "tradingTerms",
    "terms",
    "orderDescription",
    "orderRemark",
    "publicOrderRemark",
    "paymentDescription",
    "paymentRemark",
    "remarkMsg",
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

    return (
        order.get("_order_description"),
        *(detail.get(field) for field in OKX_DESCRIPTION_FIELDS),
        *(order.get(field) for field in OKX_DESCRIPTION_FIELDS),
    )
