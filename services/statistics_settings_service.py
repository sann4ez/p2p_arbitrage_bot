from decimal import Decimal, InvalidOperation

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    CryptoCurrency,
    Exchange,
    FiatCurrency,
    GlobalStatisticsPaymentMethod,
    GlobalStatisticsSettings,
    PaymentMethod,
)
from services.p2p_filters import (
    apply_settings_to_model,
    cycle_value,
    decimal_or_none,
    normalize_candidate_order_count,
    normalize_description_check_mode,
    settings_from_model,
)
from db.dto import (
    CANDIDATE_ORDER_COUNT_OPTIONS,
    DESCRIPTION_CHECK_MODE_OPTIONS,
    MIN_PERCENT_OPTIONS,
    MIN_TRADES_OPTIONS,
    ORDER_MINUTES_OPTIONS,
    PAYMENT_CATEGORIES,
    P2PFilterSettings,
)


class StatisticsSettingsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_settings(self) -> GlobalStatisticsSettings:
        settings = await self.session.get(GlobalStatisticsSettings, 1)

        if settings:
            return settings

        settings = GlobalStatisticsSettings(id=1)
        self.session.add(settings)
        await self.session.commit()
        await self.session.refresh(settings)

        return settings

    async def get_filter_settings(self) -> P2PFilterSettings:
        return settings_from_model(await self.get_or_create_settings())

    async def list_crypto_currencies(self) -> list[CryptoCurrency]:
        result = await self.session.execute(
            select(CryptoCurrency).order_by(CryptoCurrency.code)
        )

        return list(result.scalars().all())

    async def list_fiat_currencies(self) -> list[FiatCurrency]:
        result = await self.session.execute(select(FiatCurrency).order_by(FiatCurrency.code))

        return list(result.scalars().all())

    async def list_active_exchanges(self, settings: GlobalStatisticsSettings | None = None) -> list[Exchange]:
        settings = settings or await self.get_or_create_settings()
        codes = []

        if settings.scan_binance:
            codes.append("BINANCE")

        if settings.scan_okx:
            codes.append("OKX")

        if not codes:
            return []

        result = await self.session.execute(
            select(Exchange)
            .where(Exchange.code.in_(codes), Exchange.is_active.is_(True))
            .order_by(Exchange.code)
        )

        return list(result.scalars().all())

    async def list_selected_payment_method_ids(self) -> set[int]:
        result = await self.session.execute(
            select(GlobalStatisticsPaymentMethod.payment_method_id)
        )

        return set(result.scalars().all())

    async def list_selected_payment_methods(self) -> list[PaymentMethod]:
        result = await self.session.execute(
            select(PaymentMethod)
            .join(
                GlobalStatisticsPaymentMethod,
                GlobalStatisticsPaymentMethod.payment_method_id
                == PaymentMethod.id,
            )
            .where(PaymentMethod.is_active.is_(True))
            .order_by(PaymentMethod.name)
        )

        return list(result.scalars().all())

    async def list_payment_methods_for_fiat(
        self,
        fiat_currency_id: int,
    ) -> list[PaymentMethod]:
        result = await self.session.execute(
            select(PaymentMethod)
            .where(
                PaymentMethod.fiat_currency_id == fiat_currency_id,
                PaymentMethod.is_active.is_(True),
            )
            .order_by(PaymentMethod.name)
        )

        return list(result.scalars().all())

    async def list_selected_methods_for_fiat_code(
        self,
        fiat_code: str,
    ) -> list[PaymentMethod]:
        selected_ids = await self.list_selected_payment_method_ids()

        if not selected_ids:
            return []

        result = await self.session.execute(
            select(PaymentMethod)
            .join(FiatCurrency, FiatCurrency.id == PaymentMethod.fiat_currency_id)
            .where(
                FiatCurrency.code == fiat_code.upper(),
                PaymentMethod.id.in_(selected_ids),
                PaymentMethod.is_active.is_(True),
            )
            .order_by(PaymentMethod.name)
        )

        return list(result.scalars().all())

    async def toggle_payment_method(self, payment_method_id: int) -> bool:
        selected = await self.session.get(
            GlobalStatisticsPaymentMethod,
            payment_method_id,
        )

        if selected:
            await self.session.delete(selected)
            await self.session.commit()
            return False

        method = await self.session.get(PaymentMethod, payment_method_id)

        if not method or not method.is_active:
            return False

        self.session.add(
            GlobalStatisticsPaymentMethod(payment_method_id=payment_method_id)
        )
        await self.session.commit()

        return True

    async def toggle_bool(self, field: str) -> GlobalStatisticsSettings:
        settings = await self.get_or_create_settings()

        if not hasattr(settings, field):
            return settings

        setattr(settings, field, not bool(getattr(settings, field)))
        await self.session.commit()
        await self.session.refresh(settings)

        return settings

    async def cycle_order_minutes(self) -> GlobalStatisticsSettings:
        settings = await self.get_or_create_settings()
        settings.max_order_minutes = cycle_value(
            ORDER_MINUTES_OPTIONS,
            settings.max_order_minutes,
        )
        await self.session.commit()
        await self.session.refresh(settings)

        return settings

    async def cycle_min_trades(self) -> GlobalStatisticsSettings:
        settings = await self.get_or_create_settings()
        settings.min_merchant_orders = cycle_value(
            MIN_TRADES_OPTIONS,
            settings.min_merchant_orders,
        )
        await self.session.commit()
        await self.session.refresh(settings)

        return settings

    async def cycle_min_rating(self) -> GlobalStatisticsSettings:
        settings = await self.get_or_create_settings()
        current = float(settings.min_merchant_rating) if settings.min_merchant_rating else None
        settings.min_merchant_rating = decimal_or_none(
            cycle_value(MIN_PERCENT_OPTIONS, current)
        )
        await self.session.commit()
        await self.session.refresh(settings)

        return settings

    async def cycle_min_completion(self) -> GlobalStatisticsSettings:
        settings = await self.get_or_create_settings()
        current = (
            float(settings.min_merchant_completion_rate)
            if settings.min_merchant_completion_rate
            else None
        )
        settings.min_merchant_completion_rate = decimal_or_none(
            cycle_value(MIN_PERCENT_OPTIONS, current)
        )
        await self.session.commit()
        await self.session.refresh(settings)

        return settings

    async def cycle_candidate_order_count(self) -> GlobalStatisticsSettings:
        settings = await self.get_or_create_settings()
        settings.candidate_order_count = cycle_value(
            CANDIDATE_ORDER_COUNT_OPTIONS,
            normalize_candidate_order_count(settings.candidate_order_count),
        )
        await self.session.commit()
        await self.session.refresh(settings)

        return settings

    async def cycle_description_check_mode(self) -> GlobalStatisticsSettings:
        settings = await self.get_or_create_settings()
        settings.description_check_mode = cycle_value(
            DESCRIPTION_CHECK_MODE_OPTIONS,
            normalize_description_check_mode(settings.description_check_mode),
        )
        await self.session.commit()
        await self.session.refresh(settings)

        return settings

    async def reset_filters(self) -> GlobalStatisticsSettings:
        settings = await self.get_or_create_settings()
        reset = P2PFilterSettings(candidate_order_count=200, display_order_count=20)
        apply_settings_to_model(settings, reset)
        await self.session.execute(delete(GlobalStatisticsPaymentMethod))
        await self.session.commit()
        await self.session.refresh(settings)

        return settings

    async def set_filter_value(self, field: str, raw_value: str) -> P2PFilterSettings:
        settings_model = await self.get_or_create_settings()
        settings = settings_from_model(settings_model)

        if field == "min_amount":
            settings.min_order_amount = parse_optional_amount(raw_value)
        elif field == "max_amount":
            settings.max_order_amount = parse_optional_amount(raw_value)
        elif field == "time":
            settings.max_order_minutes = parse_optional_int(raw_value)
        elif field == "trades":
            settings.min_trades = parse_optional_int(raw_value)
        elif field == "rating":
            settings.min_rating = parse_optional_float(raw_value)
        elif field == "completion":
            settings.min_completion = parse_optional_float(raw_value)
        elif field == "display":
            settings.display_order_count = int(raw_value)
        elif field == "candidates":
            settings.candidate_order_count = int(raw_value)
        elif field == "desc":
            settings.description_check_mode = raw_value
        elif field == "third_party":
            settings.allow_third_party_payments = raw_value == "1"
        elif field == "split":
            settings.allow_split_payments = raw_value == "1"
        elif field == "mono_jar":
            settings.allow_monobank_jar_payments = raw_value == "1"

        validate_order_amount_range(settings)
        apply_settings_to_model(settings_model, settings)
        await self.session.commit()

        return settings_from_model(settings_model)

    async def toggle_payment_category(self, category: str) -> P2PFilterSettings:
        settings_model = await self.get_or_create_settings()
        settings = settings_from_model(settings_model)

        if category not in PAYMENT_CATEGORIES:
            return settings

        if category in settings.payment_categories and len(settings.payment_categories) > 1:
            settings.payment_categories.remove(category)
        else:
            settings.payment_categories.add(category)

        apply_settings_to_model(settings_model, settings)
        await self.session.commit()

        return settings_from_model(settings_model)


def parse_optional_int(value: str) -> int | None:
    return None if value == "none" else int(value)


def parse_optional_float(value: str) -> float | None:
    return None if value == "none" else float(value)


def parse_optional_amount(value: str) -> float | None:
    normalized = (
        str(value)
        .strip()
        .lower()
        .replace("\u00a0", "")
        .replace(" ", "")
        .replace(",", ".")
    )

    if normalized in {"none", "-", "скинути", "очистити", "безобмеження"}:
        return None

    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError("Сума має бути числом.") from exc

    if not amount.is_finite() or amount < 0:
        raise ValueError("Сума має бути невід'ємним числом.")

    if amount > Decimal("999999999999.99"):
        raise ValueError("Сума завелика.")

    try:
        rounded_amount = amount.quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError("Некоректний формат суми.") from exc

    return float(rounded_amount)


def validate_order_amount_range(settings: P2PFilterSettings):
    if (
        settings.min_order_amount is not None
        and settings.max_order_amount is not None
        and settings.min_order_amount > settings.max_order_amount
    ):
        raise ValueError("Мінімальна сума не може бути більшою за максимальну.")
