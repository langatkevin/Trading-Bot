from .base import Strategy
from .momentum import DualMomentum
from .simple import BuyAndHold, TrendFilter
from .sma_crossover import SmaCrossover

REGISTRY: dict[str, type[Strategy]] = {
    "buy_and_hold": BuyAndHold,
    "sma_crossover": SmaCrossover,
    "trend_filter": TrendFilter,
    "dual_momentum": DualMomentum,
}


def make_strategy(name: str, params: dict | None = None) -> Strategy:
    if name not in REGISTRY:
        raise ValueError(f"Unknown strategy {name!r}. Available: {sorted(REGISTRY)}")
    return REGISTRY[name](**(params or {}))
