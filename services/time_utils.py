from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import Config


def display_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(get_display_timezone())


def display_today() -> date:
    return datetime.now(get_display_timezone()).date()


def display_date_to_utc_naive_range(value: date) -> tuple[datetime, datetime]:
    timezone_info = get_display_timezone()
    started_at = datetime.combine(value, time.min, tzinfo=timezone_info)
    ended_at = started_at + timedelta(days=1)

    return (
        started_at.astimezone(UTC).replace(tzinfo=None),
        ended_at.astimezone(UTC).replace(tzinfo=None),
    )


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
