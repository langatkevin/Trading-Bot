from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    """A strategy turns bars into a desired exposure per bar, from 0.0 (flat) to 1.0 (fully long).

    Rule: the value at bar t may only use data up to and including bar t. The engine then trades
    at the OPEN of bar t+1, so there is no look-ahead.
    """

    warmup: int = 0  # bars needed before the signal is meaningful

    @abstractmethod
    def signal(self, bars: pd.DataFrame) -> pd.Series:
        ...
