import unittest
from unittest.mock import AsyncMock, patch

from services.p2p_description_filter import filter_orders_by_description_until


class ProgressiveDescriptionFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_batch_does_not_fetch_more_than_requested(self):
        orders = [{"id": str(index)} for index in range(100)]
        prepare_batch = AsyncMock()

        with patch(
            "services.p2p_description_filter.filter_orders_by_description",
            new=AsyncMock(side_effect=lambda batch, *_args, **_kwargs: batch),
        ):
            selected = await filter_orders_by_description_until(
                orders,
                "binance",
                object(),
                limit=20,
                prepare_batch=prepare_batch,
            )

        self.assertEqual(selected, orders[:20])
        prepare_batch.assert_awaited_once_with(orders[:20])

    async def test_next_batch_only_covers_remaining_candidates(self):
        orders = [{"id": str(index)} for index in range(100)]
        prepare_batch = AsyncMock()
        filter_call = 0

        async def filter_batch(batch, *_args, **_kwargs):
            nonlocal filter_call
            filter_call += 1
            return batch[:15] if filter_call == 1 else batch[:5]

        with patch(
            "services.p2p_description_filter.filter_orders_by_description",
            side_effect=filter_batch,
        ):
            selected = await filter_orders_by_description_until(
                orders,
                "binance",
                object(),
                limit=20,
                prepare_batch=prepare_batch,
            )

        self.assertEqual(len(selected), 20)
        self.assertEqual(
            [len(call.args[0]) for call in prepare_batch.await_args_list],
            [20, 10],
        )


if __name__ == "__main__":
    unittest.main()
