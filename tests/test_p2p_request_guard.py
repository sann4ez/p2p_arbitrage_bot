import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from config import Config
from services import p2p_request_guard
from services.p2p_detail_cache import PersistedDetailBatch


class P2PRequestGuardTests(unittest.TestCase):
    def setUp(self):
        p2p_request_guard._guard_lock = asyncio.Lock()
        p2p_request_guard._cache.clear()
        p2p_request_guard._cache_locks.clear()

    def tearDown(self):
        p2p_request_guard._cache.clear()
        p2p_request_guard._cache_locks.clear()
        p2p_request_guard._guard_lock = asyncio.Lock()

    def test_overlapping_detail_requests_fetch_each_order_only_once(self):
        fetch_calls = []

        async def run_test():
            first_fetch_started = asyncio.Event()
            release_first_fetch = asyncio.Event()

            async def fetcher(item_ids):
                fetch_calls.append(list(item_ids))

                if len(fetch_calls) == 1:
                    first_fetch_started.set()
                    await release_first_fetch.wait()

                return {
                    item_id: {"description": f"detail-{item_id}"}
                    for item_id in item_ids
                }

            first_task = asyncio.create_task(
                p2p_request_guard.get_cached_p2p_details(
                    exchange="binance",
                    item_ids=["1", "2"],
                    fetcher=fetcher,
                )
            )
            await first_fetch_started.wait()
            second_task = asyncio.create_task(
                p2p_request_guard.get_cached_p2p_details(
                    exchange="binance",
                    item_ids=["2", "3"],
                    fetcher=fetcher,
                )
            )
            await asyncio.sleep(0)
            release_first_fetch.set()
            return await asyncio.gather(first_task, second_task)

        empty_persisted = PersistedDetailBatch(fresh={}, stale={})

        with (
            patch(
                "services.p2p_request_guard.load_persisted_p2p_details",
                new=AsyncMock(return_value=empty_persisted),
            ),
            patch(
                "services.p2p_request_guard.store_persisted_p2p_details",
                new=AsyncMock(),
            ),
            patch(
                "services.p2p_request_guard.defer_persisted_p2p_detail_refresh",
                new=AsyncMock(),
            ),
            patch(
                "services.p2p_request_guard.wait_for_global_cooldown",
                new=AsyncMock(),
            ),
        ):
            first, second = asyncio.run(run_test())

        self.assertEqual(fetch_calls, [["1", "2"], ["3"]])
        self.assertEqual(set(first), {"1", "2"})
        self.assertEqual(set(second), {"2", "3"})

    def test_persisted_details_respect_memory_cache_limit_immediately(self):
        persisted = PersistedDetailBatch(
            fresh={
                "1": {"description": "first"},
                "2": {"description": "second"},
                "3": {"description": "third"},
            },
            stale={},
        )
        fetcher = AsyncMock(return_value={})

        with (
            patch.object(Config, "P2P_CACHE_MAX_ENTRIES", 2),
            patch(
                "services.p2p_request_guard.load_persisted_p2p_details",
                new=AsyncMock(return_value=persisted),
            ),
        ):
            details = asyncio.run(
                p2p_request_guard.get_cached_p2p_details(
                    exchange="binance",
                    item_ids=["1", "2", "3"],
                    fetcher=fetcher,
                )
            )

        self.assertEqual(3, len(details))
        self.assertLessEqual(len(p2p_request_guard._cache), 2)
        fetcher.assert_not_awaited()

    def test_stale_detail_is_used_when_refresh_returns_nothing(self):
        persisted = PersistedDetailBatch(
            fresh={},
            stale={"1": {"description": "stale"}},
        )
        fetcher = AsyncMock(return_value={})

        with (
            patch(
                "services.p2p_request_guard.load_persisted_p2p_details",
                new=AsyncMock(return_value=persisted),
            ),
            patch(
                "services.p2p_request_guard.store_persisted_p2p_details",
                new=AsyncMock(),
            ),
            patch(
                "services.p2p_request_guard.defer_persisted_p2p_detail_refresh",
                new=AsyncMock(),
            ),
            patch(
                "services.p2p_request_guard.wait_for_global_cooldown",
                new=AsyncMock(),
            ),
        ):
            details = asyncio.run(
                p2p_request_guard.get_cached_p2p_details(
                    exchange="binance",
                    item_ids=["1"],
                    fetcher=fetcher,
                )
            )

        self.assertEqual(details["1"], {"description": "stale"})
        fetcher.assert_awaited_once_with(["1"])

    def test_force_refresh_replaces_cached_order_list(self):
        fetcher = AsyncMock(
            side_effect=[
                [{"id": "old"}],
                [{"id": "fresh"}],
            ]
        )

        async def run_test():
            first = await p2p_request_guard.get_cached_p2p_orders(
                exchange="binance",
                direction="SELL",
                rows=20,
                pair_key="USDT/UAH",
                fetcher=fetcher,
            )
            refreshed = await p2p_request_guard.get_cached_p2p_orders(
                exchange="binance",
                direction="SELL",
                rows=20,
                pair_key="USDT/UAH",
                fetcher=fetcher,
                force_refresh=True,
            )
            cached = await p2p_request_guard.get_cached_p2p_orders(
                exchange="binance",
                direction="SELL",
                rows=20,
                pair_key="USDT/UAH",
                fetcher=fetcher,
            )
            return first, refreshed, cached

        with patch(
            "services.p2p_request_guard.wait_for_global_cooldown",
            new=AsyncMock(),
        ):
            first, refreshed, cached = asyncio.run(run_test())

        self.assertEqual([{"id": "old"}], first)
        self.assertEqual([{"id": "fresh"}], refreshed)
        self.assertEqual([{"id": "fresh"}], cached)
        self.assertEqual(2, fetcher.await_count)


if __name__ == "__main__":
    unittest.main()
