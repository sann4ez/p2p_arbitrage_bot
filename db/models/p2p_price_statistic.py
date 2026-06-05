from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class P2PPriceStatistic(Base):
    __tablename__ = "p2p_price_statistics"
    __table_args__ = (
        UniqueConstraint(
            "scope",
            "filter_hash",
            "exchange_id",
            "crypto_currency_id",
            "fiat_currency_id",
            "side",
            "period_type",
            "period_started_at",
            name="uq_p2p_price_stat_scope_period",
        ),
        Index(
            "ix_p2p_price_stats_lookup",
            "scope",
            "filter_hash",
            "period_type",
            "period_started_at",
            "exchange_id",
            "crypto_currency_id",
            "fiat_currency_id",
            "side",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(20), default="filter", index=True)
    filter_hash: Mapped[str] = mapped_column(String(64), default="default", index=True)
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
    side: Mapped[str] = mapped_column(String(10), index=True)
    period_type: Mapped[str] = mapped_column(String(20), index=True)
    period_started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    period_ended_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    min_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    max_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    avg_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    median_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    offers_count: Mapped[int] = mapped_column(default=0)
    scans_count: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
