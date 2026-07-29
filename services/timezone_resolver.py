import logging
from functools import lru_cache


logger = logging.getLogger(__name__)


def resolve_timezone_from_coordinates(
    latitude: float | None,
    longitude: float | None,
) -> str | None:
    if latitude is None or longitude is None:
        return None

    try:
        finder = get_timezone_finder()
    except ImportError:
        logger.warning("timezonefinder is not installed; user timezone was not resolved")
        return None
    except Exception:
        logger.exception("Failed to initialize timezonefinder")
        return None

    try:
        timezone_name = finder.timezone_at(lat=latitude, lng=longitude)

        if not timezone_name and hasattr(finder, "closest_timezone_at"):
            timezone_name = finder.closest_timezone_at(lat=latitude, lng=longitude)

        return timezone_name
    except Exception:
        logger.exception(
            "Failed to resolve timezone from coordinates: lat=%s lon=%s",
            latitude,
            longitude,
        )
        return None


@lru_cache(maxsize=1)
def get_timezone_finder():
    from timezonefinder import TimezoneFinder

    return TimezoneFinder(in_memory=False)
