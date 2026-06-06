from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import os
from typing import Iterable

from db.dto import P2PPriceStatisticView
from services.p2p_statistics_service import (
    STAT_PERIOD_DAY,
    STAT_PERIOD_HOUR,
    STAT_PERIOD_LABELS,
    STAT_PERIOD_MONTH,
    STAT_PERIOD_WEEK,
    STAT_PERIOD_YEAR,
)
from services.time_utils import display_datetime


CHART_WIDTH = 1200
CHART_HEIGHT = 720
PLOT_LEFT = 96
PLOT_TOP = 150
PLOT_RIGHT = 1130
PLOT_BOTTOM = 590
CHART_COLORS = (
    "#f0b90b",
    "#2563eb",
    "#16a34a",
    "#dc2626",
    "#9333ea",
    "#0891b2",
)


def render_p2p_statistics_chart(
    stats: Iterable[P2PPriceStatisticView],
    period_type: str,
    periods: Iterable[datetime] | None = None,
) -> bytes:
    Image, ImageDraw, ImageFont = load_pillow()
    items = sorted(list(stats), key=lambda item: item.period_started_at)

    if not items:
        return render_empty_chart(Image, ImageDraw, ImageFont, period_type)

    image = Image.new("RGB", (CHART_WIDTH, CHART_HEIGHT), "#ffffff")
    draw = ImageDraw.Draw(image)
    title_font = load_font(ImageFont, 34, bold=True)
    subtitle_font = load_font(ImageFont, 20)
    label_font = load_font(ImageFont, 18)
    small_font = load_font(ImageFont, 15)

    draw.text(
        (52, 28),
        f"P2P статистика · {STAT_PERIOD_LABELS.get(period_type, period_type)}",
        fill="#111827",
        font=title_font,
    )
    draw.text(
        (52, 72),
        "Лінія показує медіанний курс за обраними парами",
        fill="#4b5563",
        font=subtitle_font,
    )

    periods = build_chart_periods(items, periods)
    values = [decimal_to_float(item.median_price) for item in items]
    y_min, y_max = get_y_bounds(values)

    draw_grid(draw, label_font, periods, y_min, y_max, period_type)
    draw_series(draw, items, periods, y_min, y_max, small_font)
    draw_legend(draw, small_font, group_statistics(items))

    draw.text(
        (PLOT_LEFT, CHART_HEIGHT - 78),
        "Мін/макс по вертикалі рахуються з видимих точок графіка.",
        fill="#6b7280",
        font=small_font,
    )

    return image_to_png_bytes(image)


def build_chart_periods(
    items: list[P2PPriceStatisticView],
    periods: Iterable[datetime] | None = None,
) -> list[datetime]:
    item_periods = {item.period_started_at for item in items}

    if periods is None:
        return sorted(item_periods)

    return sorted(set(periods) | item_periods)


def build_p2p_statistics_caption(
    stats: Iterable[P2PPriceStatisticView],
    period_type: str,
) -> str:
    items = list(stats)
    period_label = STAT_PERIOD_LABELS.get(period_type, period_type)
    series_count = len(group_statistics(items))
    pairs = ", ".join(sorted({item.pair_label for item in items})[:5])

    if not pairs:
        pairs = "немає даних"

    return (
        f"📊 Статистика P2P · {period_label}\n"
        f"Показник: медіанний курс. Серій: {series_count}. Точок: {len(items)}.\n"
        f"Пари: {pairs}"
    )


def load_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as error:
        raise RuntimeError(
            "Для графіків потрібен пакет Pillow. Встановіть залежності з requirements.txt."
        ) from error

    return Image, ImageDraw, ImageFont


def load_font(ImageFont, size: int, *, bold: bool = False):
    font_names = (
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf",
        "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "ARIALUNI.TTF",
    )
    font_dirs = (
        r"C:\Windows\Fonts",
        "/usr/share/fonts",
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/truetype/noto",
        "/usr/share/fonts/truetype/liberation2",
        "/app/.fonts",
        "/app/fonts",
    )

    for font_path in iter_font_paths(font_dirs, font_names):
        return ImageFont.truetype(font_path, size=size)

    for font_name in font_names:
        try:
            return ImageFont.truetype(font_name, size=size)
        except OSError:
            continue

    raise RuntimeError(
        "Не знайдено Unicode-шрифт для графіка. Встановіть DejaVu/Noto fonts або додайте .ttf у /app/fonts."
    )


def iter_font_paths(font_dirs: tuple[str, ...], font_names: tuple[str, ...]):
    normalized_names = {font_name.lower() for font_name in font_names}

    for font_dir in font_dirs:
        if not os.path.isdir(font_dir):
            continue

        for font_name in font_names:
            font_path = os.path.join(font_dir, font_name)

            if os.path.exists(font_path):
                yield font_path

        for root, _, files in os.walk(font_dir):
            for file_name in files:
                if file_name.lower() in normalized_names:
                    yield os.path.join(root, file_name)


def render_empty_chart(Image, ImageDraw, ImageFont, period_type: str) -> bytes:
    image = Image.new("RGB", (CHART_WIDTH, CHART_HEIGHT), "#ffffff")
    draw = ImageDraw.Draw(image)
    title_font = load_font(ImageFont, 34, bold=True)
    label_font = load_font(ImageFont, 20)
    period_label = STAT_PERIOD_LABELS.get(period_type, period_type)

    draw.text(
        (52, 28),
        f"P2P статистика · {period_label}",
        fill="#111827",
        font=title_font,
    )
    draw.text(
        (52, 105),
        "Поки немає даних для побудови графіка.",
        fill="#4b5563",
        font=label_font,
    )

    return image_to_png_bytes(image)


def draw_grid(draw, font, periods, y_min: float, y_max: float, period_type: str):
    draw.rectangle(
        (PLOT_LEFT, PLOT_TOP, PLOT_RIGHT, PLOT_BOTTOM),
        outline="#d1d5db",
        width=1,
    )

    for index in range(6):
        value = y_min + (y_max - y_min) * index / 5
        y = y_for_value(value, y_min, y_max)
        draw.line((PLOT_LEFT, y, PLOT_RIGHT, y), fill="#e5e7eb", width=1)
        label = format_price(value)
        text_width = text_size(draw, label, font)[0]
        draw.text(
            (PLOT_LEFT - text_width - 14, y - 10),
            label,
            fill="#374151",
            font=font,
        )

    if not periods:
        return

    tick_indexes = get_tick_indexes(len(periods), max_ticks=6)

    for index in tick_indexes:
        period = periods[index]
        x = x_for_period(period, periods)
        draw.line((x, PLOT_BOTTOM, x, PLOT_BOTTOM + 8), fill="#9ca3af", width=1)
        label = format_period_label(period, period_type)
        text_width = text_size(draw, label, font)[0]
        draw.text(
            (x - text_width / 2, PLOT_BOTTOM + 16),
            label,
            fill="#374151",
            font=font,
        )


def draw_series(draw, items, periods, y_min: float, y_max: float, label_font):
    grouped = group_statistics(items)

    for index, (_, series_items) in enumerate(grouped.items()):
        color = CHART_COLORS[index % len(CHART_COLORS)]
        point_items = sorted(series_items, key=lambda item: item.period_started_at)
        points = [
            build_chart_point(item, periods, y_min, y_max)
            for item in point_items
        ]

        line_points = [(point["x"], point["y"]) for point in points]

        if len(line_points) > 1:
            draw.line(line_points, fill=color, width=4, joint="curve")

        for point in points:
            x = point["x"]
            y = point["y"]
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color, outline="#ffffff", width=2)
            draw_point_value_label(draw, point["label"], x, y, label_font, color)


def build_chart_point(item, periods, y_min: float, y_max: float) -> dict:
    median_price = decimal_to_float(item.median_price)

    return {
        "x": x_for_period(item.period_started_at, periods),
        "y": y_for_value(median_price, y_min, y_max),
        "label": format_decimal_price(item.median_price),
    }


def draw_point_value_label(draw, label: str, x: float, y: float, font, color: str):
    text_width, text_height = text_size(draw, label, font)
    padding_x = 5
    padding_y = 3
    label_x = max(PLOT_LEFT, min(PLOT_RIGHT - text_width, x - text_width / 2))
    label_y = y - text_height - 14

    if label_y < PLOT_TOP + 4:
        label_y = y + 12

    box = (
        label_x - padding_x,
        label_y - padding_y,
        label_x + text_width + padding_x,
        label_y + text_height + padding_y,
    )
    draw.rectangle(box, fill="#ffffff", outline=color, width=1)
    draw.text((label_x, label_y), label, fill="#111827", font=font)


def draw_legend(draw, font, grouped):
    legend_x = PLOT_LEFT
    legend_y = 114
    line_height = 24

    for index, label in enumerate(grouped.keys()):
        color = CHART_COLORS[index % len(CHART_COLORS)]
        label_width = text_size(draw, label, font)[0]

        if legend_x + label_width + 54 > PLOT_RIGHT:
            legend_x = PLOT_LEFT
            legend_y += line_height

        draw.line(
            (legend_x, legend_y + 9, legend_x + 24, legend_y + 9),
            fill=color,
            width=4,
        )
        draw.text((legend_x + 32, legend_y), label, fill="#111827", font=font)
        legend_x += label_width + 72


def group_statistics(items):
    grouped = defaultdict(list)

    for item in items:
        grouped[format_series_label(item)].append(item)

    return dict(grouped)


def x_for_period(period: datetime, periods: list[datetime]) -> float:
    if len(periods) <= 1:
        return (PLOT_LEFT + PLOT_RIGHT) / 2

    index = periods.index(period)
    return PLOT_LEFT + (PLOT_RIGHT - PLOT_LEFT) * index / (len(periods) - 1)


def y_for_value(value: float, y_min: float, y_max: float) -> float:
    if y_max == y_min:
        return (PLOT_TOP + PLOT_BOTTOM) / 2

    return PLOT_BOTTOM - (PLOT_BOTTOM - PLOT_TOP) * (value - y_min) / (y_max - y_min)


def get_y_bounds(values: list[float]) -> tuple[float, float]:
    y_min = min(values)
    y_max = max(values)

    if y_min == y_max:
        padding = max(abs(y_min) * 0.01, 0.01)
    else:
        padding = (y_max - y_min) * 0.08

    return y_min - padding, y_max + padding


def get_tick_indexes(count: int, *, max_ticks: int) -> list[int]:
    if count <= max_ticks:
        return list(range(count))

    return sorted(
        {
            round(index * (count - 1) / (max_ticks - 1))
            for index in range(max_ticks)
        }
    )


def format_series_label(item: P2PPriceStatisticView) -> str:
    return (
        f"{item.exchange_code} · "
        f"{item.pair_label} · "
        f"{format_side(item.side, item.exchange_code)}"
    )


def format_side(side: str, exchange_code: str | None = None) -> str:
    if str(exchange_code or "").upper() == "OKX":
        labels = {
            "BUY": "продаж",
            "SELL": "купівля",
        }
    else:
        labels = {
            "BUY": "купівля",
            "SELL": "продаж",
        }

    return labels.get(str(side).upper(), str(side).lower())


def format_period_label(value: datetime, period_type: str) -> str:
    value = display_datetime(value)

    if period_type == STAT_PERIOD_HOUR:
        return value.strftime("%d.%m %H:%M")

    if period_type in (STAT_PERIOD_DAY, STAT_PERIOD_WEEK):
        return value.strftime("%d.%m")

    if period_type == STAT_PERIOD_MONTH:
        return value.strftime("%m.%Y")

    if period_type == STAT_PERIOD_YEAR:
        return value.strftime("%Y")

    return value.strftime("%d.%m.%Y")


def format_price(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def format_decimal_price(value: Decimal) -> str:
    return format(value.normalize(), "f").rstrip("0").rstrip(".") or "0"


def decimal_to_float(value: Decimal) -> float:
    return float(value)


def text_size(draw, text: str, font) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def image_to_png_bytes(image) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
