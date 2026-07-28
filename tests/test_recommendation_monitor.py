import unittest
from unittest.mock import patch

from config import Config
from tasks.recommendation_monitor import (
    build_success_report,
    next_interval_seconds,
)


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
