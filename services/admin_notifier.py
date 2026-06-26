import asyncio
import logging
import time
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select

from config import Config
from db.base import AsyncSessionLocal
from db.dto import ROLE_ADMIN, ROLE_SUPER_ADMIN
from db.models import Role, User, UserRole


logger = logging.getLogger(__name__)

_bot: Bot | None = None
_lock = asyncio.Lock()
_last_sent_at: dict[str, float] = {}
_recipients_cache: tuple[float, set[int]] = (0.0, set())
RECIPIENTS_CACHE_TTL_SECONDS = 60.0


def configure_admin_notifier(bot: Bot):
    global _bot
    _bot = bot


async def notify_admins(
    title: str,
    message: str,
    *,
    key: str | None = None,
    cooldown_seconds: float | None = None,
) -> bool:
    if not Config.ADMIN_ALERTS_ENABLED:
        return False

    bot = _bot

    if bot is None:
        logger.debug("Admin alert skipped: bot is not configured")
        return False

    alert_key = key or f"{title}:{message}"
    cooldown = (
        Config.ADMIN_ALERT_COOLDOWN_SECONDS
        if cooldown_seconds is None
        else max(0.0, cooldown_seconds)
    )

    if not await claim_alert(alert_key, cooldown):
        return False

    recipient_ids = await get_admin_recipient_ids()

    if not recipient_ids:
        logger.warning("Admin alert skipped: no admin recipients configured")
        return False

    text = build_alert_text(title, message)
    sent_count = 0

    for telegram_id in recipient_ids:
        try:
            await bot.send_message(telegram_id, text)
            sent_count += 1
        except TelegramAPIError as error:
            logger.warning(
                "Admin alert delivery failed: telegram_id=%s error=%s",
                telegram_id,
                type(error).__name__,
            )

    logger.debug(
        "Admin alert sent: key=%s recipients=%s sent=%s",
        alert_key,
        len(recipient_ids),
        sent_count,
    )
    return sent_count > 0


async def claim_alert(key: str, cooldown_seconds: float) -> bool:
    now = time.monotonic()

    async with _lock:
        last_sent_at = _last_sent_at.get(key)

        if (
            last_sent_at is not None
            and cooldown_seconds > 0
            and now - last_sent_at < cooldown_seconds
        ):
            return False

        _last_sent_at[key] = now
        return True


async def get_admin_recipient_ids() -> set[int]:
    cached_at, cached_ids = _recipients_cache
    now = time.monotonic()

    if cached_ids and now - cached_at < RECIPIENTS_CACHE_TTL_SECONDS:
        return set(cached_ids)

    recipient_ids = set(Config.SUPER_ADMIN_TELEGRAM_IDS)
    recipient_ids.update(await get_role_admin_telegram_ids())

    set_recipients_cache(recipient_ids)
    return recipient_ids


def set_recipients_cache(recipient_ids: set[int]):
    global _recipients_cache
    _recipients_cache = (time.monotonic(), set(recipient_ids))


async def get_role_admin_telegram_ids() -> set[int]:
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User.telegram_id)
                .join(UserRole, UserRole.user_id == User.id)
                .join(Role, Role.id == UserRole.role_id)
                .where(Role.code.in_([ROLE_ADMIN, ROLE_SUPER_ADMIN]))
                .distinct()
            )
            return {int(value) for value in result.scalars().all() if value}
    except Exception:
        logger.exception("Failed to load admin alert recipients from DB")
        return set()


def build_alert_text(title: str, message: str) -> str:
    return (
        "🚨 <b>Системне повідомлення</b>\n\n"
        f"<b>{escape(title)}</b>\n"
        f"{escape(message)}"
    )
