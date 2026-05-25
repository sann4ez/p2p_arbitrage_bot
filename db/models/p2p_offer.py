from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class P2POffer(Base):
    __tablename__ = "p2p_offers"
    __table_args__ = (
        UniqueConstraint(
            "scan_batch_id",
            "exchange_id",
            "exchange_offer_id",
            name="uq_p2p_offer_scan_exchange_offer",
        ),
        Index("ix_p2p_offers_pair_side", "crypto_currency_id", "fiat_currency_id", "side"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_batch_id: Mapped[int] = mapped_column(
        ForeignKey("scan_batches.id", ondelete="CASCADE"),
        index=True,
    )
    exchange_id: Mapped[int] = mapped_column(
        ForeignKey("exchanges.id", ondelete="CASCADE"),
        index=True,
    )
    crypto_currency_id: Mapped[int] = mapped_column(
        ForeignKey("crypto_currencies.id", ondelete="CASCADE"),
        index=True,
    )
    fiat_currency_id: Mapped[int] = mapped_column(
        ForeignKey("fiat_currencies.id", ondelete="CASCADE"),
        index=True,
    )

    exchange_offer_id: Mapped[str] = mapped_column(String(100), index=True)
    side: Mapped[str] = mapped_column(String(10), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    available_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    merchant_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    merchant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    merchant_orders: Mapped[int | None] = mapped_column(nullable=True)
    merchant_rating: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    merchant_completion_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    payment_time_minutes: Mapped[int | None] = mapped_column(nullable=True)

    order_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)


class P2POfferPaymentMethod(Base):
    __tablename__ = "p2p_offer_payment_methods"

    offer_id: Mapped[int] = mapped_column(
        ForeignKey("p2p_offers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="CASCADE"),
        primary_key=True,
    )
