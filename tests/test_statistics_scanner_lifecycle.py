import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import tasks.statistics_scanner as scanner
from tasks.statistics_scanner import GlobalStatisticsScanResult


class StatisticsScannerLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await scanner.cancel_scheduled_global_statistics_scan()

    async def test_storage_maintenance_runs_before_every_scan(self):
        expected = GlobalStatisticsScanResult(scans_attempted=4)

        with (
            patch.object(
                scanner,
                "run_p2p_storage_maintenance",
                new=AsyncMock(),
            ) as maintenance,
            patch.object(
                scanner,
                "_run_global_statistics_scan_once",
                new=AsyncMock(return_value=expected),
            ) as scan,
        ):
            result = await scanner.run_global_statistics_scan_with_result()

        self.assertEqual(result, expected)
        maintenance.assert_awaited_once_with()
        scan.assert_awaited_once_with()

    async def test_manual_scan_cannot_be_queued_more_than_once(self):
        started = asyncio.Event()
        release = asyncio.Event()

        async def run_scan():
            started.set()
            await release.wait()
            return GlobalStatisticsScanResult()

        with patch.object(
            scanner,
            "run_global_statistics_scan_once",
            side_effect=run_scan,
        ) as run:
            self.assertTrue(scanner.schedule_global_statistics_scan())
            await started.wait()
            self.assertFalse(scanner.schedule_global_statistics_scan())
            release.set()
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        run.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
