from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class GlobalStatisticsSettings(Base):
    __tablename__ = "statistics_global_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    scan_binance: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    scan_okx: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    scan_buy: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    scan_sell: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    min_order_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    max_order_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    max_order_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_merchant_orders: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_merchant_rating: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    min_merchant_completion_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    allow_fop: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    allow_person: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    allow_other_payment_methods: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )
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
    allow_monobank_jar_payments: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )
    display_order_count: Mapped[int] = mapped_column(Integer, default=20, server_default="20")
    candidate_order_count: Mapped[int] = mapped_column(Integer, default=200, server_default="200")
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


class GlobalStatisticsPaymentMethod(Base):
    __tablename__ = "statistics_global_payment_methods"

    payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
