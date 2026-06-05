from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class P2PPriceStatisticView:
    exchange_code: str
    crypto_code: str
    fiat_code: str
    side: str
    period_type: str
    period_started_at: datetime
    period_ended_at: datetime
    min_price: Decimal
    max_price: Decimal
    avg_price: Decimal
    median_price: Decimal
    offers_count: int
    scans_count: int
    scope: str = "global"
    filter_hash: str = "default"

    @property
    def pair_label(self) -> str:
        return f"{self.crypto_code}/{self.fiat_code}"
