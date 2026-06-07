from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import Config


def display_datetime(value: datetime, timezone_name: str | None = None) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(get_display_timezone(timezone_name))


def display_today(timezone_name: str | None = None) -> date:
    return datetime.now(get_display_timezone(timezone_name)).date()


def display_date_to_utc_naive_range(
    value: date,
    timezone_name: str | None = None,
) -> tuple[datetime, datetime]:
    return display_dates_to_utc_naive_range(
        value,
        value + timedelta(days=1),
        timezone_name=timezone_name,
    )


def display_dates_to_utc_naive_range(
    started_on: date,
    ended_before: date,
    timezone_name: str | None = None,
) -> tuple[datetime, datetime]:
    timezone_info = get_display_timezone(timezone_name)
    started_at = datetime.combine(started_on, time.min, tzinfo=timezone_info)
    ended_at = datetime.combine(ended_before, time.min, tzinfo=timezone_info)

    return (
        started_at.astimezone(UTC).replace(tzinfo=None),
        ended_at.astimezone(UTC).replace(tzinfo=None),
    )


def get_display_timezone(timezone_name: str | None = None):
    if timezone_name:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            pass

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
