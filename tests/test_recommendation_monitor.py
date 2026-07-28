import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from config import Config
from tasks.recommendation_monitor import (
    build_success_report,
    next_interval_seconds,
    run_p2p_market_monitor,
)
from tasks.statistics_scanner import GlobalStatisticsScanResult


class MarketMonitorLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_cycle_runs_global_statistics_scan(self):
        sleep_mock = AsyncMock(
            side_effect=[None, asyncio.CancelledError()],
        )
        scan_mock = AsyncMock(
            return_value=GlobalStatisticsScanResult(),
        )

        with (
            patch(
                "tasks.recommendation_monitor.asyncio.sleep",
                new=sleep_mock,
            ),
            patch(
                "tasks.recommendation_monitor.get_enabled_recommendation_pair_ids",
                new=AsyncMock(return_value=set()),
            ),
            patch(
                "tasks.recommendation_monitor.run_global_statistics_scan_with_result",
                new=scan_mock,
            ),
            patch(
                "tasks.recommendation_monitor.can_call_openai",
                return_value=False,
            ),
            patch.object(
                Config,
                "P2P_RECOMMENDATION_MONITOR_SUCCESS_ALERTS_ENABLED",
                False,
            ),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await run_p2p_market_monitor(AsyncMock())

        scan_mock.assert_awaited_once_with()

    async def test_user_pairs_do_not_force_or_parameterize_statistics_scan(self):
        sleep_mock = AsyncMock(
            side_effect=[None, asyncio.CancelledError()],
        )
        scan_mock = AsyncMock(
            return_value=GlobalStatisticsScanResult(
                skipped_reason="disabled",
            ),
        )

        with (
            patch(
                "tasks.recommendation_monitor.asyncio.sleep",
                new=sleep_mock,
            ),
            patch(
                "tasks.recommendation_monitor.get_enabled_recommendation_pair_ids",
                new=AsyncMock(return_value={(1, 2), (3, 4)}),
            ),
            patch(
                "tasks.recommendation_monitor.run_global_statistics_scan_with_result",
                new=scan_mock,
            ),
            patch(
                "tasks.recommendation_monitor.can_call_openai",
                return_value=True,
            ),
            patch.object(
                Config,
                "P2P_RECOMMENDATION_MONITOR_SUCCESS_ALERTS_ENABLED",
                False,
            ),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await run_p2p_market_monitor(AsyncMock())

        scan_mock.assert_awaited_once_with()


class RecommendationMonitorTests(unittest.TestCase):

    def test_random_interval_stays_inside_configured_bounds(self):
        with (
            patch.object(Config, "P2P_RECOMMENDATION_MIN_INTERVAL_SECONDS", 360),
            patch.object(Config, "P2P_RECOMMENDATION_MAX_INTERVAL_SECONDS", 720),
        ):
            values = [next_interval_seconds() for _ in range(100)]

        self.assertTrue(all(360 <= value <= 720 for value in values))

    def test_success_report_contains_operational_counts(self):
        report = build_success_report(
            pair_count=2,
            scans_attempted=8,
            scans_with_orders=7,
            saved_orders=140,
            recommendation_count=1,
            sent_count=1,
            elapsed_seconds=12.34,
            next_interval=480,
            skipped_reason=None,
        )

        self.assertIn("Цикл успішно завершено", report)
        self.assertIn("Перевірено напрямків: 8", report)
        self.assertIn("Збережено ордерів: 140", report)
        self.assertIn("Наступний запуск: через 8 хв", report)


if __name__ == "__main__":
    unittest.main()
