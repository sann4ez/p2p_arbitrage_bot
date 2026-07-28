import unittest
from datetime import datetime
from decimal import Decimal

from db.models import PaymentMethod
from services.p2p_recommendation_delivery import format_recommendation_message
from services.p2p_recommendation_service import RecommendationRecord


class P2PRecommendationDeliveryTests(unittest.TestCase):
    def test_message_is_html_safe_and_fits_telegram_limit(self):
        method = PaymentMethod(
            id=1,
            name="Bank <safe>",
            code="BANK",
            fiat_currency_id=1,
            is_active=True,
        )
        recommendation = RecommendationRecord(
            id=1,
            exchange_id=1,
            exchange_code="binance",
            crypto_currency_id=1,
            crypto_code="USDT",
            fiat_currency_id=1,
            fiat_code="UAH",
            action="BUY",
            buy_price=Decimal("44.123456"),
            sell_price=Decimal("44.900000"),
            score=0.8,
            confidence=0.8,
            summary="<" * 5000,
            reasons=("<reason>" * 200,) * 3,
            risks=("<risk>" * 200,) * 2,
            observed_at=datetime(2026, 1, 1),
        )

        text = format_recommendation_message(
            recommendation,
            method,
            has_available_bank=True,
        )

        self.assertLess(len(text), 4096)
        self.assertNotIn("<safe>", text)
        self.assertIn("&lt;safe&gt;", text)


if __name__ == "__main__":
    unittest.main()
