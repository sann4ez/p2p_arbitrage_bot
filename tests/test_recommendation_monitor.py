import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from config import Config
from tasks.recommendation_monitor import (
    next_interval_seconds,
    run_p2p_market_monitor,
)
from tasks.statistics_scanner import GlobalStatisticsScanResult


class FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


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
            patch(
                "tasks.recommendation_monitor.notify_admins",
                new=AsyncMock(),
            ) as notify_admins,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await run_p2p_market_monitor(AsyncMock())

        scan_mock.assert_awaited_once_with()
        notify_admins.assert_not_awaited()

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
            patch(
                "tasks.recommendation_monitor.notify_admins",
                new=AsyncMock(),
            ) as notify_admins,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await run_p2p_market_monitor(AsyncMock())

        scan_mock.assert_awaited_once_with()
        notify_admins.assert_not_awaited()

    async def test_p2p_signals_are_still_delivered_without_success_alert(self):
        sleep_mock = AsyncMock(
            side_effect=[None, asyncio.CancelledError()],
        )
        recommendations = [object()]
        recommendation_service = Mock()
        recommendation_service.return_value.generate_recommendations = AsyncMock(
            return_value=recommendations,
        )
        delivery = AsyncMock(return_value=1)
        bot = AsyncMock()

        with (
            patch(
                "tasks.recommendation_monitor.asyncio.sleep",
                new=sleep_mock,
            ),
            patch(
                "tasks.recommendation_monitor.get_enabled_recommendation_pair_ids",
                new=AsyncMock(return_value={(1, 2)}),
            ),
            patch(
                "tasks.recommendation_monitor.run_global_statistics_scan_with_result",
                new=AsyncMock(
                    return_value=GlobalStatisticsScanResult(
                        scans_attempted=1,
                        scans_with_orders=1,
                        saved_orders=20,
                    )
                ),
            ),
            patch(
                "tasks.recommendation_monitor.can_call_openai",
                return_value=True,
            ),
            patch(
                "tasks.recommendation_monitor.AsyncSessionLocal",
                return_value=FakeSessionContext(),
            ),
            patch(
                "tasks.recommendation_monitor.P2PRecommendationService",
                recommendation_service,
            ),
            patch(
                "tasks.recommendation_monitor.deliver_market_recommendations",
                new=delivery,
            ),
            patch(
                "tasks.recommendation_monitor.notify_admins",
                new=AsyncMock(),
            ) as notify_admins,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await run_p2p_market_monitor(bot)

        delivery.assert_awaited_once_with(bot, recommendations)
        notify_admins.assert_not_awaited()

    async def test_failed_cycle_notifies_admins(self):
        sleep_mock = AsyncMock(
            side_effect=[None, asyncio.CancelledError()],
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
                new=AsyncMock(side_effect=RuntimeError("scan failed")),
            ),
            patch(
                "tasks.recommendation_monitor.can_call_openai",
                return_value=False,
            ),
            patch(
                "tasks.recommendation_monitor.notify_admins",
                new=AsyncMock(),
            ) as notify_admins,
            patch("tasks.recommendation_monitor.logger.exception"),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await run_p2p_market_monitor(AsyncMock())

        notify_admins.assert_awaited_once()

    async def test_invalid_scanner_configuration_notifies_admins(self):
        sleep_mock = AsyncMock(
            side_effect=[None, asyncio.CancelledError()],
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
                new=AsyncMock(
                    return_value=GlobalStatisticsScanResult(
                        skipped_reason="no_exchanges",
                    )
                ),
            ),
            patch(
                "tasks.recommendation_monitor.can_call_openai",
                return_value=False,
            ),
            patch(
                "tasks.recommendation_monitor.notify_admins",
                new=AsyncMock(),
            ) as notify_admins,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await run_p2p_market_monitor(AsyncMock())

        notify_admins.assert_awaited_once()


class RecommendationMonitorTests(unittest.TestCase):

    def test_random_interval_stays_inside_configured_bounds(self):
        with (
            patch.object(Config, "P2P_RECOMMENDATION_MIN_INTERVAL_SECONDS", 360),
            patch.object(Config, "P2P_RECOMMENDATION_MAX_INTERVAL_SECONDS", 720),
        ):
            values = [next_interval_seconds() for _ in range(100)]

        self.assertTrue(all(360 <= value <= 720 for value in values))


if __name__ == "__main__":
    unittest.main()
