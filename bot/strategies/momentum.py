"""Dual momentum rotation: hold the strongest trending assets, step aside when nothing is trending."""
from __future__ import annotations

import pandas as pd

from .base import Strategy
from .simple import hold_between_rebalances


class DualMomentum(Strategy):
    """At each month end, rank symbols by their trailing return and hold the top `top_n` equally.

    - Relative momentum: prefer whatever has risen the most over `lookback` bars.
    - Absolute momentum: only hold a pick if its own trailing return is positive (and, with
      `sma` > 0, its price is above that SMA). Unfilled slots stay in cash.
    - `skip` bars are left out of the lookback (the classic "12-1" momentum skips the last month).
    """

    def __init__(self, lookback: int = 126, top_n: int = 2, skip: int = 0, sma: int = 0):
        self.lookback, self.top_n, self.skip, self.sma = lookback, top_n, skip, sma
        self.warmup = max(lookback + skip, sma)

    def weights(self, bars: dict[str, pd.DataFrame]) -> pd.DataFrame:
        close = pd.DataFrame({s: df["close"] for s, df in bars.items()})
        mom = close.shift(self.skip) / close.shift(self.skip + self.lookback) - 1
        eligible = mom > 0
        if self.sma:
            eligible &= close > close.rolling(self.sma).mean()
        rank = mom.where(eligible).rank(axis=1, ascending=False, method="first")
        w = (rank <= self.top_n).astype(float) / self.top_n
        w.iloc[: self.warmup] = 0.0
        return hold_between_rebalances(w)
