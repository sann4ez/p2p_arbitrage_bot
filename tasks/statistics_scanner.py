import asyncio
import logging

from db.base import AsyncSessionLocal
from db.dto import P2PUserPair
from services.p2p_filters import get_fetch_order_count
from services.p2p_scan_runner import fetch_filtered_p2p_orders
from services.p2p_statistics_service import (
    STAT_SCOPE_GLOBAL,
    build_statistics_filter_hash,
    record_p2p_scan_snapshot,
)
from services.statistics_settings_service import StatisticsSettingsService


logger = logging.getLogger(__name__)
DEFAULT_SCAN_INTERVAL_SECONDS = 3600


async def run_global_statistics_scheduler():
    while True:
        interval_seconds = DEFAULT_SCAN_INTERVAL_SECONDS

        try:
            interval_seconds = await run_global_statistics_scan_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Global P2P statistics scan failed")

        await asyncio.sleep(max(interval_seconds, 60))


async def run_global_statistics_scan_once() -> int:
    async with AsyncSessionLocal() as session:
        service = StatisticsSettingsService(session)
        settings_model = await service.get_or_create_settings()
        interval_seconds = settings_model.interval_seconds or DEFAULT_SCAN_INTERVAL_SECONDS

        if not settings_model.is_enabled:
            logger.info("Global P2P statistics scan skipped: disabled")
            return interval_seconds

        crypto_currencies = await service.list_crypto_currencies()
        fiat_currencies = await service.list_fiat_currencies()
        filter_settings = await service.get_filter_settings()
        exchange_codes = get_enabled_exchange_codes(settings_model)
        side_by_exchange = {
            exchange_code: get_enabled_sides(exchange_code, settings_model)
            for exchange_code in exchange_codes
        }

    if not crypto_currencies or not fiat_currencies:
        logger.info("Global P2P statistics scan skipped: no currencies")
        return interval_seconds

    fetch_rows = get_fetch_order_count(filter_settings)
    scan_count = 0
    saved_count = 0
    logger.info(
        "Global P2P statistics scan start: exchanges=%s crypto=%s fiat=%s fetch_rows=%s",
        exchange_codes,
        len(crypto_currencies),
        len(fiat_currencies),
        fetch_rows,
    )

    for crypto in crypto_currencies:
        for fiat in fiat_currencies:
            pair = P2PUserPair(
                crypto_currency_id=crypto.id,
                fiat_currency_id=fiat.id,
                crypto_code=crypto.code,
                fiat_code=fiat.code,
                is_selected=True,
            )
            payment_methods = await get_global_payment_methods_for_fiat(pair.fiat_code)

            for exchange_code in exchange_codes:
                for side in side_by_exchange[exchange_code]:
                    filter_hash = build_statistics_filter_hash(
                        exchange_code=exchange_code,
                        pair=pair,
                        side=side,
                        settings=filter_settings,
                        payment_methods=payment_methods,
                    )
                    orders = await fetch_filtered_p2p_orders(
                        exchange_code=exchange_code,
                        pair=pair,
                        side=side,
                        settings=filter_settings,
                        fetch_rows=fetch_rows,
                        payment_methods=payment_methods,
                    )
                    scan_count += 1

                    if not orders:
                        continue

                    saved_count += await record_p2p_scan_snapshot(
                        exchange_code=exchange_code,
                        pair=pair,
                        side=side,
                        orders=orders,
                        requested_rows=fetch_rows,
                        scope=STAT_SCOPE_GLOBAL,
                        filter_hash=filter_hash,
                    )

    logger.info(
        "Global P2P statistics scan done: scans=%s saved_orders=%s next_interval=%ss",
        scan_count,
        saved_count,
        interval_seconds,
    )
    return interval_seconds


async def get_global_payment_methods_for_fiat(fiat_code: str):
    async with AsyncSessionLocal() as session:
        return await StatisticsSettingsService(session).list_selected_methods_for_fiat_code(
            fiat_code,
        )


def get_enabled_exchange_codes(settings_model) -> list[str]:
    codes = []

    if settings_model.scan_binance:
        codes.append("BINANCE")

    if settings_model.scan_okx:
        codes.append("OKX")

    return codes


def get_enabled_sides(exchange_code: str, settings_model) -> list[str]:
    sides = []

    if exchange_code == "OKX":
        if settings_model.scan_buy:
            sides.append("sell")

        if settings_model.scan_sell:
            sides.append("buy")

        return sides

    if settings_model.scan_buy:
        sides.append("BUY")

    if settings_model.scan_sell:
        sides.append("SELL")

    return sides
