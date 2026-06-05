from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from db.dto import P2PUserPair
from services.binance_client import fetch_binance_p2p, fetch_binance_p2p_details
from services.okx_client import fetch_okx_p2p, fetch_okx_p2p_details
from services.okx_order_payload import get_okx_order_id
from services.p2p_order_formatter import (
    attach_binance_details,
    attach_okx_details,
    build_binance_order_blocks,
    build_binance_order_urls,
    build_okx_order_blocks,
    build_okx_order_urls,
    count_binance_descriptions,
    count_okx_descriptions,
)


P2P_DIRECTION_FIAT_TO_CRYPTO = "fiat_crypto"
P2P_DIRECTION_CRYPTO_TO_FIAT = "crypto_fiat"

OrderFetcher = Callable[[str, P2PUserPair, int], Awaitable[list[dict]]]
DetailFetcher = Callable[[list[object], str, P2PUserPair], Awaitable[dict[str, dict]]]
OrderIdGetter = Callable[[dict], object | None]
DetailsAttacher = Callable[[list[dict], dict[str, dict]], None]
DescriptionCounter = Callable[[list[dict]], int]
BlockBuilder = Callable[[list[dict], str, P2PUserPair], list[str]]
UrlBuilder = Callable[[list[dict], str, P2PUserPair], list[str | None]]


@dataclass(frozen=True)
class P2PExchangeDriver:
    exchange: str
    exchange_code: str
    display_name: str
    fiat_to_crypto_side: str
    crypto_to_fiat_side: str
    fetch_orders: OrderFetcher
    fetch_details: DetailFetcher
    get_order_id: OrderIdGetter
    attach_details: DetailsAttacher
    count_descriptions: DescriptionCounter
    build_order_blocks: BlockBuilder
    build_order_urls: UrlBuilder

    def side_for_direction(self, direction: str) -> str:
        if direction == P2P_DIRECTION_FIAT_TO_CRYPTO:
            return self.fiat_to_crypto_side

        if direction == P2P_DIRECTION_CRYPTO_TO_FIAT:
            return self.crypto_to_fiat_side

        raise ValueError(f"Unsupported P2P direction: {direction}")

    def title_for_direction(self, direction: str, pair: P2PUserPair) -> str:
        action = (
            "Купівля"
            if direction == P2P_DIRECTION_FIAT_TO_CRYPTO
            else "Продаж"
        )

        return f"{self.display_name} P2P | {action} {pair.crypto_code} за {pair.fiat_code}"


async def _fetch_binance_orders(
    side: str,
    pair: P2PUserPair,
    rows: int,
) -> list[dict]:
    return await fetch_binance_p2p(
        trade_type=side,
        asset=pair.crypto_code,
        fiat=pair.fiat_code,
        rows=rows,
    )


async def _fetch_binance_details(
    item_ids: list[object],
    side: str,
    pair: P2PUserPair,
) -> dict[str, dict]:
    return await fetch_binance_p2p_details(item_ids)


def _get_binance_order_id(order: dict) -> object | None:
    return order.get("adv", {}).get("advNo")


def _build_binance_blocks(
    orders: list[dict],
    side: str,
    pair: P2PUserPair,
) -> list[str]:
    return build_binance_order_blocks(
        orders,
        asset=pair.crypto_code,
        fiat=pair.fiat_code,
    )


def _build_binance_urls(
    orders: list[dict],
    side: str,
    pair: P2PUserPair,
) -> list[str | None]:
    return build_binance_order_urls(orders)


async def _fetch_okx_orders(
    side: str,
    pair: P2PUserPair,
    rows: int,
) -> list[dict]:
    return await fetch_okx_p2p(
        side=side,
        asset=pair.crypto_code,
        fiat=pair.fiat_code,
        rows=rows,
    )


async def _fetch_okx_details(
    item_ids: list[object],
    side: str,
    pair: P2PUserPair,
) -> dict[str, dict]:
    return await fetch_okx_p2p_details(
        item_ids,
        side=side,
        asset=pair.crypto_code,
        fiat=pair.fiat_code,
    )


def _build_okx_blocks(
    orders: list[dict],
    side: str,
    pair: P2PUserPair,
) -> list[str]:
    return build_okx_order_blocks(
        orders,
        side,
        asset=pair.crypto_code,
        fiat=pair.fiat_code,
    )


def _build_okx_urls(
    orders: list[dict],
    side: str,
    pair: P2PUserPair,
) -> list[str | None]:
    return build_okx_order_urls(
        orders,
        side,
        asset=pair.crypto_code,
        fiat=pair.fiat_code,
    )


BINANCE_DRIVER = P2PExchangeDriver(
    exchange="binance",
    exchange_code="BINANCE",
    display_name="Binance",
    fiat_to_crypto_side="BUY",
    crypto_to_fiat_side="SELL",
    fetch_orders=_fetch_binance_orders,
    fetch_details=_fetch_binance_details,
    get_order_id=_get_binance_order_id,
    attach_details=attach_binance_details,
    count_descriptions=count_binance_descriptions,
    build_order_blocks=_build_binance_blocks,
    build_order_urls=_build_binance_urls,
)

OKX_DRIVER = P2PExchangeDriver(
    exchange="okx",
    exchange_code="OKX",
    display_name="OKX",
    fiat_to_crypto_side="sell",
    crypto_to_fiat_side="buy",
    fetch_orders=_fetch_okx_orders,
    fetch_details=_fetch_okx_details,
    get_order_id=get_okx_order_id,
    attach_details=attach_okx_details,
    count_descriptions=count_okx_descriptions,
    build_order_blocks=_build_okx_blocks,
    build_order_urls=_build_okx_urls,
)

P2P_EXCHANGE_DRIVERS = {
    BINANCE_DRIVER.exchange: BINANCE_DRIVER,
    BINANCE_DRIVER.exchange_code: BINANCE_DRIVER,
    OKX_DRIVER.exchange: OKX_DRIVER,
    OKX_DRIVER.exchange_code: OKX_DRIVER,
}


def get_p2p_exchange_driver(exchange: str) -> P2PExchangeDriver:
    driver = P2P_EXCHANGE_DRIVERS.get(str(exchange))

    if driver:
        return driver

    driver = P2P_EXCHANGE_DRIVERS.get(str(exchange).lower())

    if driver:
        return driver

    driver = P2P_EXCHANGE_DRIVERS.get(str(exchange).upper())

    if driver:
        return driver

    raise ValueError(f"Unsupported P2P exchange: {exchange}")
