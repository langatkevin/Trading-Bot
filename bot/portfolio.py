"""Shared sizing logic, used by both the backtester and the paper runner."""
from __future__ import annotations

from .risk import Order, RiskManager


def target_orders(weights: dict[str, float], prices: dict[str, float], positions: dict[str, float],
                  equity: float, risk: RiskManager, rebalance_band: float = 0.10) -> list[Order]:
    """Turn target weights (fraction of equity per symbol) into orders, after risk caps.

    Small drifts (less than rebalance_band of the target position's value) are ignored to avoid
    churning fees, but a target of zero always closes the whole position.
    """
    wanted = {s: w * equity for s, w in weights.items()}
    capped = risk.cap_targets(wanted, equity)
    orders = []
    for s, value in capped.items():
        held = positions.get(s, 0.0)
        delta = value / prices[s] - held
        if value == 0 and held:
            orders.append(Order(s, -held, prices[s]))
        elif abs(delta) * prices[s] >= rebalance_band * max(value, 1e-9):
            orders.append(Order(s, delta, prices[s]))
    return orders
