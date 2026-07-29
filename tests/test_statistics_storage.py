import unittest
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from services.p2p_statistics_service import (
    P2PStatisticsService,
    build_binance_offer_model,
    build_okx_offer_model,
)


def build_reference_models(exchange_code: str):
    return (
        SimpleNamespace(id=1, code=exchange_code),
        SimpleNamespace(id=2, code="USDT"),
        SimpleNamespace(id=3, code="UAH"),
    )


class FakeStatisticsSession:
    def __init__(self):
        self.offers = []
        self.payment_links = []
        self.flush_count = 0

    def add_all(self, offers):
        self.offers.extend(offers)

    def add(self, model):
        self.payment_links.append(model)

    async def flush(self):
        self.flush_count += 1

        for index, offer in enumerate(self.offers, start=1):
            offer.id = index


class StatisticsStorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_hour_statistic_is_aggregated_by_postgresql(self):
        result = SimpleNamespace(
            one=lambda: SimpleNamespace(
                min_price=Decimal("44.10"),
                max_price=Decimal("44.90"),
                avg_price=Decimal("44.50"),
                median_price=Decimal("44.45"),
                offers_count=400,
                scans_count=2,
            )
        )
        session = SimpleNamespace(execute=AsyncMock(return_value=result))
        service = P2PStatisticsService(session)
        service.save_calculated_period_statistic = AsyncMock()
        started_at = datetime(2026, 7, 29, 12)
        ended_at = datetime(2026, 7, 29, 13)

        await service.recalculate_hour_period(
            exchange_id=1,
            crypto_currency_id=2,
            fiat_currency_id=3,
            side="SELL",
            scope="global",
            filter_hash="hash",
            period_type="hour",
            period_started_at=started_at,
            period_ended_at=ended_at,
        )

        service.save_calculated_period_statistic.assert_awaited_once_with(
            exchange_id=1,
            crypto_currency_id=2,
            fiat_currency_id=3,
            side="SELL",
            scope="global",
            filter_hash="hash",
            period_type="hour",
            period_started_at=started_at,
            period_ended_at=ended_at,
            min_price=Decimal("44.10"),
            max_price=Decimal("44.90"),
            avg_price=Decimal("44.50"),
            median_price=Decimal("44.45"),
            offers_count=400,
            scans_count=2,
        )

    async def test_offer_batch_uses_one_flush_and_does_not_store_raw_json(self):
        session = FakeStatisticsSession()
        service = P2PStatisticsService(session)
        service.payment_method_repo.list_by_fiat = AsyncMock(return_value=[])
        exchange, crypto, fiat = build_reference_models("BINANCE")
        orders = [
            {
                "adv": {
                    "advNo": "one",
                    "price": "44.10",
                    "tradeMethods": [],
                },
                "advertiser": {},
                "_detail": {"remarks": "large detail"},
            },
            {
                "adv": {
                    "advNo": "two",
                    "price": "44.20",
                    "tradeMethods": [],
                },
                "advertiser": {},
                "_detail": {"remarks": "another large detail"},
            },
        ]

        saved = await service.save_offers(
            scan_batch_id=1,
            exchange=exchange,
            crypto=crypto,
            fiat=fiat,
            side="sell",
            raw_side="SELL",
            orders=orders,
        )

        self.assertEqual(saved, 2)
        self.assertEqual(session.flush_count, 1)
        self.assertEqual(len(session.offers), 2)
        self.assertTrue(all(offer.raw_payload is None for offer in session.offers))

    def test_okx_offer_does_not_store_raw_json(self):
        exchange, crypto, fiat = build_reference_models("OKX")
        order = {
            "publicId": "order-one",
            "price": "44.10",
            "_detail": {"remark": "large detail"},
        }

        offer = build_okx_offer_model(
            scan_batch_id=1,
            exchange=exchange,
            crypto=crypto,
            fiat=fiat,
            side="buy",
            raw_side="buy",
            order=order,
            offer_id="order-one",
            price=Decimal("44.10"),
        )

        self.assertIsNone(offer.raw_payload)

    def test_binance_offer_does_not_store_raw_json(self):
        exchange, crypto, fiat = build_reference_models("BINANCE")
        order = {
            "adv": {"advNo": "order-one"},
            "advertiser": {},
            "_detail": {"remarks": "large detail"},
        }

        offer = build_binance_offer_model(
            scan_batch_id=1,
            exchange=exchange,
            crypto=crypto,
            fiat=fiat,
            side="sell",
            raw_side="SELL",
            order=order,
            offer_id="order-one",
            price=Decimal("44.10"),
        )

        self.assertIsNone(offer.raw_payload)


if __name__ == "__main__":
    unittest.main()
