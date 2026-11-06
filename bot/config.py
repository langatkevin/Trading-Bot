"""Load settings.yaml into plain dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class StrategyConfig:
    name: str = "sma_crossover"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestConfig:
    initial_cash: float = 100_000.0
    fee_bps: float = 1.0
    slippage_bps: float = 2.0


@dataclass
class RiskConfig:
    max_position_pct: float = 0.30
    max_gross_exposure: float = 1.0
    max_daily_loss_pct: float = 0.02
    max_orders_per_day: int = 20
    min_order_value: float = 50.0
    kill_switch_file: str = "KILL_SWITCH"


@dataclass
class PaperConfig:
    poll_seconds: int = 60
    state_dir: str = "state"


@dataclass
class Settings:
    mode: str = "backtest"
    allow_live: bool = False
    symbols: list[str] = field(default_factory=lambda: ["SPY"])
    timeframe: str = "1Day"
    start: str = "2018-01-01"
    end: str | None = None
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    paper: PaperConfig = field(default_factory=PaperConfig)


def load_settings(path: str | Path = "config/settings.yaml") -> Settings:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    return Settings(
        mode=raw.get("mode", "backtest"),
        allow_live=bool(raw.get("allow_live", False)),
        symbols=list(raw.get("symbols", ["SPY"])),
        timeframe=raw.get("timeframe", "1Day"),
        start=str(raw.get("start", "2018-01-01")),
        end=raw.get("end"),
        strategy=StrategyConfig(**raw.get("strategy", {})),
        backtest=BacktestConfig(**raw.get("backtest", {})),
        risk=RiskConfig(**raw.get("risk", {})),
        paper=PaperConfig(**raw.get("paper", {})),
    )
