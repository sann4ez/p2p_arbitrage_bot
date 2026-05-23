import asyncio

import aiohttp


OKX_P2P_URL = "https://www.okx.com/v3/c2c/tradingOrders/books"


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
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    }

    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.get(OKX_P2P_URL, params=params) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return []

    if data.get("code") != 0 and data.get("error_code") not in ("0", 0):
        return []

    orders = data.get("data", {}).get(side.lower(), [])

    return orders[:rows]
