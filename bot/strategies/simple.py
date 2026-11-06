"""Baselines: buy-and-hold and a plain trend filter."""
from __future__ import annotations

import pandas as pd

from .base import Strategy


class BuyAndHold(Strategy):
    """Always fully invested, equal weight. The benchmark every strategy has to beat."""

    def signal(self, bars: pd.DataFrame) -> pd.Series:
        return pd.Series(1.0, index=bars.index)


class TrendFilter(Strategy):
    """Equal weight; hold a symbol while its close is above its N-day SMA, otherwise that slice is cash."""

    def __init__(self, sma: int = 200, check: str = "monthly"):
        self.sma = sma
        self.check = check
        self.warmup = sma

    def signal(self, bars: pd.DataFrame) -> pd.Series:
        close = bars["close"]
        sig = (close > close.rolling(self.sma).mean()).astype(float)
        sig.iloc[: self.warmup] = 0.0
        if self.check == "monthly":
            sig = hold_between_rebalances(sig)
        return sig


def month_end_mask(index: pd.DatetimeIndex) -> pd.Series:
    """True on the last bar of each calendar month present in the index."""
    naive = index if index.tz is None else index.tz_convert(None)
    period = pd.Series(naive.to_period("M"), index=index)
    mask = period != period.shift(-1)
    if len(index):
        # The newest bar: we can't see the next bar yet, so ask the calendar instead.
        nxt = naive[-1] + pd.offsets.BDay(1)
        mask.iloc[-1] = nxt.month != naive[-1].month
    return mask


def hold_between_rebalances(values: pd.Series | pd.DataFrame):
    """Keep values only on month-end bars and carry them forward, so trading happens monthly."""
    mask = month_end_mask(values.index)
    if isinstance(values, pd.Series):
        out = values.where(mask)
    else:
        out = values.where(mask, axis=0)
    return out.ffill().fillna(0.0)
