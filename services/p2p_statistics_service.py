import logging
import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import AsyncSessionLocal
from db.dto import P2PPriceStatisticView
from db.models import (
    CryptoCurrency,
    Exchange,
    FiatCurrency,
    P2POffer,
    P2POfferPaymentMethod,
    P2PPriceStatistic,
    PaymentMethod,
    ScanBatch,
)
from repositories.payment_method_repository import PaymentMethodRepository
from services.okx_order_payload import get_okx_order_id, get_okx_order_payment_timeout
from services.p2p_filters import (
    get_order_payment_names,
    parse_int,
    parse_percent,
    payment_name_matches_method,
)
from services.p2p_exchange_drivers import get_p2p_exchange_driver
from services.p2p_order_formatter import build_binance_order_url, build_okx_order_url
from services.time_utils import utc_now_naive as utc_now


logger = logging.getLogger(__name__)

STAT_PERIOD_HOUR = "hour"
STAT_PERIOD_DAY = "day"
STAT_PERIOD_WEEK = "week"
STAT_PERIOD_MONTH = "month"
STAT_PERIOD_YEAR = "year"
STAT_PERIOD_TYPES = (
    STAT_PERIOD_HOUR,
    STAT_PERIOD_DAY,
    STAT_PERIOD_WEEK,
    STAT_PERIOD_MONTH,
    STAT_PERIOD_YEAR,
)
STAT_ROLLUP_SOURCE_PERIODS = {
    STAT_PERIOD_DAY: STAT_PERIOD_HOUR,
    STAT_PERIOD_WEEK: STAT_PERIOD_DAY,
    STAT_PERIOD_MONTH: STAT_PERIOD_DAY,
    STAT_PERIOD_YEAR: STAT_PERIOD_MONTH,
}
STAT_PERIOD_LABELS = {
    STAT_PERIOD_HOUR: "година",
    STAT_PERIOD_DAY: "день",
    STAT_PERIOD_WEEK: "тиждень",
    STAT_PERIOD_MONTH: "місяць",
    STAT_PERIOD_YEAR: "рік",
}
PRICE_QUANT = Decimal("0.000001")
STAT_SCOPE_GLOBAL = "global"
STAT_SCOPE_FILTER = "filter"
DEFAULT_FILTER_HASH = "default"


async def cleanup_raw_scan_history(retention_hours: int) -> int:
    if retention_hours <= 0:
        return 0

    cutoff = utc_now() - timedelta(hours=retention_hours)
    expired_batch_ids = (
        select(ScanBatch.id)
        .where(
            ScanBatch.started_at < cutoff,
            ScanBatch.status != "running",
        )
        .order_by(ScanBatch.started_at)
        .limit(250)
    )

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                delete(ScanBatch).where(ScanBatch.id.in_(expired_batch_ids))
            )
            await session.commit()
            return max(0, int(result.rowcount or 0))
    except Exception as error:
        logger.warning(
            "Raw P2P scan cleanup failed: error=%s",
            type(error).__name__,
        )
        return 0


class P2PStatisticsService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.payment_method_repo = PaymentMethodRepository(session)

    async def record_scan(
        self,
        *,
        exchange_code: str,
        pair,
        side: str,
        orders: list[dict],
        requested_rows: int,
        scope: str = STAT_SCOPE_FILTER,
        filter_hash: str = DEFAULT_FILTER_HASH,
        user_id: int | None = None,
    ) -> int:
        if not orders:
            return 0

        exchange = await self.ensure_exchange(exchange_code)
        crypto = await self.ensure_crypto_currency(pair.crypto_currency_id, pair.crypto_code)
        fiat = await self.ensure_fiat_currency(pair.fiat_currency_id, pair.fiat_code)
        normalized_side = normalize_side(side)
        started_at = utc_now()
        scan_batch = ScanBatch(
            exchange_id=exchange.id,
            user_id=user_id,
            scope=scope,
            filter_hash=filter_hash,
            status="running",
            started_at=started_at,
        )
        self.session.add(scan_batch)
        await self.session.flush()

        saved_count = await self.save_offers(
            scan_batch_id=scan_batch.id,
            exchange=exchange,
            crypto=crypto,
            fiat=fiat,
            side=normalized_side,
            raw_side=side,
            orders=orders,
        )

        scan_batch.status = "done"
        scan_batch.finished_at = utc_now()

        for period_type in STAT_PERIOD_TYPES:
            period_started_at, period_ended_at = get_period_bounds(
                scan_batch.started_at,
                period_type,
            )
            await self.recalculate_period(
                exchange_code=exchange.code,
                exchange_id=exchange.id,
                crypto_currency_id=crypto.id,
                fiat_currency_id=fiat.id,
                side=normalized_side,
                scope=scope,
                filter_hash=filter_hash,
                period_type=period_type,
                period_started_at=period_started_at,
                period_ended_at=period_ended_at,
            )

        await self.session.commit()
        logger.debug(
            "P2P statistics scan saved: scope=%s filter_hash=%s exchange=%s pair=%s/%s side=%s requested=%s received=%s saved=%s",
            scope,
            filter_hash,
            exchange.code,
            crypto.code,
            fiat.code,
            normalized_side,
            requested_rows,
            len(orders),
            saved_count,
        )

        return saved_count

    async def save_offers(
        self,
        *,
        scan_batch_id: int,
        exchange: Exchange,
        crypto: CryptoCurrency,
        fiat: FiatCurrency,
        side: str,
        raw_side: str,
        orders: list[dict],
    ) -> int:
        seen_offer_ids = set()
        prepared_offers: list[tuple[P2POffer, list[str]]] = []
        payment_methods = await self.payment_method_repo.list_by_fiat(fiat.id)
        active_payment_methods = [
            method for method in payment_methods if method.is_active
        ]

        for order in orders:
            offer_id = get_exchange_offer_id(exchange.code, order)
            price = get_order_price(exchange.code, order)

            if not offer_id or price is None or offer_id in seen_offer_ids:
                continue

            seen_offer_ids.add(offer_id)
            payment_names = get_order_payment_names(order, exchange.code.lower())
            offer = build_offer_model(
                scan_batch_id=scan_batch_id,
                exchange=exchange,
                crypto=crypto,
                fiat=fiat,
                side=side,
                raw_side=raw_side,
                order=order,
                offer_id=offer_id,
                price=price,
            )
            prepared_offers.append((offer, payment_names))

        if not prepared_offers:
            return 0

        self.session.add_all([offer for offer, _ in prepared_offers])
        await self.session.flush()

        for offer, payment_names in prepared_offers:
            self.attach_offer_payment_methods(
                offer.id,
                payment_names,
                active_payment_methods,
            )

        return len(prepared_offers)

    def attach_offer_payment_methods(
        self,
        offer_id: int,
        payment_names: list[str],
        payment_methods: list[PaymentMethod],
    ):
        matched_method_ids = {
            method.id
            for payment_name in payment_names
            for method in payment_methods
            if payment_name_matches_method(payment_name, method)
        }

        for method_id in matched_method_ids:
            self.session.add(
                P2POfferPaymentMethod(
                    offer_id=offer_id,
                    payment_method_id=method_id,
                )
            )

    async def recalculate_period(
        self,
        *,
        exchange_code: str,
        exchange_id: int,
        crypto_currency_id: int,
        fiat_currency_id: int,
        side: str,
        scope: str,
        filter_hash: str,
        period_type: str,
        period_started_at: datetime,
        period_ended_at: datetime,
    ):
        if period_type == STAT_PERIOD_HOUR:
            await self.recalculate_hour_period(
                exchange_id=exchange_id,
                crypto_currency_id=crypto_currency_id,
                fiat_currency_id=fiat_currency_id,
                side=side,
                scope=scope,
                filter_hash=filter_hash,
                period_type=period_type,
                period_started_at=period_started_at,
                period_ended_at=period_ended_at,
            )
            return

        await self.recalculate_rollup_period(
            exchange_code=exchange_code,
            exchange_id=exchange_id,
            crypto_currency_id=crypto_currency_id,
            fiat_currency_id=fiat_currency_id,
            side=side,
            scope=scope,
            filter_hash=filter_hash,
            period_type=period_type,
            period_started_at=period_started_at,
            period_ended_at=period_ended_at,
        )

    async def recalculate_hour_period(
        self,
        *,
        exchange_id: int,
        crypto_currency_id: int,
        fiat_currency_id: int,
        side: str,
        scope: str,
        filter_hash: str,
        period_type: str,
        period_started_at: datetime,
        period_ended_at: datetime,
    ):
        result = await self.session.execute(
            select(
                func.min(P2POffer.price).label("min_price"),
                func.max(P2POffer.price).label("max_price"),
                func.avg(P2POffer.price).label("avg_price"),
                func.percentile_cont(0.5)
                .within_group(P2POffer.price)
                .label("median_price"),
                func.count(P2POffer.id).label("offers_count"),
                func.count(P2POffer.scan_batch_id.distinct()).label("scans_count"),
            )
            .join(ScanBatch, ScanBatch.id == P2POffer.scan_batch_id)
            .where(
                P2POffer.exchange_id == exchange_id,
                P2POffer.crypto_currency_id == crypto_currency_id,
                P2POffer.fiat_currency_id == fiat_currency_id,
                P2POffer.side == side,
                ScanBatch.scope == scope,
                ScanBatch.filter_hash == filter_hash,
                ScanBatch.started_at >= period_started_at,
                ScanBatch.started_at < period_ended_at,
            )
        )
        row = result.one()

        if not row.offers_count:
            return

        await self.save_calculated_period_statistic(
            exchange_id=exchange_id,
            crypto_currency_id=crypto_currency_id,
            fiat_currency_id=fiat_currency_id,
            side=side,
            scope=scope,
            filter_hash=filter_hash,
            period_type=period_type,
            period_started_at=period_started_at,
            period_ended_at=period_ended_at,
            min_price=row.min_price,
            max_price=row.max_price,
            avg_price=row.avg_price,
            median_price=row.median_price,
            offers_count=int(row.offers_count),
            scans_count=int(row.scans_count),
        )

    async def recalculate_rollup_period(
        self,
        *,
        exchange_code: str,
        exchange_id: int,
        crypto_currency_id: int,
        fiat_currency_id: int,
        side: str,
        scope: str,
        filter_hash: str,
        period_type: str,
        period_started_at: datetime,
        period_ended_at: datetime,
    ):
        source_period_type = STAT_ROLLUP_SOURCE_PERIODS.get(period_type)

        if source_period_type is None:
            return

        result = await self.session.execute(
            select(P2PPriceStatistic).where(
                P2PPriceStatistic.exchange_id == exchange_id,
                P2PPriceStatistic.crypto_currency_id == crypto_currency_id,
                P2PPriceStatistic.fiat_currency_id == fiat_currency_id,
                P2PPriceStatistic.side == side,
                P2PPriceStatistic.scope == scope,
                P2PPriceStatistic.filter_hash == filter_hash,
                P2PPriceStatistic.period_type == source_period_type,
                P2PPriceStatistic.period_started_at >= period_started_at,
                P2PPriceStatistic.period_started_at < period_ended_at,
            )
        )
        source_statistics = list(result.scalars().all())

        if not source_statistics:
            return

        await self.save_period_statistic(
            exchange_id=exchange_id,
            crypto_currency_id=crypto_currency_id,
            fiat_currency_id=fiat_currency_id,
            side=side,
            scope=scope,
            filter_hash=filter_hash,
            period_type=period_type,
            period_started_at=period_started_at,
            period_ended_at=period_ended_at,
            prices=sorted(
                get_rollup_price(statistic, exchange_code)
                for statistic in source_statistics
            ),
            offers_count=sum(statistic.offers_count for statistic in source_statistics),
            scans_count=sum(statistic.scans_count for statistic in source_statistics),
        )

    async def save_period_statistic(
        self,
        *,
        exchange_id: int,
        crypto_currency_id: int,
        fiat_currency_id: int,
        side: str,
        scope: str,
        filter_hash: str,
        period_type: str,
        period_started_at: datetime,
        period_ended_at: datetime,
        prices: list[Decimal],
        offers_count: int,
        scans_count: int,
    ):
        if not prices:
            return

        min_price = prices[0]
        max_price = prices[-1]
        avg_price = sum(prices, Decimal("0")) / Decimal(len(prices))
        median_price = calculate_median(prices)
        await self.save_calculated_period_statistic(
            exchange_id=exchange_id,
            crypto_currency_id=crypto_currency_id,
            fiat_currency_id=fiat_currency_id,
            side=side,
            scope=scope,
            filter_hash=filter_hash,
            period_type=period_type,
            period_started_at=period_started_at,
            period_ended_at=period_ended_at,
            min_price=min_price,
            max_price=max_price,
            avg_price=avg_price,
            median_price=median_price,
            offers_count=offers_count,
            scans_count=scans_count,
        )

    async def save_calculated_period_statistic(
        self,
        *,
        exchange_id: int,
        crypto_currency_id: int,
        fiat_currency_id: int,
        side: str,
        scope: str,
        filter_hash: str,
        period_type: str,
        period_started_at: datetime,
        period_ended_at: datetime,
        min_price: Decimal,
        max_price: Decimal,
        avg_price: Decimal,
        median_price: Decimal,
        offers_count: int,
        scans_count: int,
    ):
        statistic = await self.get_statistic(
            exchange_id=exchange_id,
            crypto_currency_id=crypto_currency_id,
            fiat_currency_id=fiat_currency_id,
            side=side,
            scope=scope,
            filter_hash=filter_hash,
            period_type=period_type,
            period_started_at=period_started_at,
        )

        if statistic is None:
            statistic = P2PPriceStatistic(
                scope=scope,
                filter_hash=filter_hash,
                exchange_id=exchange_id,
                crypto_currency_id=crypto_currency_id,
                fiat_currency_id=fiat_currency_id,
                side=side,
                period_type=period_type,
                period_started_at=period_started_at,
                period_ended_at=period_ended_at,
                min_price=round_price(min_price),
                max_price=round_price(max_price),
                avg_price=round_price(avg_price),
                median_price=round_price(median_price),
                offers_count=offers_count,
                scans_count=scans_count,
            )
            self.session.add(statistic)
            return

        statistic.period_ended_at = period_ended_at
        statistic.min_price = round_price(min_price)
        statistic.max_price = round_price(max_price)
        statistic.avg_price = round_price(avg_price)
        statistic.median_price = round_price(median_price)
        statistic.offers_count = offers_count
        statistic.scans_count = scans_count

    async def get_statistic(
        self,
        *,
        exchange_id: int,
        crypto_currency_id: int,
        fiat_currency_id: int,
        side: str,
        scope: str,
        filter_hash: str,
        period_type: str,
        period_started_at: datetime,
    ) -> P2PPriceStatistic | None:
        result = await self.session.execute(
            select(P2PPriceStatistic).where(
                P2PPriceStatistic.scope == scope,
                P2PPriceStatistic.filter_hash == filter_hash,
                P2PPriceStatistic.exchange_id == exchange_id,
                P2PPriceStatistic.crypto_currency_id == crypto_currency_id,
                P2PPriceStatistic.fiat_currency_id == fiat_currency_id,
                P2PPriceStatistic.side == side,
                P2PPriceStatistic.period_type == period_type,
                P2PPriceStatistic.period_started_at == period_started_at,
            )
        )

        return result.scalar_one_or_none()

    async def list_latest_for_pairs(
        self,
        pairs,
        *,
        period_type: str,
        limit: int = 20,
        scope: str = STAT_SCOPE_GLOBAL,
        filter_hashes: list[str] | None = None,
    ) -> list[P2PPriceStatisticView]:
        if filter_hashes is not None and not filter_hashes:
            return []

        pair_conditions = [
            and_(
                P2PPriceStatistic.crypto_currency_id == pair.crypto_currency_id,
                P2PPriceStatistic.fiat_currency_id == pair.fiat_currency_id,
            )
            for pair in pairs
        ]
        conditions = [
            P2PPriceStatistic.scope == scope,
            P2PPriceStatistic.period_type == period_type,
        ]

        if pair_conditions:
            conditions.append(or_(*pair_conditions))

        if filter_hashes:
            conditions.append(P2PPriceStatistic.filter_hash.in_(filter_hashes))

        result = await self.session.execute(
            select(P2PPriceStatistic, Exchange, CryptoCurrency, FiatCurrency)
            .join(Exchange, Exchange.id == P2PPriceStatistic.exchange_id)
            .join(
                CryptoCurrency,
                CryptoCurrency.id == P2PPriceStatistic.crypto_currency_id,
            )
            .join(FiatCurrency, FiatCurrency.id == P2PPriceStatistic.fiat_currency_id)
            .where(*conditions)
            .order_by(P2PPriceStatistic.period_started_at.desc())
        )
        rows = result.all()
        latest_by_key = {}

        for statistic, exchange, crypto, fiat in rows:
            key = (exchange.id, crypto.id, fiat.id, statistic.side)

            if key in latest_by_key:
                continue

            latest_by_key[key] = build_statistic_view(
                statistic,
                exchange,
                crypto,
                fiat,
            )

            if len(latest_by_key) >= limit:
                break

        return list(latest_by_key.values())

    async def list_history_for_pairs(
        self,
        pairs,
        *,
        period_type: str,
        max_periods: int = 12,
        max_series: int = 6,
        scope: str = STAT_SCOPE_GLOBAL,
        filter_hashes: list[str] | None = None,
        exchange_codes: list[str] | None = None,
        sides: list[str] | None = None,
        period_started_from: datetime | None = None,
        period_started_to: datetime | None = None,
        include_previous_filter_hashes: bool = False,
    ) -> list[P2PPriceStatisticView]:
        if filter_hashes is not None and not filter_hashes:
            return []

        pair_conditions = [
            and_(
                P2PPriceStatistic.crypto_currency_id == pair.crypto_currency_id,
                P2PPriceStatistic.fiat_currency_id == pair.fiat_currency_id,
            )
            for pair in pairs
        ]
        conditions = [
            P2PPriceStatistic.scope == scope,
            P2PPriceStatistic.period_type == period_type,
        ]

        if pair_conditions:
            conditions.append(or_(*pair_conditions))

        if filter_hashes and not include_previous_filter_hashes:
            conditions.append(P2PPriceStatistic.filter_hash.in_(filter_hashes))

        if exchange_codes:
            conditions.append(
                Exchange.code.in_([str(code).upper() for code in exchange_codes])
            )

        if sides:
            conditions.append(
                P2PPriceStatistic.side.in_([normalize_side(side) for side in sides])
            )

        if period_started_from is not None:
            conditions.append(P2PPriceStatistic.period_started_at >= period_started_from)

        if period_started_to is not None:
            conditions.append(P2PPriceStatistic.period_started_at < period_started_to)

        query = select(P2PPriceStatistic, Exchange, CryptoCurrency, FiatCurrency)

        if include_previous_filter_hashes:
            current_hash_priority = case(
                (P2PPriceStatistic.filter_hash.in_(filter_hashes or []), 0),
                else_=1,
            )
            history_rank = func.row_number().over(
                partition_by=(
                    P2PPriceStatistic.exchange_id,
                    P2PPriceStatistic.crypto_currency_id,
                    P2PPriceStatistic.fiat_currency_id,
                    P2PPriceStatistic.side,
                    P2PPriceStatistic.period_started_at,
                ),
                order_by=(
                    current_hash_priority,
                    P2PPriceStatistic.updated_at.desc(),
                    P2PPriceStatistic.id.desc(),
                ),
            ).label("history_rank")
            ranked_history = (
                select(
                    P2PPriceStatistic.id.label("statistic_id"),
                    history_rank,
                )
                .join(Exchange, Exchange.id == P2PPriceStatistic.exchange_id)
                .where(*conditions)
                .subquery()
            )
            query = query.join(
                ranked_history,
                and_(
                    ranked_history.c.statistic_id == P2PPriceStatistic.id,
                    ranked_history.c.history_rank == 1,
                ),
            )

        result = await self.session.execute(
            query
            .join(Exchange, Exchange.id == P2PPriceStatistic.exchange_id)
            .join(
                CryptoCurrency,
                CryptoCurrency.id == P2PPriceStatistic.crypto_currency_id,
            )
            .join(FiatCurrency, FiatCurrency.id == P2PPriceStatistic.fiat_currency_id)
            .where(*conditions)
            .order_by(P2PPriceStatistic.period_started_at.desc())
            .limit(max(max_periods * max_series * 4, 100))
        )
        rows = select_preferred_history_rows(
            result.all(),
            current_filter_hashes=filter_hashes or [],
        )
        views = [
            build_statistic_view(statistic, exchange, crypto, fiat)
            for statistic, exchange, crypto, fiat in rows
        ]
        selected_periods = []

        for view in views:
            if view.period_started_at in selected_periods:
                continue

            selected_periods.append(view.period_started_at)

            if len(selected_periods) >= max_periods:
                break

        selected_period_set = set(selected_periods)
        selected_series = []

        for view in views:
            if view.period_started_at not in selected_period_set:
                continue

            series_key = get_statistic_series_key(view)

            if series_key in selected_series:
                continue

            selected_series.append(series_key)

            if len(selected_series) >= max_series:
                break

        selected_series_set = set(selected_series)

        return sorted(
            [
                view
                for view in views
                if view.period_started_at in selected_period_set
                and get_statistic_series_key(view) in selected_series_set
            ],
            key=lambda view: (
                view.period_started_at,
                view.exchange_code,
                view.pair_label,
                view.side,
            ),
        )

    async def ensure_exchange(self, code: str) -> Exchange:
        normalized_code = code.upper()
        result = await self.session.execute(
            select(Exchange).where(Exchange.code == normalized_code)
        )
        exchange = result.scalar_one_or_none()

        if exchange:
            return exchange

        exchange = Exchange(code=normalized_code, name=normalized_code.title())
        self.session.add(exchange)
        await self.session.flush()

        return exchange

    async def ensure_crypto_currency(
        self,
        currency_id: int,
        code: str,
    ) -> CryptoCurrency:
        currency = await self.session.get(CryptoCurrency, currency_id)

        if currency:
            return currency

        return await self.ensure_currency_by_code(CryptoCurrency, code)

    async def ensure_fiat_currency(
        self,
        currency_id: int,
        code: str,
    ) -> FiatCurrency:
        currency = await self.session.get(FiatCurrency, currency_id)

        if currency:
            return currency

        return await self.ensure_currency_by_code(FiatCurrency, code)

    async def ensure_currency_by_code(self, model, code: str):
        normalized_code = code.upper()
        result = await self.session.execute(
            select(model).where(model.code == normalized_code)
        )
        currency = result.scalar_one_or_none()

        if currency:
            return currency

        currency = model(code=normalized_code, name=normalized_code)
        self.session.add(currency)
        await self.session.flush()

        return currency


async def record_p2p_scan_snapshot(
    *,
    exchange_code: str,
    pair,
    side: str,
    orders: list[dict],
    requested_rows: int,
    scope: str = STAT_SCOPE_FILTER,
    filter_hash: str = DEFAULT_FILTER_HASH,
    user_id: int | None = None,
) -> int:
    try:
        async with AsyncSessionLocal() as session:
            return await P2PStatisticsService(session).record_scan(
                exchange_code=exchange_code,
                pair=pair,
                side=side,
                orders=orders,
                requested_rows=requested_rows,
                scope=scope,
                filter_hash=filter_hash,
                user_id=user_id,
            )
    except Exception:
        logger.exception(
            "P2P statistics scan save failed: scope=%s filter_hash=%s exchange=%s pair=%s side=%s orders=%s",
            scope,
            filter_hash,
            exchange_code,
            getattr(pair, "label", "?"),
            side,
            len(orders or []),
        )
        return 0


def build_statistics_filter_hash(
    *,
    exchange_code: str,
    pair,
    side: str,
    settings,
    payment_methods=None,
) -> str:
    payload = build_statistics_filter_payload(
        exchange_code=exchange_code,
        pair=pair,
        side=side,
        settings=settings,
        payment_methods=payment_methods or [],
    )
    serialized_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    return hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()


def build_statistics_filter_payload(
    *,
    exchange_code: str,
    pair,
    side: str,
    settings,
    payment_methods,
) -> dict:
    payload = {
        "exchange": str(exchange_code).upper(),
        "asset": str(getattr(pair, "crypto_code", "")).upper(),
        "fiat": str(getattr(pair, "fiat_code", "")).upper(),
        "side": normalize_side(side),
        "candidate_order_count": int(getattr(settings, "candidate_order_count", 0) or 0),
        "description_check_mode": str(
            getattr(settings, "description_check_mode", "regex") or "regex"
        ),
        "max_order_minutes": getattr(settings, "max_order_minutes", None),
        "min_trades": getattr(settings, "min_trades", None),
        "min_rating": normalize_hash_float(getattr(settings, "min_rating", None)),
        "min_completion": normalize_hash_float(
            getattr(settings, "min_completion", None)
        ),
        "payment_categories": sorted(
            str(category)
            for category in getattr(settings, "payment_categories", set())
        ),
        "payment_methods": sorted(
            normalize_payment_method_for_hash(method)
            for method in payment_methods
        ),
        "allow_third_party_payments": bool(
            getattr(settings, "allow_third_party_payments", True)
        ),
        "allow_split_payments": bool(
            getattr(settings, "allow_split_payments", True)
        ),
        "allow_monobank_jar_payments": bool(
            getattr(settings, "allow_monobank_jar_payments", True)
        ),
    }
    min_order_amount = getattr(settings, "min_order_amount", None)
    max_order_amount = getattr(settings, "max_order_amount", None)

    if min_order_amount is not None:
        payload["min_order_amount"] = normalize_hash_float(min_order_amount)

    if max_order_amount is not None:
        payload["max_order_amount"] = normalize_hash_float(max_order_amount)

    return payload


def normalize_hash_float(value) -> float | None:
    if value is None:
        return None

    return round(float(value), 4)


def normalize_payment_method_for_hash(method) -> str:
    method_id = getattr(method, "id", None) or getattr(method, "payment_method_id", None)
    code = getattr(method, "code", "")

    return f"{method_id}:{str(code).upper()}"


def build_offer_model(
    *,
    scan_batch_id: int,
    exchange: Exchange,
    crypto: CryptoCurrency,
    fiat: FiatCurrency,
    side: str,
    raw_side: str,
    order: dict,
    offer_id: str,
    price: Decimal,
) -> P2POffer:
    if exchange.code == "BINANCE":
        return build_binance_offer_model(
            scan_batch_id=scan_batch_id,
            exchange=exchange,
            crypto=crypto,
            fiat=fiat,
            side=side,
            raw_side=raw_side,
            order=order,
            offer_id=offer_id,
            price=price,
        )

    return build_okx_offer_model(
        scan_batch_id=scan_batch_id,
        exchange=exchange,
        crypto=crypto,
        fiat=fiat,
        side=side,
        raw_side=raw_side,
        order=order,
        offer_id=offer_id,
        price=price,
    )


def build_binance_offer_model(
    *,
    scan_batch_id: int,
    exchange: Exchange,
    crypto: CryptoCurrency,
    fiat: FiatCurrency,
    side: str,
    raw_side: str,
    order: dict,
    offer_id: str,
    price: Decimal,
) -> P2POffer:
    adv = order.get("adv", {})
    advertiser = order.get("advertiser", {})

    return P2POffer(
        scan_batch_id=scan_batch_id,
        exchange_id=exchange.id,
        crypto_currency_id=crypto.id,
        fiat_currency_id=fiat.id,
        exchange_offer_id=offer_id,
        side=side,
        price=price,
        available_amount=decimal_or_none(adv.get("tradableQuantity") or adv.get("surplusAmount")),
        min_amount=decimal_or_none(adv.get("minSingleTransAmount")),
        max_amount=decimal_or_none(adv.get("dynamicMaxSingleTransAmount")),
        merchant_id=string_or_none(
            advertiser.get("userNo")
            or advertiser.get("userId")
            or advertiser.get("advertiserNo")
        ),
        merchant_name=string_or_none(advertiser.get("nickName")),
        merchant_orders=parse_int(
            advertiser.get("monthOrderCount") or advertiser.get("orderCount")
        ),
        merchant_rating=decimal_or_none(parse_percent(advertiser.get("positiveRate"))),
        merchant_completion_rate=decimal_or_none(
            parse_percent(advertiser.get("monthFinishRate"))
        ),
        payment_time_minutes=parse_int(adv.get("payTimeLimit")),
        order_url=build_binance_order_url(order),
    )


def build_okx_offer_model(
    *,
    scan_batch_id: int,
    exchange: Exchange,
    crypto: CryptoCurrency,
    fiat: FiatCurrency,
    side: str,
    raw_side: str,
    order: dict,
    offer_id: str,
    price: Decimal,
) -> P2POffer:
    creator = order.get("creator") if isinstance(order.get("creator"), dict) else {}

    return P2POffer(
        scan_batch_id=scan_batch_id,
        exchange_id=exchange.id,
        crypto_currency_id=crypto.id,
        fiat_currency_id=fiat.id,
        exchange_offer_id=offer_id,
        side=side,
        price=price,
        available_amount=decimal_or_none(order.get("availableAmount")),
        min_amount=decimal_or_none(order.get("quoteMinAmountPerOrder")),
        max_amount=decimal_or_none(order.get("quoteMaxAmountPerOrder")),
        merchant_id=string_or_none(
            order.get("publicUserId")
            or order.get("publicMerchantId")
            or creator.get("publicUserId")
            or creator.get("publicMerchantId")
        ),
        merchant_name=string_or_none(order.get("nickName") or creator.get("nickName")),
        merchant_orders=parse_int(
            order.get("completedOrderQuantity")
            or creator.get("completedOrderQuantity")
        ),
        merchant_rating=decimal_or_none(
            parse_percent(order.get("posReviewPercentage"))
            or parse_percent(order.get("completedRate"))
            or parse_percent(creator.get("completionRate"))
        ),
        merchant_completion_rate=decimal_or_none(
            parse_percent(order.get("completedRate") or creator.get("completionRate"))
        ),
        payment_time_minutes=parse_int(get_okx_order_payment_timeout(order)),
        order_url=build_okx_order_url(
            order,
            raw_side.lower(),
            asset=crypto.code,
            fiat=fiat.code,
        ),
    )


def get_exchange_offer_id(exchange_code: str, order: dict) -> str | None:
    if exchange_code == "BINANCE":
        adv = order.get("adv", {})
        return string_or_none(adv.get("advNo"))

    return get_okx_order_id(order)


def get_order_price(exchange_code: str, order: dict) -> Decimal | None:
    if exchange_code == "BINANCE":
        return decimal_or_none(order.get("adv", {}).get("price"))

    return decimal_or_none(order.get("price"))


def build_statistic_view(
    statistic: P2PPriceStatistic,
    exchange: Exchange,
    crypto: CryptoCurrency,
    fiat: FiatCurrency,
) -> P2PPriceStatisticView:
    return P2PPriceStatisticView(
        exchange_code=exchange.code,
        crypto_code=crypto.code,
        fiat_code=fiat.code,
        side=statistic.side,
        period_type=statistic.period_type,
        period_started_at=statistic.period_started_at,
        period_ended_at=statistic.period_ended_at,
        min_price=statistic.min_price,
        max_price=statistic.max_price,
        avg_price=statistic.avg_price,
        median_price=statistic.median_price,
        offers_count=statistic.offers_count,
        scans_count=statistic.scans_count,
        scope=statistic.scope,
        filter_hash=statistic.filter_hash,
    )


def get_statistic_series_key(view: P2PPriceStatisticView) -> tuple[str, str, str, str]:
    return (view.exchange_code, view.crypto_code, view.fiat_code, view.side)


def select_preferred_history_rows(
    rows,
    *,
    current_filter_hashes: list[str],
):
    """Keep one point per period, preferring the currently active filter."""
    current_hashes = set(current_filter_hashes)
    selected = {}

    for row in rows:
        statistic, exchange, crypto, fiat = row
        key = (
            exchange.id,
            crypto.id,
            fiat.id,
            statistic.side,
            statistic.period_started_at,
        )
        priority = (
            statistic.filter_hash in current_hashes,
            statistic.updated_at or statistic.created_at or datetime.min,
            statistic.id or 0,
        )
        previous = selected.get(key)

        if previous is None or priority > previous[0]:
            selected[key] = (priority, row)

    return [item[1] for item in selected.values()]


def get_period_bounds(value: datetime, period_type: str) -> tuple[datetime, datetime]:
    if period_type == STAT_PERIOD_HOUR:
        start = value.replace(minute=0, second=0, microsecond=0)
        return start, start + timedelta(hours=1)

    if period_type == STAT_PERIOD_DAY:
        start = value.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)

    if period_type == STAT_PERIOD_WEEK:
        day_start = value.replace(hour=0, minute=0, second=0, microsecond=0)
        start = day_start - timedelta(days=day_start.weekday())
        return start, start + timedelta(days=7)

    if period_type == STAT_PERIOD_MONTH:
        start = value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            return start, start.replace(year=start.year + 1, month=1)

        return start, start.replace(month=start.month + 1)

    if period_type == STAT_PERIOD_YEAR:
        start = value.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, start.replace(year=start.year + 1)

    raise ValueError(f"Unsupported statistic period type: {period_type}")


def normalize_side(value: str) -> str:
    return str(value).upper()


def calculate_median(prices: list[Decimal]) -> Decimal:
    midpoint = len(prices) // 2

    if len(prices) % 2:
        return prices[midpoint]

    return (prices[midpoint - 1] + prices[midpoint]) / Decimal("2")


def get_rollup_price(statistic: P2PPriceStatistic, exchange_code: str) -> Decimal:
    if statistic.period_type == STAT_PERIOD_HOUR:
        return get_directional_extreme_price(statistic, exchange_code)

    return statistic.avg_price


def get_directional_extreme_price(
    statistic,
    exchange_code: str | None = None,
) -> Decimal:
    exchange = exchange_code or getattr(statistic, "exchange_code", None)

    if is_crypto_to_fiat_side(exchange, statistic.side):
        return statistic.max_price

    return statistic.min_price


def is_crypto_to_fiat_side(exchange_code: str | None, side: str) -> bool:
    if exchange_code:
        try:
            driver = get_p2p_exchange_driver(exchange_code)
        except ValueError:
            driver = None

        if driver is not None:
            return normalize_side(side) == normalize_side(driver.crypto_to_fiat_side)

    return normalize_side(side) == "SELL"


def round_price(value: Decimal) -> Decimal:
    return value.quantize(PRICE_QUANT, rounding=ROUND_HALF_UP)


def decimal_or_none(value) -> Decimal | None:
    if value in (None, ""):
        return None

    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def string_or_none(value) -> str | None:
    if value in (None, ""):
        return None

    return str(value)
