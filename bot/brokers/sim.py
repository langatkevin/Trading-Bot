"""Simulated broker for backtests: fills at the given price plus slippage, charges fees."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..risk import Order


@dataclass
class Fill:
    time: object
    symbol: str
    qty: float
    price: float
    fee: float


@dataclass
class SimBroker:
    cash: float
    fee_bps: float = 1.0
    slippage_bps: float = 2.0
    positions: dict[str, float] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + sum(q * prices[s] for s, q in self.positions.items())

    def submit(self, order: Order, price: float, time=None) -> Fill | None:
        side = 1 if order.qty > 0 else -1
        fill_price = price * (1 + side * self.slippage_bps / 10_000)
        qty = order.qty
        if side > 0:
            # Never spend cash we don't have (no margin in the backtest).
            affordable = self.cash / (fill_price * (1 + self.fee_bps / 10_000))
            qty = min(qty, affordable)
        else:
            qty = max(qty, -self.positions.get(order.symbol, 0.0))  # no shorting
        if abs(qty) * fill_price < 1e-6:
            return None
        notional = qty * fill_price
        fee = abs(notional) * self.fee_bps / 10_000
        self.cash -= notional + fee
        self.positions[order.symbol] = self.positions.get(order.symbol, 0.0) + qty
        fill = Fill(time, order.symbol, qty, fill_price, fee)
        self.fills.append(fill)
        return fill
