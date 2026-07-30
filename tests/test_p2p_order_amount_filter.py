import unittest
from decimal import Decimal
from types import SimpleNamespace

from db.dto import P2PFilterSettings
from db.models import GlobalStatisticsSettings
from services.p2p_filters import (
    apply_settings_to_model,
    filter_orders,
    has_advertising_terms,
    settings_from_model,
)
from services.p2p_description_filter import filter_orders_by_description
from services.p2p_statistics_service import (
    build_statistics_filter_hash,
    build_statistics_filter_payload,
)
from services.statistics_settings_service import (
    parse_optional_amount,
    validate_order_amount_range,
)


def build_binance_order(
    *,
    min_amount: str = "1000",
    max_amount: str = "700000",
    description: str | None = None,
) -> dict:
    return {
        "adv": {
            "advNo": "test-order",
            "minSingleTransAmount": min_amount,
            "dynamicMaxSingleTransAmount": max_amount,
            "tradeMethods": [],
        },
        "advertiser": {},
        "_order_description": description,
    }


class P2POrderAmountFilterTests(unittest.TestCase):
    def test_rejects_order_whose_minimum_exceeds_configured_maximum(self):
        settings = P2PFilterSettings(max_order_amount=100_000)
        order = build_binance_order(min_amount="700000", max_amount="900000")

        result = filter_orders(
            [order],
            "binance",
            settings,
            apply_description_filters=False,
            apply_payment_filters=False,
        )

        self.assertEqual(result, [])

    def test_keeps_order_when_available_range_overlaps_configured_range(self):
        settings = P2PFilterSettings(
            min_order_amount=10_000,
            max_order_amount=100_000,
        )
        order = build_binance_order(min_amount="1000", max_amount="700000")

        result = filter_orders(
            [order],
            "binance",
            settings,
            apply_description_filters=False,
            apply_payment_filters=False,
        )

        self.assertEqual(result, [order])

    def test_rejects_order_whose_maximum_is_below_configured_minimum(self):
        settings = P2PFilterSettings(min_order_amount=50_000)
        order = build_binance_order(min_amount="1000", max_amount="40000")

        result = filter_orders(
            [order],
            "binance",
            settings,
            apply_description_filters=False,
            apply_payment_filters=False,
        )

        self.assertEqual(result, [])

    def test_amount_parser_accepts_spaces_and_decimal_comma(self):
        self.assertEqual(parse_optional_amount("100 000,50"), 100_000.5)
        self.assertIsNone(parse_optional_amount("скинути"))

    def test_rejects_inverted_amount_range(self):
        settings = P2PFilterSettings(
            min_order_amount=200_000,
            max_order_amount=100_000,
        )

        with self.assertRaises(ValueError):
            validate_order_amount_range(settings)

    def test_amount_range_changes_statistics_filter_hash(self):
        pair = SimpleNamespace(
            crypto_code="USDT",
            fiat_code="UAH",
        )
        default_hash = build_statistics_filter_hash(
            exchange_code="BINANCE",
            pair=pair,
            side="SELL",
            settings=P2PFilterSettings(),
        )
        ranged_hash = build_statistics_filter_hash(
            exchange_code="BINANCE",
            pair=pair,
            side="SELL",
            settings=P2PFilterSettings(max_order_amount=100_000),
        )

        self.assertNotEqual(default_hash, ranged_hash)

    def test_unset_amount_range_keeps_legacy_filter_payload(self):
        payload = build_statistics_filter_payload(
            exchange_code="BINANCE",
            pair=SimpleNamespace(crypto_code="USDT", fiat_code="UAH"),
            side="SELL",
            settings=P2PFilterSettings(),
            payment_methods=[],
        )

        self.assertNotIn("min_order_amount", payload)
        self.assertNotIn("max_order_amount", payload)

    def test_global_statistics_model_round_trips_amount_range(self):
        model = GlobalStatisticsSettings(
            id=1,
            min_order_amount=Decimal("10000.00"),
            max_order_amount=Decimal("100000.00"),
        )

        settings = settings_from_model(model)
        self.assertEqual(settings.min_order_amount, 10_000)
        self.assertEqual(settings.max_order_amount, 100_000)

        settings.min_order_amount = 20_000
        settings.max_order_amount = 80_000
        apply_settings_to_model(model, settings)

        self.assertEqual(model.min_order_amount, Decimal("20000"))
        self.assertEqual(model.max_order_amount, Decimal("80000"))


class P2PAdvertisingFilterTests(unittest.IsolatedAsyncioTestCase):
    AD_DESCRIPTION = (
        "У кого есть аккаунт на Бинанс, есть предложение по сотрудничеству. "
        "Отпишите в тлгрм - RcaSwаp"
    )

    def test_detects_cooperation_telegram_advertisement(self):
        self.assertTrue(has_advertising_terms(self.AD_DESCRIPTION))

    def test_advertisement_is_hard_blocked_even_without_configurable_filters(self):
        order = build_binance_order(description=self.AD_DESCRIPTION)

        result = filter_orders(
            [order],
            "binance",
            P2PFilterSettings(),
            apply_description_filters=False,
            apply_payment_filters=False,
        )

        self.assertEqual(result, [])

    async def test_advertisement_is_blocked_by_description_pipeline(self):
        order = build_binance_order(description=self.AD_DESCRIPTION)

        result = await filter_orders_by_description(
            [order],
            "binance",
            P2PFilterSettings(),
        )

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
