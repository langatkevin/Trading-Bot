from __future__ import annotations

import pandas as pd

from .base import Strategy


class SmaCrossover(Strategy):
    """Long when the fast SMA is above the slow SMA (and price is above the trend SMA); flat otherwise.

    A baseline to prove the pipeline end to end, not a strategy expected to beat the market.
    """

    def __init__(self, fast: int = 20, slow: int = 50, trend: int = 200):
        if fast >= slow:
            raise ValueError("fast must be shorter than slow")
        self.fast, self.slow, self.trend = fast, slow, trend
        self.warmup = max(slow, trend)

    def signal(self, bars: pd.DataFrame) -> pd.Series:
        close = bars["close"]
        fast = close.rolling(self.fast).mean()
        slow = close.rolling(self.slow).mean()
        long = fast > slow
        if self.trend:
            long &= close > close.rolling(self.trend).mean()
        sig = long.astype(float)
        sig.iloc[: self.warmup] = 0.0
        return sig
