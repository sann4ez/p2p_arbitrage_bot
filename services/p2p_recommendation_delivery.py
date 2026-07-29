import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import Config
from db.base import AsyncSessionLocal
from db.models import (
    Exchange,
    P2PMarketRecommendation,
    P2POffer,
    P2POfferPaymentMethod,
    P2PRecommendationDelivery,
    PaymentMethod,
    ScanBatch,
    User,
    UserPair,
    UserPaymentMethod,
    UserSettings,
)
from keyboards.recommendations import recommendation_action_kb
from services.p2p_exchange_drivers import get_p2p_exchange_driver
from services.p2p_recommendation_service import RecommendationRecord
from services.p2p_recommendation_signals import ACTION_BUY, ACTION_SELL
from services.p2p_statistics_service import STAT_SCOPE_GLOBAL, normalize_side
from services.time_utils import utc_now_naive as utc_now


logger = logging.getLogger(__name__)
DELIVERY_PENDING = "pending"
DELIVERY_SENT = "sent"
DELIVERY_ACCEPTED = "accepted"
DELIVERY_SKIPPED = "skipped"
DELIVERY_FAILED = "failed"


@dataclass(frozen=True)
class RecommendationTarget:
    user_id: int
    telegram_id: int
    timezone_name: str | None
    pairs: frozenset[tuple[int, int]]


@dataclass(frozen=True)
class BankChoiceResult:
    delivery_id: int | None
    methods: tuple[PaymentMethod, ...]
    message: str


@dataclass(frozen=True)
class DeliveryActionResult:
    ok: bool
    message: str


class P2PRecommendationDeliveryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_enabled_targets(self) -> list[RecommendationTarget]:
        allowed_ids = sorted(Config.P2P_RECOMMENDATIONS_TELEGRAM_IDS)

        if not Config.P2P_RECOMMENDATIONS_ENABLED or not allowed_ids:
            return []

        result = await self.session.execute(
            select(
                User.id,
                User.telegram_id,
                User.location_timezone,
            )
            .join(UserSettings, UserSettings.user_id == User.id)
            .where(
                User.telegram_id.in_(allowed_ids),
                User.is_notifications_enabled.is_(True),
                UserSettings.is_recommendations_enabled.is_(True),
            )
        )
        users = result.all()

        if not users:
            return []

        user_ids = [row.id for row in users]
        pair_result = await self.session.execute(
            select(
                UserPair.user_id,
                UserPair.crypto_currency_id,
                UserPair.fiat_currency_id,
            ).where(UserPair.user_id.in_(user_ids))
        )
        pairs_by_user = {user_id: set() for user_id in user_ids}

        for user_id, crypto_id, fiat_id in pair_result.all():
            pairs_by_user[user_id].add((crypto_id, fiat_id))

        return [
            RecommendationTarget(
                user_id=row.id,
                telegram_id=row.telegram_id,
                timezone_name=row.location_timezone,
                pairs=frozenset(pairs_by_user[row.id]),
            )
            for row in users
        ]

    async def has_completed_action_this_month(
        self,
        target: RecommendationTarget,
        action: str,
    ) -> bool:
        started_at, ended_at = local_month_utc_bounds(target.timezone_name)
        result = await self.session.execute(
            select(P2PRecommendationDelivery.id)
            .join(
                P2PMarketRecommendation,
                P2PMarketRecommendation.id
                == P2PRecommendationDelivery.recommendation_id,
            )
            .where(
                P2PRecommendationDelivery.user_id == target.user_id,
                P2PRecommendationDelivery.status == DELIVERY_ACCEPTED,
                P2PRecommendationDelivery.responded_at >= started_at,
                P2PRecommendationDelivery.responded_at < ended_at,
                P2PMarketRecommendation.action == action,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_unused_payment_methods(
        self,
        target: RecommendationTarget,
        fiat_currency_id: int,
    ) -> list[PaymentMethod]:
        started_at, ended_at = local_month_utc_bounds(target.timezone_name)
        used_result = await self.session.execute(
            select(P2PRecommendationDelivery.selected_payment_method_id).where(
                P2PRecommendationDelivery.user_id == target.user_id,
                P2PRecommendationDelivery.status == DELIVERY_ACCEPTED,
                P2PRecommendationDelivery.responded_at >= started_at,
                P2PRecommendationDelivery.responded_at < ended_at,
                P2PRecommendationDelivery.selected_payment_method_id.is_not(None),
            )
        )
        used_ids = set(used_result.scalars().all())
        result = await self.session.execute(
            select(PaymentMethod)
            .join(
                UserPaymentMethod,
                UserPaymentMethod.payment_method_id == PaymentMethod.id,
            )
            .where(
                UserPaymentMethod.user_id == target.user_id,
                PaymentMethod.fiat_currency_id == fiat_currency_id,
                PaymentMethod.is_active.is_(True),
            )
            .order_by(PaymentMethod.name)
        )
        return [method for method in result.scalars().all() if method.id not in used_ids]

    async def list_relevant_unused_payment_methods(
        self,
        target: RecommendationTarget,
        recommendation: RecommendationRecord | P2PMarketRecommendation,
    ) -> list[PaymentMethod]:
        methods = await self.list_unused_payment_methods(
            target,
            recommendation.fiat_currency_id,
        )

        if not methods:
            return []

        exchange_code = getattr(recommendation, "exchange_code", None)

        if not exchange_code:
            result = await self.session.execute(
                select(Exchange.code).where(
                    Exchange.id == recommendation.exchange_id,
                )
            )
            exchange_code = result.scalar_one_or_none()

        if not exchange_code:
            return methods

        try:
            driver = get_p2p_exchange_driver(exchange_code)
        except ValueError:
            return methods

        side = normalize_side(
            driver.fiat_to_crypto_side
            if recommendation.action == ACTION_BUY
            else driver.crypto_to_fiat_side
        )
        batch_result = await self.session.execute(
            select(ScanBatch.id)
            .join(P2POffer, P2POffer.scan_batch_id == ScanBatch.id)
            .where(
                ScanBatch.scope == STAT_SCOPE_GLOBAL,
                ScanBatch.status == "done",
                P2POffer.exchange_id == recommendation.exchange_id,
                P2POffer.crypto_currency_id
                == recommendation.crypto_currency_id,
                P2POffer.fiat_currency_id == recommendation.fiat_currency_id,
                P2POffer.side == side,
            )
            .order_by(ScanBatch.started_at.desc())
            .limit(1)
        )
        batch_id = batch_result.scalar_one_or_none()

        if batch_id is None:
            return methods

        price_aggregate = (
            func.min(P2POffer.price)
            if recommendation.action == ACTION_BUY
            else func.max(P2POffer.price)
        )
        price_result = await self.session.execute(
            select(
                P2POfferPaymentMethod.payment_method_id,
                price_aggregate.label("price"),
            )
            .join(
                P2POffer,
                P2POffer.id == P2POfferPaymentMethod.offer_id,
            )
            .where(
                P2POffer.scan_batch_id == batch_id,
                P2POfferPaymentMethod.payment_method_id.in_(
                    [method.id for method in methods]
                ),
            )
            .group_by(P2POfferPaymentMethod.payment_method_id)
        )
        price_by_method_id = {
            method_id: price
            for method_id, price in price_result.all()
        }

        if not price_by_method_id:
            return methods

        matching = [
            method for method in methods if method.id in price_by_method_id
        ]
        matching.sort(
            key=lambda method: price_by_method_id[method.id],
            reverse=recommendation.action == ACTION_SELL,
        )
        unmatched = [
            method for method in methods if method.id not in price_by_method_id
        ]
        return matching + unmatched

    async def create_delivery(
        self,
        target: RecommendationTarget,
        recommendation: RecommendationRecord,
        suggested_method: PaymentMethod | None,
    ) -> P2PRecommendationDelivery | None:
        existing = await self.session.execute(
            select(P2PRecommendationDelivery.id).where(
                P2PRecommendationDelivery.recommendation_id == recommendation.id,
                P2PRecommendationDelivery.user_id == target.user_id,
            )
        )

        if existing.scalar_one_or_none() is not None:
            return None

        delivery = P2PRecommendationDelivery(
            recommendation_id=recommendation.id,
            user_id=target.user_id,
            suggested_payment_method_id=(suggested_method.id if suggested_method else None),
            status=DELIVERY_PENDING,
        )
        self.session.add(delivery)
        await self.session.flush()
        return delivery

    async def mark_sent(self, delivery_id: int, telegram_message_id: int):
        delivery = await self.session.get(P2PRecommendationDelivery, delivery_id)

        if delivery is None:
            return

        delivery.status = DELIVERY_SENT
        delivery.telegram_message_id = telegram_message_id
        delivery.sent_at = utc_now()
        await self.session.commit()

    async def mark_failed(self, delivery_id: int, error: Exception):
        delivery = await self.session.get(P2PRecommendationDelivery, delivery_id)

        if delivery is None:
            return

        delivery.status = DELIVERY_FAILED
        delivery.error_message = f"{type(error).__name__}: {error}"[:1000]
        await self.session.commit()

    async def get_bank_choices(
        self,
        delivery_id: int,
        telegram_id: int,
    ) -> BankChoiceResult:
        context = await self.get_delivery_context(delivery_id, telegram_id)

        if context is None:
            return BankChoiceResult(None, (), "Рекомендацію не знайдено.")

        delivery, recommendation, target = context

        if delivery.status in {DELIVERY_ACCEPTED, DELIVERY_SKIPPED}:
            return BankChoiceResult(
                delivery.id,
                (),
                "Цю рекомендацію вже оброблено.",
            )

        if recommendation_is_expired(recommendation):
            return BankChoiceResult(
                delivery.id,
                (),
                "Термін дії цієї рекомендації вже минув.",
            )

        if await self.has_completed_action_this_month(target, recommendation.action):
            return BankChoiceResult(
                delivery.id,
                (),
                "Цей напрямок уже позначено виконаним у поточному місяці.",
            )

        methods = await self.list_relevant_unused_payment_methods(
            target,
            recommendation,
        )

        if not methods:
            return BankChoiceResult(
                delivery.id,
                (),
                "Немає невикористаного банку серед обраних у профілі.",
            )

        return BankChoiceResult(
            delivery.id,
            tuple(methods),
            "Оберіть банк, через який виконали операцію:",
        )

    async def mark_completed(
        self,
        delivery_id: int,
        payment_method_id: int,
        telegram_id: int,
    ) -> DeliveryActionResult:
        context = await self.get_delivery_context(
            delivery_id,
            telegram_id,
            lock=True,
        )

        if context is None:
            return DeliveryActionResult(False, "Рекомендацію не знайдено.")

        delivery, recommendation, target = context

        if delivery.status == DELIVERY_ACCEPTED:
            return DeliveryActionResult(False, "Рекомендацію вже позначено виконаною.")

        if delivery.status == DELIVERY_SKIPPED:
            return DeliveryActionResult(False, "Рекомендацію вже пропущено.")

        if recommendation_is_expired(recommendation):
            return DeliveryActionResult(
                False,
                "Термін дії цієї рекомендації вже минув.",
            )

        if await self.has_completed_action_this_month(target, recommendation.action):
            return DeliveryActionResult(
                False,
                "Цей напрямок уже виконано в поточному місяці.",
            )

        methods = await self.list_unused_payment_methods(
            target,
            recommendation.fiat_currency_id,
        )
        method = next(
            (item for item in methods if item.id == payment_method_id),
            None,
        )

        if method is None:
            return DeliveryActionResult(
                False,
                "Цей банк недоступний або вже використовувався цього місяця.",
            )

        delivery.selected_payment_method_id = method.id
        delivery.status = DELIVERY_ACCEPTED
        delivery.responded_at = utc_now()
        await self.session.commit()
        return DeliveryActionResult(
            True,
            f"Виконання збережено. Банк: {method.name}.",
        )

    async def mark_skipped(
        self,
        delivery_id: int,
        telegram_id: int,
    ) -> DeliveryActionResult:
        context = await self.get_delivery_context(
            delivery_id,
            telegram_id,
            lock=True,
        )

        if context is None:
            return DeliveryActionResult(False, "Рекомендацію не знайдено.")

        delivery, _, _ = context

        if delivery.status == DELIVERY_ACCEPTED:
            return DeliveryActionResult(False, "Рекомендацію вже позначено виконаною.")

        if delivery.status == DELIVERY_SKIPPED:
            return DeliveryActionResult(False, "Рекомендацію вже пропущено.")

        delivery.status = DELIVERY_SKIPPED
        delivery.responded_at = utc_now()
        await self.session.commit()
        return DeliveryActionResult(True, "Рекомендацію пропущено.")

    async def get_delivery_context(
        self,
        delivery_id: int,
        telegram_id: int,
        *,
        lock: bool = False,
    ):
        statement = (
            select(P2PRecommendationDelivery, P2PMarketRecommendation, User)
            .join(
                P2PMarketRecommendation,
                P2PMarketRecommendation.id
                == P2PRecommendationDelivery.recommendation_id,
            )
            .join(User, User.id == P2PRecommendationDelivery.user_id)
            .where(
                P2PRecommendationDelivery.id == delivery_id,
                User.telegram_id == telegram_id,
            )
        )

        if lock:
            statement = statement.with_for_update()

        result = await self.session.execute(statement)
        row = result.one_or_none()

        if row is None:
            return None

        delivery, recommendation, user = row
        target = RecommendationTarget(
            user_id=user.id,
            telegram_id=user.telegram_id,
            timezone_name=user.location_timezone,
            pairs=frozenset(),
        )
        return delivery, recommendation, target


async def get_enabled_recommendation_pair_ids() -> set[tuple[int, int]]:
    async with AsyncSessionLocal() as session:
        service = P2PRecommendationDeliveryService(session)
        targets = await service.list_enabled_targets()
        return {
            pair
            for target in targets
            for pair in target.pairs
        }


async def deliver_market_recommendations(
    bot: Bot,
    recommendations: list[RecommendationRecord],
) -> int:
    if not recommendations:
        return 0

    sent_count = 0

    async with AsyncSessionLocal() as session:
        service = P2PRecommendationDeliveryService(session)
        targets = await service.list_enabled_targets()

        for target in targets:
            for recommendation in recommendations:
                pair_key = (
                    recommendation.crypto_currency_id,
                    recommendation.fiat_currency_id,
                )

                if pair_key not in target.pairs:
                    continue

                if await service.has_completed_action_this_month(
                    target,
                    recommendation.action,
                ):
                    continue

                methods = await service.list_relevant_unused_payment_methods(
                    target,
                    recommendation,
                )
                suggested_method = methods[0] if methods else None
                delivery = await service.create_delivery(
                    target,
                    recommendation,
                    suggested_method,
                )

                if delivery is None:
                    continue

                await session.commit()

                try:
                    message = await bot.send_message(
                        target.telegram_id,
                        format_recommendation_message(
                            recommendation,
                            suggested_method,
                            has_available_bank=bool(methods),
                        ),
                        reply_markup=recommendation_action_kb(
                            delivery.id,
                            can_complete=bool(methods),
                        ),
                    )
                except Exception as error:
                    logger.warning(
                        "P2P recommendation delivery failed: user=%s error=%s",
                        target.telegram_id,
                        type(error).__name__,
                    )
                    await service.mark_failed(delivery.id, error)
                    continue

                await service.mark_sent(delivery.id, message.message_id)
                sent_count += 1

    return sent_count


def format_recommendation_message(
    recommendation: RecommendationRecord,
    suggested_method: PaymentMethod | None,
    *,
    has_available_bank: bool,
) -> str:
    action_label = "BUY" if recommendation.action == ACTION_BUY else "SELL"
    action_icon = "🟢" if recommendation.action == ACTION_BUY else "🔴"
    price = (
        recommendation.buy_price
        if recommendation.action == ACTION_BUY
        else recommendation.sell_price
    )
    reasons = "\n".join(
        f"• {escape_and_truncate(reason, 500)}"
        for reason in recommendation.reasons[:3]
    )
    risks = "\n".join(
        f"• {escape_and_truncate(risk, 400)}"
        for risk in recommendation.risks[:2]
    )
    bank_text = (
        escape(suggested_method.name)
        if suggested_method is not None
        else "немає невикористаного серед обраних"
    )
    lines = [
        f"<b>{action_icon} P2P сигнал · {action_label}</b>",
        "",
        (
            f"<b>{escape(recommendation.exchange_code.upper())}</b> · "
            f"<b>{escape(recommendation.crypto_code)}/"
            f"{escape(recommendation.fiat_code)}</b>"
        ),
        (
            "Ринковий орієнтир: "
            f"<b>{format_decimal(price)} {escape(recommendation.fiat_code)}</b>"
        ),
        f"Впевненість: <b>{round(recommendation.confidence * 100)}%</b>",
        f"Вільний банк: <b>{bank_text}</b>",
        "",
        escape_and_truncate(recommendation.summary, 900),
    ]

    if reasons:
        lines.extend(["", "<b>Чому:</b>", reasons])

    if risks:
        lines.extend(["", "<b>Що може змінити сигнал:</b>", risks])

    if not has_available_bank:
        lines.extend(
            [
                "",
                (
                    "Додайте ще один банк у профілі, щоб зафіксувати виконання "
                    "без повторного використання банку цього місяця."
                ),
            ]
        )

    lines.extend(
        [
            "",
            (
                "<i>Сигнал сформовано зі статистики бота та AI-перевірки. "
                "Угода не виконується автоматично.</i>"
            ),
        ]
    )
    return "\n".join(lines)


def local_month_utc_bounds(timezone_name: str | None) -> tuple[datetime, datetime]:
    try:
        tz = ZoneInfo(timezone_name or Config.DISPLAY_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        tz = timezone.utc

    local_now = datetime.now(tz)
    started_local = local_now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    if started_local.month == 12:
        ended_local = started_local.replace(
            year=started_local.year + 1,
            month=1,
        )
    else:
        ended_local = started_local.replace(month=started_local.month + 1)

    return (
        started_local.astimezone(timezone.utc).replace(tzinfo=None),
        ended_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def format_decimal(value: Decimal | None) -> str:
    if value is None:
        return "не вказано"

    return format(value.normalize(), "f")


def escape_and_truncate(value: str, escaped_limit: int) -> str:
    value = str(value or "").strip()
    escaped_parts = []
    escaped_length = 0

    for character in value:
        escaped_character = escape(character)

        if escaped_length + len(escaped_character) > escaped_limit - 1:
            return "".join(escaped_parts).rstrip() + "…"

        escaped_parts.append(escaped_character)
        escaped_length += len(escaped_character)

    return "".join(escaped_parts)


def recommendation_is_expired(
    recommendation: P2PMarketRecommendation,
) -> bool:
    ttl_seconds = max(
        300,
        int(Config.P2P_RECOMMENDATION_NOTIFICATION_COOLDOWN_SECONDS),
    )
    return recommendation.observed_at < utc_now() - timedelta(
        seconds=ttl_seconds,
    )
