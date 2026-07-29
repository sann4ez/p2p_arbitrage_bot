import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from services.p2p_detail_cache import cleanup_persisted_p2p_details
from services.p2p_statistics_chart import image_to_png_bytes
from services.timezone_resolver import get_timezone_finder


class FakeSession:
    def __init__(self, *, rowcount: int):
        self.execute = AsyncMock(
            return_value=SimpleNamespace(rowcount=rowcount),
        )
        self.commit = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class PersistentDetailCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_deletes_only_one_bounded_batch(self):
        session = FakeSession(rowcount=17)

        with patch(
            "services.p2p_detail_cache.AsyncSessionLocal",
            return_value=session,
        ):
            deleted = await cleanup_persisted_p2p_details(
                30,
                batch_size=1000,
            )

        self.assertEqual(deleted, 17)
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    async def test_cleanup_can_be_disabled(self):
        session_factory = Mock()

        with patch(
            "services.p2p_detail_cache.AsyncSessionLocal",
            session_factory,
        ):
            deleted = await cleanup_persisted_p2p_details(0)

        self.assertEqual(deleted, 0)
        session_factory.assert_not_called()


class ResourceReleaseTests(unittest.TestCase):
    def test_chart_image_is_closed_after_encoding(self):
        image = Mock()

        def save(buffer, **_kwargs):
            buffer.write(b"png-data")

        image.save.side_effect = save

        self.assertEqual(image_to_png_bytes(image), b"png-data")
        image.close.assert_called_once_with()

    def test_timezone_finder_uses_low_memory_mode(self):
        fake_module = ModuleType("timezonefinder")
        factory = Mock(return_value=object())
        fake_module.TimezoneFinder = factory
        get_timezone_finder.cache_clear()

        try:
            with patch.dict(sys.modules, {"timezonefinder": fake_module}):
                finder = get_timezone_finder()

            self.assertIsNotNone(finder)
            factory.assert_called_once_with(in_memory=False)
        finally:
            get_timezone_finder.cache_clear()


if __name__ == "__main__":
    unittest.main()
