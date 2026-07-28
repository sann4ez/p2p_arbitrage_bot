import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from config import Config
from db.models import (
    CryptoCurrency,
    Exchange,
    FiatCurrency,
    P2PMacroAnalysis,
    P2PMarketRecommendation,
    P2POffer,
    P2PPriceStatistic,
    ScanBatch,
)
from services.p2p_exchange_drivers import get_p2p_exchange_driver
from services.p2p_recommendation_ai import (
    AIRecommendationResult,
    MacroAnalysisResult,
    analyze_fiat_macro_context,
    can_call_openai,
    review_market_signal,
)
from services.p2p_recommendation_signals import (
    ACTION_BUY,
    ACTION_HOLD,
    ACTION_SELL,
    MarketSignal,
    PricePoint,
    build_market_signal,
)
from services.p2p_statistics_service import (
    STAT_PERIOD_HOUR,
    STAT_SCOPE_GLOBAL,
    normalize_side,
)


logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class RecommendationRecord:
    id: int
    exchange_id: int
    exchange_code: str
    crypto_currency_id: int
    crypto_code: str
    fiat_currency_id: int
    fiat_code: str
    action: str
    buy_price: Decimal | None
    sell_price: Decimal | None
    score: float
    confidence: float
    summary: str
    reasons: tuple[str, ...]
    risks: tuple[str, ...]
    observed_at: datetime


@dataclass
class MarketHistory:
    exchange_id: int
    exchange_code: str
    crypto_currency_id: int
    crypto_code: str
    fiat_currency_id: int
    fiat_code: str
    buy_points: list[PricePoint]
    sell_points: list[PricePoint]
    buy_price_is_fresh: bool
    sell_price_is_fresh: bool
    filter_hashes: set[str]


class P2PRecommendationService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        latest_scan_cutoff: datetime | None = None,
    ):
        self.session = session
        self.latest_scan_cutoff = latest_scan_cutoff

    async def generate_recommendations(
        self,
        *,
        pair_ids: set[tuple[int, int]] | None = None,
    ) -> list[RecommendationRecord]:
        if not can_call_openai():
            return []

        markets = await self.load_market_histories(pair_ids=pair_ids)
        recommendations = []
        macro_by_fiat = {}
        min_history_points = max(
            2,
            Config.P2P_RECOMMENDATION_MIN_HISTORY_POINTS,
        )

        for market in markets:
            if pair_ids is not None and (
                market.crypto_currency_id,
                market.fiat_currency_id,
            ) not in pair_ids:
                continue

            buy_points = market.buy_points if market.buy_price_is_fresh else []
            sell_points = market.sell_points if market.sell_price_is_fresh else []

            if not buy_points and not sell_points:
                continue

            if (
                len(buy_points) < min_history_points
                and len(sell_points) < min_history_points
            ):
                continue

            macro = macro_by_fiat.get(market.fiat_currency_id)

            if market.fiat_currency_id not in macro_by_fiat:
                macro = await self.get_or_refresh_macro_analysis(
                    market.fiat_currency_id,
                    market.fiat_code,
                    market.crypto_code,
                )
                macro_by_fiat[market.fiat_currency_id] = macro

            if (
                Config.P2P_RECOMMENDATION_WEB_SEARCH_ENABLED
                and macro is None
            ):
                continue

            signal = build_market_signal(
                buy_points,
                sell_points,
                min_history_points=min_history_points,
                signal_threshold=Config.P2P_RECOMMENDATION_SIGNAL_THRESHOLD,
                macro_impact_score=(
                    macro.impact_score * macro.confidence
                    if macro
                    else 0.0
                ),
            )

            if signal.action == ACTION_HOLD:
                continue

            if not await self.is_materially_new(market, signal):
                continue

            ai_result = await review_market_signal(
                exchange_code=market.exchange_code,
                crypto_code=market.crypto_code,
                fiat_code=market.fiat_code,
                signal=signal,
                macro_context=macro,
            )

            if ai_result is None:
                continue

            if (
                ai_result.action == ACTION_HOLD
                or ai_result.confidence < 0.55
            ):
                continue

            recommendation = await self.save_recommendation(
                market,
                signal,
                macro,
                ai_result,
            )
            recommendations.append(recommendation)

        await self.session.commit()
        return recommendations

    async def load_market_histories(
        self,
        *,
        pair_ids: set[tuple[int, int]] | None = None,
    ) -> list[MarketHistory]:
        latest_prices = await self.load_latest_market_prices(pair_ids=pair_ids)

        if not latest_prices:
            return []

        current_filter_hashes = {
            latest_price[3]
            for latest_price in latest_prices.values()
        }
        statement = (
            select(
                P2PPriceStatistic.side,
                P2PPriceStatistic.period_started_at,
                P2PPriceStatistic.min_price,
                P2PPriceStatistic.max_price,
                P2PPriceStatistic.filter_hash,
                P2PPriceStatistic.updated_at,
                Exchange.id,
                Exchange.code,
                CryptoCurrency.id,
                CryptoCurrency.code,
                FiatCurrency.id,
                FiatCurrency.code,
            )
            .join(Exchange, Exchange.id == P2PPriceStatistic.exchange_id)
            .join(
                CryptoCurrency,
                CryptoCurrency.id == P2PPriceStatistic.crypto_currency_id,
            )
            .join(FiatCurrency, FiatCurrency.id == P2PPriceStatistic.fiat_currency_id)
            .where(
                P2PPriceStatistic.scope == STAT_SCOPE_GLOBAL,
                P2PPriceStatistic.period_type == STAT_PERIOD_HOUR,
                P2PPriceStatistic.filter_hash.in_(current_filter_hashes),
                Exchange.is_active.is_(True),
            )
            .order_by(
                P2PPriceStatistic.period_started_at,
                P2PPriceStatistic.updated_at,
            )
        )

        if pair_ids is not None:
            statement = statement.where(
                tuple_(
                    P2PPriceStatistic.crypto_currency_id,
                    P2PPriceStatistic.fiat_currency_id,
                ).in_(pair_ids)
            )

        result = await self.session.stream(statement)
        grouped = {}

        async for row in result:
            (
                side,
                period_started_at,
                min_price,
                max_price,
                filter_hash,
                _updated_at,
                exchange_id,
                exchange_code,
                crypto_id,
                crypto_code,
                fiat_id,
                fiat_code,
            ) = row
            latest_price = latest_prices.get(
                (
                    exchange_id,
                    crypto_id,
                    fiat_id,
                    normalize_side(side),
                )
            )

            if latest_price is None or filter_hash != latest_price[3]:
                continue

            key = (exchange_id, crypto_id, fiat_id)
            market = grouped.setdefault(
                key,
                {
                    "exchange_id": exchange_id,
                    "exchange_code": exchange_code,
                    "crypto_currency_id": crypto_id,
                    "crypto_code": crypto_code,
                    "fiat_currency_id": fiat_id,
                    "fiat_code": fiat_code,
                    "points": {},
                    "filter_hashes": set(),
                },
            )
            market["points"][(side, period_started_at)] = (
                min_price,
                max_price,
            )
            market["filter_hashes"].add(filter_hash)

        histories = []

        for market in grouped.values():
            try:
                driver = get_p2p_exchange_driver(market["exchange_code"])
            except ValueError:
                logger.warning(
                    "Recommendation history skipped: unsupported exchange=%s",
                    market["exchange_code"],
                )
                continue

            buy_side = normalize_side(driver.fiat_to_crypto_side)
            sell_side = normalize_side(driver.crypto_to_fiat_side)
            buy_points = []
            sell_points = []

            for (side, observed_at), prices in market["points"].items():
                if normalize_side(side) == buy_side:
                    buy_points.append(
                        PricePoint(
                            observed_at=observed_at,
                            price=prices[0],
                        )
                    )
                elif normalize_side(side) == sell_side:
                    sell_points.append(
                        PricePoint(
                            observed_at=observed_at,
                            price=prices[1],
                        )
                    )

            latest_buy = latest_prices.get(
                (
                    market["exchange_id"],
                    market["crypto_currency_id"],
                    market["fiat_currency_id"],
                    buy_side,
                )
            )
            latest_sell = latest_prices.get(
                (
                    market["exchange_id"],
                    market["crypto_currency_id"],
                    market["fiat_currency_id"],
                    sell_side,
                )
            )
            buy_points, buy_price_is_fresh = merge_latest_scan_price(
                buy_points,
                latest_buy,
                prefer_min=True,
            )
            sell_points, sell_price_is_fresh = merge_latest_scan_price(
                sell_points,
                latest_sell,
                prefer_min=False,
            )
            histories.append(
                MarketHistory(
                    exchange_id=market["exchange_id"],
                    exchange_code=market["exchange_code"],
                    crypto_currency_id=market["crypto_currency_id"],
                    crypto_code=market["crypto_code"],
                    fiat_currency_id=market["fiat_currency_id"],
                    fiat_code=market["fiat_code"],
                    buy_points=buy_points,
                    sell_points=sell_points,
                    buy_price_is_fresh=buy_price_is_fresh,
                    sell_price_is_fresh=sell_price_is_fresh,
                    filter_hashes=market["filter_hashes"],
                )
            )

        return histories

    async def load_latest_market_prices(
        self,
        *,
        pair_ids: set[tuple[int, int]] | None = None,
    ) -> dict[
        tuple[int, int, int, str],
        tuple[datetime, Decimal, Decimal, str],
    ]:
        freshness_cutoff = utc_now() - timedelta(
            seconds=max(
                60,
                int(Config.P2P_RECOMMENDATION_MAX_DATA_AGE_SECONDS),
            )
        )

        if (
            self.latest_scan_cutoff is not None
            and self.latest_scan_cutoff > freshness_cutoff
        ):
            freshness_cutoff = self.latest_scan_cutoff

        latest_statement = (
            select(
                P2POffer.exchange_id.label("exchange_id"),
                P2POffer.crypto_currency_id.label("crypto_currency_id"),
                P2POffer.fiat_currency_id.label("fiat_currency_id"),
                P2POffer.side.label("side"),
                func.max(ScanBatch.started_at).label("observed_at"),
            )
            .join(ScanBatch, ScanBatch.id == P2POffer.scan_batch_id)
            .where(
                ScanBatch.scope == STAT_SCOPE_GLOBAL,
                ScanBatch.status == "done",
                ScanBatch.started_at >= freshness_cutoff,
            )
            .group_by(
                P2POffer.exchange_id,
                P2POffer.crypto_currency_id,
                P2POffer.fiat_currency_id,
                P2POffer.side,
            )
        )

        if pair_ids is not None:
            latest_statement = latest_statement.where(
                tuple_(
                    P2POffer.crypto_currency_id,
                    P2POffer.fiat_currency_id,
                ).in_(pair_ids)
            )

        latest_times = latest_statement.subquery()
        statement = (
            select(
                latest_times.c.exchange_id,
                latest_times.c.crypto_currency_id,
                latest_times.c.fiat_currency_id,
                latest_times.c.side,
                latest_times.c.observed_at,
                func.min(P2POffer.price),
                func.max(P2POffer.price),
                ScanBatch.filter_hash,
            )
            .select_from(latest_times)
            .join(
                ScanBatch,
                and_(
                    ScanBatch.exchange_id == latest_times.c.exchange_id,
                    ScanBatch.scope == STAT_SCOPE_GLOBAL,
                    ScanBatch.status == "done",
                    ScanBatch.started_at == latest_times.c.observed_at,
                ),
            )
            .join(
                P2POffer,
                and_(
                    P2POffer.scan_batch_id == ScanBatch.id,
                    P2POffer.exchange_id == latest_times.c.exchange_id,
                    P2POffer.crypto_currency_id
                    == latest_times.c.crypto_currency_id,
                    P2POffer.fiat_currency_id
                    == latest_times.c.fiat_currency_id,
                    P2POffer.side == latest_times.c.side,
                ),
            )
            .group_by(
                latest_times.c.exchange_id,
                latest_times.c.crypto_currency_id,
                latest_times.c.fiat_currency_id,
                latest_times.c.side,
                latest_times.c.observed_at,
                ScanBatch.filter_hash,
            )
        )
        result = await self.session.execute(statement)

        return {
            (
                exchange_id,
                crypto_currency_id,
                fiat_currency_id,
                normalize_side(side),
            ): (observed_at, min_price, max_price, filter_hash)
            for (
                exchange_id,
                crypto_currency_id,
                fiat_currency_id,
                side,
                observed_at,
                min_price,
                max_price,
                filter_hash,
            ) in result.all()
        }

    async def get_or_refresh_macro_analysis(
        self,
        fiat_currency_id: int,
        fiat_code: str,
        crypto_code: str,
    ) -> MacroAnalysisResult | None:
        now = utc_now()
        result = await self.session.execute(
            select(P2PMacroAnalysis)
            .where(
                P2PMacroAnalysis.fiat_currency_id == fiat_currency_id,
                P2PMacroAnalysis.valid_until > now,
            )
            .order_by(P2PMacroAnalysis.created_at.desc())
            .limit(1)
        )
        cached = result.scalar_one_or_none()

        if cached is not None:
            return macro_result_from_model(cached)

        analysis = await analyze_fiat_macro_context(fiat_code, crypto_code)

        if analysis is None:
            return None

        model = P2PMacroAnalysis(
            fiat_currency_id=fiat_currency_id,
            model=analysis.model,
            impact_score=Decimal(str(analysis.impact_score)),
            confidence=Decimal(str(analysis.confidence)),
            summary=analysis.summary,
            factors=list(analysis.factors),
            sources=list(analysis.sources),
            created_at=now,
            valid_until=now + timedelta(
                seconds=max(300, Config.P2P_RECOMMENDATION_NEWS_REFRESH_SECONDS)
            ),
        )
        self.session.add(model)
        await self.session.flush()

        return analysis

    async def is_materially_new(
        self,
        market: MarketHistory,
        signal: MarketSignal,
    ) -> bool:
        cutoff = utc_now() - timedelta(
            seconds=max(
                60,
                Config.P2P_RECOMMENDATION_NOTIFICATION_COOLDOWN_SECONDS,
            )
        )
        result = await self.session.execute(
            select(P2PMarketRecommendation)
            .where(
                P2PMarketRecommendation.exchange_id == market.exchange_id,
                P2PMarketRecommendation.crypto_currency_id
                == market.crypto_currency_id,
                P2PMarketRecommendation.fiat_currency_id
                == market.fiat_currency_id,
                P2PMarketRecommendation.action == signal.action,
                P2PMarketRecommendation.filter_hash
                == hash_filter_set(market.filter_hashes),
                P2PMarketRecommendation.observed_at >= cutoff,
            )
            .order_by(P2PMarketRecommendation.observed_at.desc())
            .limit(1)
        )
        previous = result.scalar_one_or_none()

        if previous is None:
            return True

        current_price = (
            signal.current_buy_price
            if signal.action == ACTION_BUY
            else signal.current_sell_price
        )
        previous_price = (
            previous.buy_price
            if signal.action == ACTION_BUY
            else previous.sell_price
        )

        if current_price is None or previous_price is None or previous_price <= 0:
            return float(signal.score) >= float(previous.score) + 0.03

        if signal.action == ACTION_BUY:
            improvement = float((previous_price - current_price) / previous_price)
        else:
            improvement = float((current_price - previous_price) / previous_price)

        return improvement >= 0.002 or float(signal.score) >= float(previous.score) + 0.03

    async def save_recommendation(
        self,
        market: MarketHistory,
        signal: MarketSignal,
        macro: MacroAnalysisResult | None,
        ai_result: AIRecommendationResult | None,
    ) -> RecommendationRecord:
        observed_at = utc_now()
        confidence = ai_result.confidence if ai_result else signal.score
        summary = (
            ai_result.summary
            if ai_result and ai_result.summary
            else build_fallback_summary(signal)
        )
        reasons = (
            ai_result.reasons
            if ai_result and ai_result.reasons
            else signal.reasons
        )
        risks = ai_result.risks if ai_result else ()
        filter_hash = hash_filter_set(market.filter_hashes)
        macro_model_id = await self.find_macro_model_id(
            market.fiat_currency_id,
            macro,
        )
        model = P2PMarketRecommendation(
            exchange_id=market.exchange_id,
            crypto_currency_id=market.crypto_currency_id,
            fiat_currency_id=market.fiat_currency_id,
            macro_analysis_id=macro_model_id,
            action=signal.action,
            buy_price=signal.current_buy_price,
            sell_price=signal.current_sell_price,
            score=Decimal(str(signal.score)),
            confidence=Decimal(str(confidence)),
            summary=summary,
            reasons=list(reasons),
            risks=list(risks),
            feature_payload=signal.as_payload(),
            filter_hash=filter_hash,
            model=ai_result.model if ai_result else None,
            observed_at=observed_at,
        )
        self.session.add(model)
        await self.session.flush()

        return RecommendationRecord(
            id=model.id,
            exchange_id=market.exchange_id,
            exchange_code=market.exchange_code,
            crypto_currency_id=market.crypto_currency_id,
            crypto_code=market.crypto_code,
            fiat_currency_id=market.fiat_currency_id,
            fiat_code=market.fiat_code,
            action=signal.action,
            buy_price=signal.current_buy_price,
            sell_price=signal.current_sell_price,
            score=signal.score,
            confidence=confidence,
            summary=summary,
            reasons=tuple(reasons),
            risks=tuple(risks),
            observed_at=observed_at,
        )

    async def find_macro_model_id(
        self,
        fiat_currency_id: int,
        macro: MacroAnalysisResult | None,
    ) -> int | None:
        if macro is None:
            return None

        result = await self.session.execute(
            select(P2PMacroAnalysis.id)
            .where(P2PMacroAnalysis.fiat_currency_id == fiat_currency_id)
            .order_by(P2PMacroAnalysis.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


def macro_result_from_model(model: P2PMacroAnalysis) -> MacroAnalysisResult:
    return MacroAnalysisResult(
        impact_score=float(model.impact_score),
        confidence=float(model.confidence),
        summary=model.summary,
        factors=tuple(model.factors or []),
        sources=tuple(model.sources or []),
        model=model.model or "",
    )


def hash_filter_set(filter_hashes: set[str]) -> str:
    value = ":".join(sorted(filter_hashes)) or "default"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_fallback_summary(signal: MarketSignal) -> str:
    if signal.action == ACTION_BUY:
        return "Ціна перебуває у нижній частині історичного діапазону."

    if signal.action == ACTION_SELL:
        return "Ціна перебуває у верхній частині історичного діапазону."

    return "Сильного ринкового сигналу немає."


def merge_latest_scan_price(
    points: list[PricePoint],
    latest: tuple[datetime, Decimal, Decimal, str] | None,
    *,
    prefer_min: bool,
) -> tuple[list[PricePoint], bool]:
    points = sorted(points, key=lambda point: point.observed_at)

    if latest is None:
        return points, False

    observed_at, min_price, max_price, _filter_hash = latest
    period_started_at = observed_at.replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    period_ended_at = period_started_at + timedelta(hours=1)
    points = [
        point
        for point in points
        if not period_started_at <= point.observed_at < period_ended_at
    ]
    points.append(
        PricePoint(
            observed_at=observed_at,
            price=min_price if prefer_min else max_price,
        )
    )
    max_age = max(
        60,
        int(Config.P2P_RECOMMENDATION_MAX_DATA_AGE_SECONDS),
    )
    age_seconds = (utc_now() - observed_at).total_seconds()
    return (
        sorted(points, key=lambda point: point.observed_at),
        age_seconds <= max_age,
    )
