import asyncio

import aiohttp

BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
BINANCE_P2P_DETAIL_URL = "https://p2p.binance.com/bapi/c2c/v2/public/c2c/adv/detail"
BINANCE_MAX_ROWS_PER_REQUEST = 20
BINANCE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}


async def fetch_binance_p2p(
    *,
    trade_type: str,
    asset: str = "USDT",
    fiat: str = "UAH",
    amount: float | None = None,
    rows: int = 5,
):
    timeout = aiohttp.ClientTimeout(total=15)
    orders = []

    try:
        async with aiohttp.ClientSession(headers=BINANCE_HEADERS, timeout=timeout) as session:
            page = 1

            while len(orders) < rows:
                payload = {
                    "page": page,
                    "rows": min(BINANCE_MAX_ROWS_PER_REQUEST, rows - len(orders)),
                    "asset": asset,
                    "fiat": fiat,
                    "tradeType": trade_type,  # BUY / SELL
                    "payTypes": [],
                    "publisherType": None,
                }

                if amount:
                    payload["transAmount"] = str(amount)

                async with session.post(BINANCE_P2P_URL, json=payload) as response:
                    response.raise_for_status()
                    data = await response.json(content_type=None)

                page_orders = data.get("data")

                if not isinstance(page_orders, list) or not page_orders:
                    break

                orders.extend(page_orders)
                page += 1
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return []

    return orders[:rows]


async def fetch_binance_p2p_details(adv_nos: list[object]) -> dict[str, dict]:
    unique_adv_nos = []
    seen = set()

    for adv_no in adv_nos:
        if not adv_no:
            continue

        adv_no = str(adv_no)

        if adv_no in seen:
            continue

        unique_adv_nos.append(adv_no)
        seen.add(adv_no)

    if not unique_adv_nos:
        return {}

    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(headers=BINANCE_HEADERS, timeout=timeout) as session:
            results = await asyncio.gather(
                *(_fetch_binance_p2p_detail(session, adv_no) for adv_no in unique_adv_nos),
                return_exceptions=True,
            )
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return {}

    details = {}

    for result in results:
        if not isinstance(result, tuple):
            continue

        adv_no, detail = result

        if detail:
            details[adv_no] = detail

    return details


async def _fetch_binance_p2p_detail(
    session: aiohttp.ClientSession,
    adv_no: str,
) -> tuple[str, dict]:
    headers = {
        "Referer": f"https://p2p.binance.com/en/adv?code={adv_no}",
        "Origin": "https://p2p.binance.com",
    }

    try:
        async with session.get(
            BINANCE_P2P_DETAIL_URL,
            params={"advNo": adv_no},
            headers=headers,
        ) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return adv_no, {}

    if data.get("code") != "000000":
        return adv_no, {}

    detail = data.get("data")

    if not isinstance(detail, dict):
        return adv_no, {}

    return adv_no, detail
