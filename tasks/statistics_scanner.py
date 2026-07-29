import asyncio
import logging
from dataclasses import dataclass

from config import Config
from db.base import AsyncSessionLocal
from db.dto import P2PUserPair
from services.p2p_detail_cache import cleanup_persisted_p2p_details
from services.p2p_filters import get_fetch_order_count
from services.p2p_scan_runner import fetch_filtered_p2p_orders
from services.p2p_statistics_service import (
    STAT_SCOPE_GLOBAL,
    build_statistics_filter_hash,
    cleanup_raw_scan_history,
    record_p2p_scan_snapshot,
)
from services.statistics_settings_service import StatisticsSettingsService


logger = logging.getLogger(__name__)
_GLOBAL_SCAN_LOCK = asyncio.Lock()


@dataclass(frozen=True)
class GlobalStatisticsScanResult:
    scans_attempted: int = 0
    scans_with_orders: int = 0
    saved_orders: int = 0
    skipped_reason: str | None = None


_manual_scan_task: asyncio.Task[GlobalStatisticsScanResult] | None = None


async def run_global_statistics_scan_once() -> GlobalStatisticsScanResult:
    return await run_global_statistics_scan_with_result()


async def run_global_statistics_scan_with_result() -> GlobalStatisticsScanResult:
    async with _GLOBAL_SCAN_LOCK:
        await run_p2p_storage_maintenance()
        return await _run_global_statistics_scan_once()


def schedule_global_statistics_scan() -> bool:
    global _manual_scan_task

    if (
        _GLOBAL_SCAN_LOCK.locked()
        or (_manual_scan_task is not None and not _manual_scan_task.done())
    ):
        return False

    task = asyncio.create_task(
        run_global_statistics_scan_once(),
        name="manual-global-statistics-scan",
    )
    _manual_scan_task = task
    task.add_done_callback(_on_manual_scan_done)
    return True


async def cancel_scheduled_global_statistics_scan():
    global _manual_scan_task

    task = _manual_scan_task

    if task is None:
        return

    if not task.done():
        task.cancel()

    await asyncio.gather(task, return_exceptions=True)

    if _manual_scan_task is task:
        _manual_scan_task = None


def _on_manual_scan_done(task: asyncio.Task[GlobalStatisticsScanResult]):
    global _manual_scan_task

    if _manual_scan_task is task:
        _manual_scan_task = None

    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("Manual global statistics scan failed")


async def run_p2p_storage_maintenance():
    raw_deleted = await cleanup_raw_scan_history(
        Config.P2P_RAW_SCAN_RETENTION_HOURS
    )
    details_deleted = await cleanup_persisted_p2p_details(
        Config.P2P_DETAIL_CACHE_RETENTION_DAYS,
        batch_size=Config.P2P_DETAIL_CACHE_CLEANUP_BATCH_SIZE,
    )

    if raw_deleted or details_deleted:
        logger.debug(
            "P2P storage maintenance done: raw_batches=%s detail_rows=%s",
            raw_deleted,
            details_deleted,
        )


async def _run_global_statistics_scan_once() -> GlobalStatisticsScanResult:
    async with AsyncSessionLocal() as session:
        service = StatisticsSettingsService(session)
        settings_model = await service.get_or_create_settings()

        if not settings_model.is_enabled:
            logger.debug("Global P2P statistics scan skipped: disabled")
            return GlobalStatisticsScanResult(
                skipped_reason="disabled",
            )

        crypto_currencies = await service.list_crypto_currencies()
        fiat_currencies = await service.list_fiat_currencies()
        filter_settings = await service.get_filter_settings()
        exchange_codes = get_enabled_exchange_codes(settings_model)
        side_by_exchange = {
            exchange_code: get_enabled_sides(exchange_code, settings_model)
            for exchange_code in exchange_codes
        }

        if not crypto_currencies or not fiat_currencies:
            logger.debug("Global P2P statistics scan skipped: no currencies")
            return GlobalStatisticsScanResult(
                skipped_reason="no_currencies",
            )

        if not exchange_codes:
            logger.debug("Global P2P statistics scan skipped: no exchanges")
            return GlobalStatisticsScanResult(
                skipped_reason="no_exchanges",
            )

        if not any(side_by_exchange.values()):
            logger.debug("Global P2P statistics scan skipped: no directions")
            return GlobalStatisticsScanResult(
                skipped_reason="no_directions",
            )

        selected_payment_methods = await service.list_selected_payment_methods()
        payment_methods_by_fiat = {
            fiat.code: [
                method
                for method in selected_payment_methods
                if method.fiat_currency_id == fiat.id
            ]
            for fiat in fiat_currencies
        }

    fetch_rows = get_fetch_order_count(filter_settings)
    scan_count = 0
    scans_with_orders = 0
    saved_count = 0
    logger.debug(
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
            payment_methods = payment_methods_by_fiat.get(pair.fiat_code, [])

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
                        force_orders_refresh=True,
                    )
                    scan_count += 1

                    if not orders:
                        continue

                    scans_with_orders += 1
                    saved_count += await record_p2p_scan_snapshot(
                        exchange_code=exchange_code,
                        pair=pair,
                        side=side,
                        orders=orders,
                        requested_rows=fetch_rows,
                        scope=STAT_SCOPE_GLOBAL,
                        filter_hash=filter_hash,
                    )

    logger.debug(
        "Global P2P statistics scan done: scans=%s saved_orders=%s",
        scan_count,
        saved_count,
    )
    return GlobalStatisticsScanResult(
        scans_attempted=scan_count,
        scans_with_orders=scans_with_orders,
        saved_orders=saved_count,
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
