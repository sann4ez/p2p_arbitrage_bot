import asyncio
import logging
import time

import aiohttp

from config import Config
from services.okx_order_payload import flatten_okx_detail

logger = logging.getLogger(__name__)

OKX_P2P_URL = "https://www.okx.com/v3/c2c/tradingOrders/books"
OKX_P2P_DETAIL_URL = "https://www.okx.com/v3/c2c/tradingOrders/{order_id}"
OKX_DETAIL_CONCURRENCY = 10
OKX_P2P_MARKET_URLS = {
    "sell": "https://www.okx.com/p2p-markets/uah/buy-usdt",
    "buy": "https://www.okx.com/p2p-markets/uah/sell-usdt",
}
OKX_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "App-Type": "web",
    "X-Locale": "uk_UA",
    "X-Utc": "2",
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


async def fetch_okx_p2p_details(
    order_ids: list[object],
    *,
    side: str | None = None,
) -> dict[str, dict]:
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
                    if side is None
                    else _fetch_okx_p2p_detail_limited(
                        session,
                        semaphore,
                        order_id,
                        side=side,
                    )
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
    *,
    side: str | None = None,
) -> tuple[str, dict]:
    async with semaphore:
        return await _fetch_okx_p2p_detail(session, order_id, side=side)


async def _fetch_okx_p2p_detail(
    session: aiohttp.ClientSession,
    order_id: str,
    *,
    side: str | None = None,
) -> tuple[str, dict]:
    referers = get_okx_detail_referers(order_id, side)
    last_status = None
    last_body = ""

    for referer in referers:
        request_timestamp = int(time.time() * 1000)
        headers = build_okx_detail_headers(referer, request_timestamp)

        try:
            async with session.get(
                OKX_P2P_DETAIL_URL.format(order_id=order_id),
                params={"t": request_timestamp},
                headers=headers,
            ) as response:
                last_status = response.status

                if response.status >= 400:
                    last_body = await response.text()
                    continue

                data = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            logger.warning(
                "OKX detail request failed: order_id=%s side=%s error=%s",
                order_id,
                side,
                type(error).__name__,
            )
            return order_id, {}

        detail = extract_okx_detail(data)

        if detail:
            return order_id, detail

    logger.warning(
        "OKX detail request returned empty detail: order_id=%s side=%s status=%s body=%s",
        order_id,
        side,
        last_status,
        last_body[:300],
    )

    return order_id, {}


def build_okx_detail_headers(referer: str, request_timestamp: int) -> dict[str, str]:
    headers = {
        "Origin": "https://www.okx.com",
        "Referer": referer,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Requested-With": "XMLHttpRequest",
        "X-Request-Timestamp": str(request_timestamp),
    }

    authorization = Config.OKX_AUTHORIZATION.strip()

    if authorization:
        headers["Authorization"] = authorization

    return headers


def get_okx_detail_referers(order_id: str, side: str | None = None) -> list[str]:
    sides = [side] if side in OKX_P2P_MARKET_URLS else ["sell", "buy"]
    referers = []

    for item in sides:
        base_url = OKX_P2P_MARKET_URLS[item]
        referers.append(f"{base_url}?id={order_id}")
        referers.append(base_url)

    return referers


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
