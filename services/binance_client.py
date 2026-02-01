import aiohttp

BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

async def fetch_binance_p2p(
    *,
    trade_type: str,
    asset: str = "USDT",
    fiat: str = "UAH",
    amount: float | None = None,
    rows: int = 5,
):
    payload = {
        "page": 1,
        "rows": rows,
        "asset": asset,
        "fiat": fiat,
        "tradeType": trade_type,  # BUY / SELL
        "payTypes": [],
        "publisherType": None,
    }

    if amount:
        payload["transAmount"] = str(amount)

    async with aiohttp.ClientSession() as session:
        async with session.post(BINANCE_P2P_URL, json=payload) as response:
            data = await response.json()
            return data.get("data", [])