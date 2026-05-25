from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_settings_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    arbitrage_mode: Mapped[str] = mapped_column(String(45), default="manual")
    spread_type: Mapped[str] = mapped_column(String(20), default="percent")
    spread_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    min_trade_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    max_trade_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    max_order_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_merchant_orders: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_merchant_rating: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    min_merchant_completion_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    allow_fop: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_person: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_other_payment_methods: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_third_party_payments: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )
    allow_split_payments: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )
    display_order_count: Mapped[int] = mapped_column(
        Integer,
        default=5,
        server_default="5",
    )
    candidate_order_count: Mapped[int] = mapped_column(
        Integer,
        default=20,
        server_default="20",
    )
    description_check_mode: Mapped[str] = mapped_column(
        String(20),
        default="regex",
        server_default="regex",
    )

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class UserExchange(Base):
    __tablename__ = "users_exchanges"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    exchange_id: Mapped[int] = mapped_column(
        ForeignKey("exchanges.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class UserPair(Base):
    __tablename__ = "users_pairs"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    crypto_currency_id: Mapped[int] = mapped_column(
        ForeignKey("crypto_currencies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    fiat_currency_id: Mapped[int] = mapped_column(
        ForeignKey("fiat_currencies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class UserPaymentMethod(Base):
    __tablename__ = "users_payment_methods"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
