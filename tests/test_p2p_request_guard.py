import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from config import Config
from services import p2p_request_guard
from services.p2p_detail_cache import PersistedDetailBatch


class P2PRequestGuardTests(unittest.TestCase):
    def setUp(self):
        p2p_request_guard._cache.clear()
        p2p_request_guard._cache_locks.clear()

    def tearDown(self):
        p2p_request_guard._cache.clear()
        p2p_request_guard._cache_locks.clear()

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


if __name__ == "__main__":
    unittest.main()
