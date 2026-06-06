from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import Config


def display_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(get_display_timezone())


def get_display_timezone():
    try:
        return ZoneInfo(Config.DISPLAY_TIMEZONE)
    except ZoneInfoNotFoundError:
        return parse_utc_offset(Config.DISPLAY_UTC_OFFSET)


def parse_utc_offset(value: str):
    text = str(value or "+00:00").strip()
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")

    try:
        hours_text, minutes_text = text.split(":", 1)
        hours = int(hours_text)
        minutes = int(minutes_text)
    except (TypeError, ValueError):
        return UTC

    return timezone(sign * timedelta(hours=hours, minutes=minutes))
