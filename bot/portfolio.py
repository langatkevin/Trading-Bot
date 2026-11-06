"""Shared sizing logic, used by both the backtester and the paper runner."""
from __future__ import annotations

from .risk import Order, RiskManager


def target_orders(signals: dict[str, float], prices: dict[str, float], positions: dict[str, float],
                  equity: float, risk: RiskManager, rebalance_band: float = 0.02) -> list[Order]:
    """Equal-weight allocation across symbols, scaled by each symbol's signal, then capped by risk.

    Small drifts (less than rebalance_band of equity) are ignored to avoid churning fees,
    but a target of zero always closes the whole position.
    """
    n = len(signals) or 1
    wanted = {s: sig * equity / n for s, sig in signals.items()}
    capped = risk.cap_targets(wanted, equity)
    orders = []
    for s, value in capped.items():
        held = positions.get(s, 0.0)
        delta = value / prices[s] - held
        if value == 0 and held:
            orders.append(Order(s, -held, prices[s]))
        elif abs(delta) * prices[s] >= rebalance_band * equity:
            orders.append(Order(s, delta, prices[s]))
    return orders
