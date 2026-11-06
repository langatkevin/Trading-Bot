"""Historical bar data: Alpaca download with a local CSV cache, plus synthetic data for offline tests."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

CACHE_DIR = Path("data_cache")
COLUMNS = ["open", "high", "low", "close", "volume"]


def _alpaca_timeframe(tf: str):
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    units = {"Min": TimeFrameUnit.Minute, "Hour": TimeFrameUnit.Hour, "Day": TimeFrameUnit.Day}
    for suffix, unit in units.items():
        if tf.endswith(suffix):
            return TimeFrame(int(tf[: -len(suffix)] or 1), unit)
    raise ValueError(f"Unsupported timeframe: {tf}")


def fetch_alpaca_bars(symbols: list[str], timeframe: str, start: str, end: str | None = None,
                      use_cache: bool = True) -> dict[str, pd.DataFrame]:
    """Download split/dividend-adjusted bars from Alpaca. Needs ALPACA_API_KEY / ALPACA_SECRET_KEY."""
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest

    out: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for sym in symbols:
        path = CACHE_DIR / f"{sym}_{timeframe}_{start}_{end or 'latest'}.csv"
        if use_cache and path.exists() and end is not None:
            out[sym] = pd.read_csv(path, index_col=0, parse_dates=True)
        else:
            missing.append(sym)
    if not missing:
        return out

    # Alpaca's free plan serves full SIP history as long as the request ends 15+ minutes ago.
    end_ts = pd.Timestamp(end, tz="UTC") if end else pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=20)
    client = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
    req = StockBarsRequest(
        symbol_or_symbols=missing,
        timeframe=_alpaca_timeframe(timeframe),
        start=pd.Timestamp(start, tz="UTC").to_pydatetime(),
        end=end_ts.to_pydatetime(),
        adjustment=Adjustment.ALL,
        feed=DataFeed.SIP,  # all US exchanges; history back to 2016
    )
    df = client.get_stock_bars(req).df
    CACHE_DIR.mkdir(exist_ok=True)
    for sym in missing:
        bars = df.xs(sym, level="symbol")[COLUMNS].sort_index()
        bars.index = pd.to_datetime(bars.index, utc=True)
        out[sym] = bars
        bars.to_csv(CACHE_DIR / f"{sym}_{timeframe}_{start}_{end or 'latest'}.csv")
    return out


def synthetic_bars(symbols: list[str], n: int = 1500, seed: int = 7,
                   start: str = "2018-01-01") -> dict[str, pd.DataFrame]:
    """Random-walk daily bars with mild drift and regime changes. For tests and offline demos only."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n, tz="UTC")
    out = {}
    for i, sym in enumerate(symbols):
        drift = np.where((np.arange(n) // 250) % 2 == 0, 0.0006, -0.0002)
        rets = drift + rng.normal(0, 0.012 + 0.002 * i, n)
        close = 100 * np.exp(np.cumsum(rets))
        open_ = close * np.exp(rng.normal(0, 0.003, n))
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, n)))
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, n)))
        vol = rng.integers(1_000_000, 5_000_000, n)
        out[sym] = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                                 "volume": vol}, index=idx)
    return out


def align(bars: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Restrict every symbol to the timestamps all symbols share."""
    common = None
    for df in bars.values():
        common = df.index if common is None else common.intersection(df.index)
    return {s: df.loc[common] for s, df in bars.items()}
