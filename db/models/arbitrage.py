from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ArbitrageOpportunity(Base):
    __tablename__ = "arbitrage_opportunities"
    __table_args__ = (
        UniqueConstraint(
            "buy_offer_id",
            "sell_offer_id",
            name="uq_arbitrage_buy_sell_offer",
        ),
        Index("ix_arbitrage_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    spread_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    spread_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    arbitrage_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default="new")

    buy_offer_id: Mapped[int] = mapped_column(
        ForeignKey("p2p_offers.id", ondelete="CASCADE"),
        index=True,
    )
    sell_offer_id: Mapped[int] = mapped_column(
        ForeignKey("p2p_offers.id", ondelete="CASCADE"),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UserSpreadAlert(Base):
    __tablename__ = "user_spread_alerts"
    __table_args__ = (
        UniqueConstraint("user_id", "arbitrage_id", name="uq_user_arbitrage_alert"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    arbitrage_id: Mapped[int] = mapped_column(
        ForeignKey("arbitrage_opportunities.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), default="sent")
    telegram_message_id: Mapped[int | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
