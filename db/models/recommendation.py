from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class P2POrderDetailCache(Base):
    __tablename__ = "p2p_order_detail_cache"
    __table_args__ = (
        UniqueConstraint(
            "exchange_code",
            "exchange_offer_id",
            name="uq_p2p_order_detail_exchange_offer",
        ),
        Index(
            "ix_p2p_order_detail_refresh",
            "exchange_code",
            "next_refresh_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exchange_code: Mapped[str] = mapped_column(String(30), index=True)
    exchange_offer_id: Mapped[str] = mapped_column(String(100), index=True)
    detail_payload: Mapped[dict] = mapped_column(JSON)
    detail_hash: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    next_refresh_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class P2PMacroAnalysis(Base):
    __tablename__ = "p2p_macro_analyses"
    __table_args__ = (
        Index(
            "ix_p2p_macro_analysis_lookup",
            "fiat_currency_id",
            "valid_until",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fiat_currency_id: Mapped[int] = mapped_column(
        ForeignKey("fiat_currencies.id", ondelete="CASCADE"),
        index=True,
    )
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    impact_score: Mapped[Decimal] = mapped_column(Numeric(6, 5), default=0)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    factors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    valid_until: Mapped[datetime] = mapped_column(DateTime, index=True)


class P2PMarketRecommendation(Base):
    __tablename__ = "p2p_market_recommendations"
    __table_args__ = (
        Index(
            "ix_p2p_recommendation_market_lookup",
            "exchange_id",
            "crypto_currency_id",
            "fiat_currency_id",
            "action",
            "observed_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
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
    macro_analysis_id: Mapped[int | None] = mapped_column(
        ForeignKey("p2p_macro_analyses.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(10), index=True)
    buy_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    sell_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    score: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    summary: Mapped[str] = mapped_column(Text, default="")
    reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    risks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    feature_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    filter_hash: Mapped[str] = mapped_column(String(64), default="default")
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)


class P2PRecommendationDelivery(Base):
    __tablename__ = "p2p_recommendation_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "recommendation_id",
            "user_id",
            name="uq_p2p_recommendation_delivery_user",
        ),
        Index(
            "ix_p2p_recommendation_delivery_lookup",
            "user_id",
            "status",
            "sent_at",
        ),
        Index(
            "ix_p2p_recommendation_delivery_month",
            "user_id",
            "status",
            "responded_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("p2p_market_recommendations.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    suggested_payment_method_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="SET NULL"),
        nullable=True,
    )
    selected_payment_method_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        index=True,
    )
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
