from sqlalchemy import BigInteger, String, Boolean, DateTime, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    telegram_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    location_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    location_message_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    location_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    is_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
