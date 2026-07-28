import asyncio
import logging
import random
import time
from datetime import datetime, timezone

from aiogram import Bot

from config import Config
from db.base import AsyncSessionLocal
from services.admin_notifier import notify_admins
from services.p2p_recommendation_delivery import (
    deliver_market_recommendations,
    get_enabled_recommendation_pair_ids,
)
from services.p2p_recommendation_ai import can_call_openai
from services.p2p_recommendation_service import P2PRecommendationService
from tasks.statistics_scanner import run_global_statistics_scan_with_result


logger = logging.getLogger(__name__)


async def run_p2p_market_monitor(bot: Bot):
    await asyncio.sleep(next_interval_seconds())

    while True:
        next_interval = next_interval_seconds()
        cycle_started_at = time.monotonic()

        try:
            pair_ids = await get_enabled_recommendation_pair_ids()
            openai_available = can_call_openai()
            recommendation_pair_ids = (
                pair_ids if pair_ids and openai_available else set()
            )

            if pair_ids and not openai_available:
                await notify_admins(
                    "AI-рекомендації не запущено",
                    (
                        "Для монітора P2P-рекомендацій не задано "
                        "OPENAI_API_KEY або OPENAI_RECOMMENDATION_MODEL.\n"
                        f"Наступна спроба через {format_minutes(next_interval)} хв."
                    ),
                    key="p2p_recommendation_openai_not_configured",
                    cooldown_seconds=0,
                )

            scan_started_at = utc_now()
            scan_result = await run_global_statistics_scan_with_result()

            recommendations = []
            sent_count = 0
            if recommendation_pair_ids and not scan_result.skipped_reason:
                async with AsyncSessionLocal() as session:
                    recommendations = await P2PRecommendationService(
                        session,
                        latest_scan_cutoff=scan_started_at,
                    ).generate_recommendations(
                        pair_ids=recommendation_pair_ids,
                    )

                sent_count = await deliver_market_recommendations(
                    bot,
                    recommendations,
                )

            if Config.P2P_RECOMMENDATION_MONITOR_SUCCESS_ALERTS_ENABLED:
                await notify_admins(
                    "Єдиний P2P-монітор завершено",
                    build_success_report(
                        pair_count=len(recommendation_pair_ids),
                        scans_attempted=scan_result.scans_attempted,
                        scans_with_orders=scan_result.scans_with_orders,
                        saved_orders=scan_result.saved_orders,
                        recommendation_count=len(recommendations),
                        sent_count=sent_count,
                        elapsed_seconds=(
                            time.monotonic() - cycle_started_at
                        ),
                        next_interval=next_interval,
                        skipped_reason=scan_result.skipped_reason,
                    ),
                    key="p2p_recommendation_monitor_success",
                    cooldown_seconds=0,
                )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.exception("Unified P2P market monitor failed")
            await notify_admins(
                "Помилка єдиного P2P-монітора",
                (
                    "Цикл статистики та рекомендацій завершився помилкою: "
                    f"{type(error).__name__}: {error}\n"
                    f"Наступна спроба через {format_minutes(next_interval)} хв."
                ),
                key="p2p_recommendation_monitor_failed",
                cooldown_seconds=0,
            )

        await asyncio.sleep(next_interval)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def next_interval_seconds() -> int:
    minimum = min_recommendation_interval_seconds()
    maximum = max(minimum, int(Config.P2P_RECOMMENDATION_MAX_INTERVAL_SECONDS))
    return random.randint(minimum, maximum)


def min_recommendation_interval_seconds() -> int:
    return max(60, int(Config.P2P_RECOMMENDATION_MIN_INTERVAL_SECONDS))


def build_success_report(
    *,
    pair_count: int,
    scans_attempted: int,
    scans_with_orders: int,
    saved_orders: int,
    recommendation_count: int,
    sent_count: int,
    elapsed_seconds: float,
    next_interval: int,
    skipped_reason: str | None,
) -> str:
    status = (
        f"Скан пропущено: {skipped_reason}."
        if skipped_reason
        else "Цикл успішно завершено."
    )
    return (
        f"{status}\n"
        f"Пар користувачів: {pair_count}\n"
        f"Перевірено напрямків: {scans_attempted}\n"
        f"Напрямків з ордерами: {scans_with_orders}\n"
        f"Збережено ордерів: {saved_orders}\n"
        f"Створено рекомендацій: {recommendation_count}\n"
        f"Доставлено користувачам: {sent_count}\n"
        f"Тривалість: {elapsed_seconds:.1f} с\n"
        f"Наступний запуск: через {format_minutes(next_interval)} хв."
    )


def format_minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f}".rstrip("0").rstrip(".")
