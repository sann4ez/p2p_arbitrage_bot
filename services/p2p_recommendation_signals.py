from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from statistics import fmean


ACTION_BUY = "BUY"
ACTION_SELL = "SELL"
ACTION_HOLD = "HOLD"


@dataclass(frozen=True)
class PricePoint:
    observed_at: datetime
    price: Decimal


@dataclass(frozen=True)
class MarketSignal:
    action: str
    score: float
    buy_score: float
    sell_score: float
    current_buy_price: Decimal | None
    current_sell_price: Decimal | None
    buy_percentile_all: float | None
    sell_percentile_all: float | None
    buy_percentile_30d: float | None
    sell_percentile_30d: float | None
    buy_relative_percentile_all: float | None
    sell_relative_percentile_all: float | None
    buy_monthly_cycle_percentile: float | None
    sell_monthly_cycle_percentile: float | None
    buy_mean_30d: float | None
    sell_mean_30d: float | None
    spread_percent: float | None
    history_started_at: datetime | None
    history_ended_at: datetime | None
    buy_points_count: int
    sell_points_count: int
    reasons: tuple[str, ...]

    def as_payload(self) -> dict:
        return {
            "action": self.action,
            "score": round(self.score, 5),
            "buy_score": round(self.buy_score, 5),
            "sell_score": round(self.sell_score, 5),
            "current_buy_price": decimal_text(self.current_buy_price),
            "current_sell_price": decimal_text(self.current_sell_price),
            "buy_percentile_all": optional_round(self.buy_percentile_all),
            "sell_percentile_all": optional_round(self.sell_percentile_all),
            "buy_percentile_30d": optional_round(self.buy_percentile_30d),
            "sell_percentile_30d": optional_round(self.sell_percentile_30d),
            "buy_relative_percentile_all": optional_round(
                self.buy_relative_percentile_all
            ),
            "sell_relative_percentile_all": optional_round(
                self.sell_relative_percentile_all
            ),
            "buy_monthly_cycle_percentile": optional_round(
                self.buy_monthly_cycle_percentile
            ),
            "sell_monthly_cycle_percentile": optional_round(
                self.sell_monthly_cycle_percentile
            ),
            "buy_mean_30d": optional_round(self.buy_mean_30d, 6),
            "sell_mean_30d": optional_round(self.sell_mean_30d, 6),
            "spread_percent": optional_round(self.spread_percent, 4),
            "history_started_at": datetime_text(self.history_started_at),
            "history_ended_at": datetime_text(self.history_ended_at),
            "buy_points_count": self.buy_points_count,
            "sell_points_count": self.sell_points_count,
            "reasons": list(self.reasons),
        }


def build_market_signal(
    buy_points: list[PricePoint],
    sell_points: list[PricePoint],
    *,
    min_history_points: int = 24,
    signal_threshold: float = 0.72,
    macro_impact_score: float = 0.0,
) -> MarketSignal:
    buy_points = sorted(buy_points, key=lambda point: point.observed_at)
    sell_points = sorted(sell_points, key=lambda point: point.observed_at)
    all_points = buy_points + sell_points
    history_started_at = min(
        (point.observed_at for point in all_points),
        default=None,
    )
    history_ended_at = max(
        (point.observed_at for point in all_points),
        default=None,
    )
    buy_metrics = calculate_side_metrics(buy_points)
    sell_metrics = calculate_side_metrics(sell_points)
    buy_ready = len(buy_points) >= max(2, min_history_points)
    sell_ready = len(sell_points) >= max(2, min_history_points)
    buy_score = calculate_direction_score(
        buy_metrics,
        prefer_low=True,
        macro_impact_score=macro_impact_score,
    ) if buy_ready else 0.0
    sell_score = calculate_direction_score(
        sell_metrics,
        prefer_low=False,
        macro_impact_score=macro_impact_score,
    ) if sell_ready else 0.0
    action = ACTION_HOLD
    score = max(buy_score, sell_score)

    if score >= clamp(signal_threshold):
        action = ACTION_BUY if buy_score >= sell_score else ACTION_SELL

    current_buy_price = latest_price(buy_points)
    current_sell_price = latest_price(sell_points)
    spread_percent = calculate_spread_percent(
        current_buy_price,
        current_sell_price,
    )
    reasons = build_signal_reasons(
        action=action,
        metrics=buy_metrics if action == ACTION_BUY else sell_metrics,
        points_count=(
            len(buy_points)
            if action == ACTION_BUY
            else len(sell_points)
        ),
        min_history_points=min_history_points,
    )

    return MarketSignal(
        action=action,
        score=score,
        buy_score=buy_score,
        sell_score=sell_score,
        current_buy_price=current_buy_price,
        current_sell_price=current_sell_price,
        buy_percentile_all=buy_metrics.get("percentile_all"),
        sell_percentile_all=sell_metrics.get("percentile_all"),
        buy_percentile_30d=buy_metrics.get("percentile_30d"),
        sell_percentile_30d=sell_metrics.get("percentile_30d"),
        buy_relative_percentile_all=buy_metrics.get("relative_percentile_all"),
        sell_relative_percentile_all=sell_metrics.get("relative_percentile_all"),
        buy_monthly_cycle_percentile=buy_metrics.get(
            "monthly_cycle_percentile"
        ),
        sell_monthly_cycle_percentile=sell_metrics.get(
            "monthly_cycle_percentile"
        ),
        buy_mean_30d=buy_metrics.get("mean_30d"),
        sell_mean_30d=sell_metrics.get("mean_30d"),
        spread_percent=spread_percent,
        history_started_at=history_started_at,
        history_ended_at=history_ended_at,
        buy_points_count=len(buy_points),
        sell_points_count=len(sell_points),
        reasons=tuple(reasons),
    )


def calculate_side_metrics(points: list[PricePoint]) -> dict:
    if not points:
        return {}

    current_point = points[-1]
    values_all = [float(point.price) for point in points]
    cutoff = current_point.observed_at - timedelta(days=30)
    values_30d = [
        float(point.price)
        for point in points
        if point.observed_at >= cutoff
    ] or values_all
    current = float(current_point.price)
    mean_30d = fmean(values_30d)

    return {
        "current": current,
        "percentile_all": percentile_rank(values_all, current),
        "percentile_30d": percentile_rank(values_30d, current),
        "relative_percentile_all": rolling_deviation_percentile(points),
        "monthly_cycle_percentile": monthly_cycle_percentile(points),
        "mean_30d": mean_30d,
        "deviation_30d": safe_ratio(current - mean_30d, mean_30d),
    }


def calculate_direction_score(
    metrics: dict,
    *,
    prefer_low: bool,
    macro_impact_score: float,
) -> float:
    if not metrics:
        return 0.0

    relative_percentile_all = metrics["relative_percentile_all"]
    percentile_30d = metrics["percentile_30d"]
    monthly_cycle_percentile = metrics["monthly_cycle_percentile"]
    deviation = metrics["deviation_30d"]

    if prefer_low:
        recent_component = 1.0 - percentile_30d
        history_component = 1.0 - relative_percentile_all
        seasonal_component = 1.0 - monthly_cycle_percentile
        deviation_component = clamp(-deviation / 0.03)
        macro_component = clamp(max(0.0, macro_impact_score))
    else:
        recent_component = percentile_30d
        history_component = relative_percentile_all
        seasonal_component = monthly_cycle_percentile
        deviation_component = clamp(deviation / 0.03)
        macro_component = clamp(max(0.0, -macro_impact_score))

    return clamp(
        recent_component * 0.30
        + history_component * 0.25
        + seasonal_component * 0.25
        + deviation_component * 0.10
        + macro_component * 0.10
    )


def build_signal_reasons(
    *,
    action: str,
    metrics: dict,
    points_count: int,
    min_history_points: int,
) -> list[str]:
    if not metrics or points_count < min_history_points:
        return [
            f"Недостатньо історії: {points_count} із {min_history_points} точок."
        ]

    percentile_30d = metrics["percentile_30d"]
    relative_percentile_all = metrics["relative_percentile_all"]
    monthly_cycle = metrics["monthly_cycle_percentile"]
    deviation_percent = metrics["deviation_30d"] * 100

    if action == ACTION_BUY:
        return [
            f"Поточна ціна нижча за {round((1 - percentile_30d) * 100)}% точок за 30 днів.",
            (
                "Позиція у всій історії після корекції локального тренду: "
                f"{round(relative_percentile_all * 100)}-й перцентиль."
            ),
            (
                "Сезонність поточного дня місяця: "
                f"{round(monthly_cycle * 100)}-й перцентиль."
            ),
            f"Відхилення від середньої за 30 днів: {deviation_percent:.2f}%.",
        ]

    if action == ACTION_SELL:
        return [
            f"Поточна ціна вища за {round(percentile_30d * 100)}% точок за 30 днів.",
            (
                "Позиція у всій історії після корекції локального тренду: "
                f"{round(relative_percentile_all * 100)}-й перцентиль."
            ),
            (
                "Сезонність поточного дня місяця: "
                f"{round(monthly_cycle * 100)}-й перцентиль."
            ),
            f"Відхилення від середньої за 30 днів: {deviation_percent:.2f}%.",
        ]

    return [
        "Поточна ціна ще не досягла порогу сильного BUY або SELL сигналу."
    ]


def percentile_rank(values: list[float], current: float) -> float:
    if not values:
        return 0.5

    lower = sum(value < current for value in values)
    equal = sum(value == current for value in values)
    return clamp((lower + equal * 0.5) / len(values))


def rolling_deviation_percentile(points: list[PricePoint]) -> float:
    if not points:
        return 0.5

    window = deque()
    window_sum = 0.0
    deviations = []

    for point in points:
        current = float(point.price)
        cutoff = point.observed_at - timedelta(days=30)

        while window and window[0][0] < cutoff:
            _, expired = window.popleft()
            window_sum -= expired

        window.append((point.observed_at, current))
        window_sum += current
        baseline = window_sum / len(window)
        deviations.append(safe_ratio(current - baseline, baseline))

    return percentile_rank(deviations, deviations[-1])


def monthly_cycle_percentile(points: list[PricePoint]) -> float:
    if not points:
        return 0.5

    current = points[-1]
    current_month = (current.observed_at.year, current.observed_at.month)
    daily_sums = defaultdict(float)
    daily_counts = defaultdict(int)

    for point in points:
        month_key = (point.observed_at.year, point.observed_at.month)

        if month_key >= current_month:
            continue

        key = (month_key, point.observed_at.day)
        daily_sums[key] += float(point.price)
        daily_counts[key] += 1

    monthly_days = defaultdict(dict)

    for (month_key, day), total in daily_sums.items():
        monthly_days[month_key][day] = total / daily_counts[(month_key, day)]

    if len(monthly_days) < 2:
        return 0.5

    ratios_by_day = defaultdict(list)

    for day_prices in monthly_days.values():
        if len(day_prices) < 5:
            continue

        month_mean = fmean(day_prices.values())

        if month_mean <= 0:
            continue

        for day, price in day_prices.items():
            ratios_by_day[day].append(price / month_mean)

    day_profile = {
        day: fmean(ratios)
        for day, ratios in ratios_by_day.items()
        if ratios
    }

    if len(day_profile) < 10:
        return 0.5

    current_day_values = [
        ratio
        for day, ratio in day_profile.items()
        if day_of_month_distance(day, current.observed_at.day) <= 2
    ]

    if not current_day_values:
        return 0.5

    return percentile_rank(
        list(day_profile.values()),
        fmean(current_day_values),
    )


def day_of_month_distance(first: int, second: int) -> int:
    direct = abs(first - second)
    return min(direct, 31 - direct)


def calculate_spread_percent(
    buy_price: Decimal | None,
    sell_price: Decimal | None,
) -> float | None:
    if buy_price is None or sell_price is None or buy_price <= 0:
        return None

    return float((sell_price - buy_price) / buy_price * Decimal("100"))


def latest_price(points: list[PricePoint]) -> Decimal | None:
    return points[-1].price if points else None


def safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def decimal_text(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def datetime_text(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def optional_round(value: float | None, digits: int = 5) -> float | None:
    return round(value, digits) if value is not None else None
