from .base import Strategy
from .sma_crossover import SmaCrossover

REGISTRY: dict[str, type[Strategy]] = {"sma_crossover": SmaCrossover}


def make_strategy(name: str, params: dict) -> Strategy:
    if name not in REGISTRY:
        raise ValueError(f"Unknown strategy {name!r}. Available: {sorted(REGISTRY)}")
    return REGISTRY[name](**params)
