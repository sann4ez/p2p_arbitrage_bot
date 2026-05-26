import asyncio
import time

import aiohttp

from services.okx_order_payload import flatten_okx_detail

OKX_P2P_URL = "https://www.okx.com/v3/c2c/tradingOrders/books"
OKX_P2P_DETAIL_URL = "https://www.okx.com/v3/c2c/tradingOrders/{order_id}"
OKX_DETAIL_CONCURRENCY = 10
OKX_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}


async def fetch_okx_p2p(
    *,
    side: str,
    asset: str = "USDT",
    fiat: str = "UAH",
    rows: int = 5,
):
    params = {
        "quoteCurrency": fiat,
        "baseCurrency": asset,
        "side": side.lower(),
        "paymentMethod": "all",
        "userType": "all",
        "showTrade": "false",
        "showFollow": "false",
        "showAlreadyTraded": "false",
        "isAbleFilter": "false",
    }
    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(headers=OKX_HEADERS, timeout=timeout) as session:
            async with session.get(OKX_P2P_URL, params=params) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return []

    if not is_okx_success_response(data):
        return []

    orders = data.get("data", {}).get(side.lower(), [])

    return orders[:rows]


async def fetch_okx_p2p_details(order_ids: list[object]) -> dict[str, dict]:
    unique_order_ids = []
    seen = set()

    for order_id in order_ids:
        if not order_id:
            continue

        order_id = str(order_id)

        if order_id in seen:
            continue

        unique_order_ids.append(order_id)
        seen.add(order_id)

    if not unique_order_ids:
        return {}

    timeout = aiohttp.ClientTimeout(total=20)
    semaphore = asyncio.Semaphore(OKX_DETAIL_CONCURRENCY)

    try:
        async with aiohttp.ClientSession(headers=OKX_HEADERS, timeout=timeout) as session:
            results = await asyncio.gather(
                *(
                    _fetch_okx_p2p_detail_limited(session, semaphore, order_id)
                    for order_id in unique_order_ids
                ),
                return_exceptions=True,
            )
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return {}

    details = {}

    for result in results:
        if not isinstance(result, tuple):
            continue

        order_id, detail = result

        if detail:
            details[order_id] = detail

    return details


async def _fetch_okx_p2p_detail_limited(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    order_id: str,
) -> tuple[str, dict]:
    async with semaphore:
        return await _fetch_okx_p2p_detail(session, order_id)


async def _fetch_okx_p2p_detail(
    session: aiohttp.ClientSession,
    order_id: str,
) -> tuple[str, dict]:
    headers = {
        "Referer": "https://www.okx.com/p2p-markets/uah/buy-usdt",
    }

    try:
        async with session.get(
            OKX_P2P_DETAIL_URL.format(order_id=order_id),
            params={"t": int(time.time() * 1000)},
            headers=headers,
        ) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return order_id, {}

    detail = extract_okx_detail(data)

    if not detail:
        return order_id, {}

    return order_id, detail


def extract_okx_detail(data: dict) -> dict:
    if not isinstance(data, dict):
        return {}

    if not is_okx_success_response(data):
        return {}

    detail = data.get("data", data)

    if isinstance(detail, list):
        detail = next((item for item in detail if isinstance(item, dict)), {})

    if not isinstance(detail, dict):
        return {}

    return flatten_okx_detail(detail)


def is_okx_success_response(data: dict) -> bool:
    if data.get("code") in (0, "0"):
        return True

    if data.get("error_code") in (0, "0"):
        return True

    return "data" in data and "code" not in data and "error_code" not in data
