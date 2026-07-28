import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from config import Config
from services.p2p_recommendation_service import merge_latest_scan_price
from services.p2p_recommendation_signals import (
    ACTION_BUY,
    ACTION_HOLD,
    ACTION_SELL,
    PricePoint,
    build_market_signal,
    calculate_side_metrics,
)


class P2PRecommendationSignalTests(unittest.TestCase):
    def test_low_buy_price_creates_buy_signal(self):
        buy_points = build_points([100 + index for index in range(30)] + [90])
        sell_points = build_points([110] * 31)

        signal = build_market_signal(
            buy_points,
            sell_points,
            min_history_points=24,
            signal_threshold=0.65,
        )

        self.assertEqual(ACTION_BUY, signal.action)
        self.assertEqual(Decimal("90"), signal.current_buy_price)
        self.assertGreater(signal.buy_score, signal.sell_score)

    def test_high_sell_price_creates_sell_signal(self):
        buy_points = build_points([100] * 31)
        sell_points = build_points([100 + index for index in range(30)] + [140])

        signal = build_market_signal(
            buy_points,
            sell_points,
            min_history_points=24,
            signal_threshold=0.65,
        )

        self.assertEqual(ACTION_SELL, signal.action)
        self.assertEqual(Decimal("140"), signal.current_sell_price)
        self.assertGreater(signal.sell_score, signal.buy_score)

    def test_insufficient_history_holds(self):
        signal = build_market_signal(
            build_points([100, 99]),
            build_points([101, 102]),
            min_history_points=24,
            signal_threshold=0.5,
        )

        self.assertEqual(ACTION_HOLD, signal.action)
        self.assertEqual(0.0, signal.score)

    def test_monthly_cycle_uses_completed_months(self):
        points = []

        for month in (1, 2, 3):
            for day in range(1, 29):
                if day <= 5:
                    price = 90
                elif 15 <= day <= 25:
                    price = 110
                else:
                    price = 100

                points.append(
                    PricePoint(
                        observed_at=datetime(2026, month, day, 12),
                        price=Decimal(str(price)),
                    )
                )

        points.append(
            PricePoint(
                observed_at=datetime(2026, 4, 2, 12),
                price=Decimal("95"),
            )
        )
        metrics = calculate_side_metrics(points)

        self.assertLess(metrics["monthly_cycle_percentile"], 0.35)

    def test_latest_scan_replaces_partial_hour_extreme(self):
        observed_at = (
            datetime.now(timezone.utc)
            .replace(tzinfo=None, second=0, microsecond=0)
        )
        hour_started_at = observed_at.replace(minute=0)
        points = [
            PricePoint(
                observed_at=hour_started_at - timedelta(hours=1),
                price=Decimal("100"),
            ),
            PricePoint(
                observed_at=hour_started_at,
                price=Decimal("90"),
            ),
        ]

        with patch.object(
            Config,
            "P2P_RECOMMENDATION_MAX_DATA_AGE_SECONDS",
            1800,
        ):
            merged, is_fresh = merge_latest_scan_price(
                points,
                (
                    observed_at,
                    Decimal("95"),
                    Decimal("105"),
                    "current-filter",
                ),
                prefer_min=True,
            )

        self.assertTrue(is_fresh)
        self.assertEqual(2, len(merged))
        self.assertEqual(Decimal("95"), merged[-1].price)


def build_points(values):
    started_at = datetime(2026, 1, 1)
    return [
        PricePoint(
            observed_at=started_at + timedelta(hours=index),
            price=Decimal(str(value)),
        )
        for index, value in enumerate(values)
    ]


if __name__ == "__main__":
    unittest.main()
