from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ScanBatch(Base):
    __tablename__ = "scan_batches"
    __table_args__ = (
        Index(
            "ix_scan_batches_scope_status_started",
            "scope",
            "status",
            "started_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exchange_id: Mapped[int] = mapped_column(
        ForeignKey("exchanges.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scope: Mapped[str] = mapped_column(String(20), default="filter", index=True)
    filter_hash: Mapped[str] = mapped_column(String(64), default="default", index=True)
    status: Mapped[str] = mapped_column(String(30), default="running")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
