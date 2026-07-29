import asyncio
import logging
import random

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
from services.time_utils import utc_now_naive as utc_now
from tasks.statistics_scanner import run_global_statistics_scan_with_result


logger = logging.getLogger(__name__)


async def run_p2p_market_monitor(bot: Bot):
    await asyncio.sleep(next_interval_seconds())

    while True:
        next_interval = next_interval_seconds()

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

            if (
                scan_result.skipped_reason
                and scan_result.skipped_reason != "disabled"
            ):
                await notify_admins(
                    "P2P-монітор не виконав сканування",
                    (
                        f"Причина: {format_scan_skip_reason(scan_result.skipped_reason)}\n"
                        f"Наступна спроба через {format_minutes(next_interval)} хв."
                    ),
                    key=(
                        "p2p_recommendation_monitor_skipped:"
                        f"{scan_result.skipped_reason}"
                    ),
                )

            if recommendation_pair_ids and not scan_result.skipped_reason:
                async with AsyncSessionLocal() as session:
                    recommendations = await P2PRecommendationService(
                        session,
                        latest_scan_cutoff=scan_started_at,
                    ).generate_recommendations(
                        pair_ids=recommendation_pair_ids,
                    )

                await deliver_market_recommendations(
                    bot,
                    recommendations,
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


def next_interval_seconds() -> int:
    minimum = min_recommendation_interval_seconds()
    maximum = max(minimum, int(Config.P2P_RECOMMENDATION_MAX_INTERVAL_SECONDS))
    return random.randint(minimum, maximum)


def min_recommendation_interval_seconds() -> int:
    return max(60, int(Config.P2P_RECOMMENDATION_MIN_INTERVAL_SECONDS))


def format_scan_skip_reason(reason: str) -> str:
    labels = {
        "no_currencies": "не налаштовано валютні пари",
        "no_exchanges": "не обрано жодної біржі",
        "no_directions": "не обрано жодного напрямку",
    }
    return labels.get(reason, reason)


def format_minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f}".rstrip("0").rstrip(".")
