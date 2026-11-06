from __future__ import annotations

from abc import ABC

import pandas as pd


class Strategy(ABC):
    """A strategy turns bars into target portfolio weights.

    `weights(bars)` returns a DataFrame (index = timestamps, columns = symbols) where each value is the
    fraction of equity to hold in that symbol, from 0 to 1, summing to at most 1 per row.

    Rule: the row at bar t may only use data up to and including bar t. The engine trades at the
    OPEN of bar t+1, so there is no look-ahead.

    Simple per-symbol strategies only implement `signal(bars) -> Series` of 0..1 exposure; the default
    `weights` then splits equity equally across symbols.
    """

    warmup: int = 0  # bars needed before the output is meaningful

    def signal(self, bars: pd.DataFrame) -> pd.Series:
        raise NotImplementedError

    def weights(self, bars: dict[str, pd.DataFrame]) -> pd.DataFrame:
        n = len(bars)
        return pd.DataFrame({s: self.signal(df) / n for s, df in bars.items()})
