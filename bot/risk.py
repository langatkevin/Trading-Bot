"""Risk manager: every order passes through here and can be shrunk or vetoed."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import RiskConfig


@dataclass
class Order:
    symbol: str
    qty: float  # positive = buy, negative = sell
    ref_price: float

    @property
    def value(self) -> float:
        return abs(self.qty) * self.ref_price


@dataclass
class RiskState:
    day: object = None
    day_start_equity: float = 0.0
    orders_today: int = 0
    halted_reason: str | None = None
    log: list[str] = field(default_factory=list)


class RiskManager:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg
        self.state = RiskState()

    # -- daily bookkeeping -------------------------------------------------
    def start_bar(self, day, equity: float) -> None:
        if day != self.state.day:
            self.state.day = day
            self.state.day_start_equity = equity
            self.state.orders_today = 0
            if self.state.halted_reason and self.state.halted_reason.startswith("daily loss"):
                self.state.halted_reason = None  # daily-loss halts reset the next day

    def kill_switch_on(self) -> bool:
        return Path(self.cfg.kill_switch_file).exists()

    def daily_loss_breached(self, equity: float) -> bool:
        start = self.state.day_start_equity
        return start > 0 and (start - equity) / start >= self.cfg.max_daily_loss_pct

    # -- sizing -------------------------------------------------------------
    def cap_targets(self, target_values: dict[str, float], equity: float) -> dict[str, float]:
        """Clamp per-symbol and total exposure. Long-only: negative targets become 0."""
        per_cap = self.cfg.max_position_pct * equity
        capped = {s: min(max(v, 0.0), per_cap) for s, v in target_values.items()}
        gross = sum(capped.values())
        limit = self.cfg.max_gross_exposure * equity
        if gross > limit > 0:
            scale = limit / gross
            capped = {s: v * scale for s, v in capped.items()}
        return capped

    # -- order approval -----------------------------------------------------
    def approve(self, orders: list[Order], equity: float) -> list[Order]:
        if self.kill_switch_on():
            self._note("kill switch file present: no orders")
            return []
        if self.daily_loss_breached(equity):
            self.state.halted_reason = f"daily loss >= {self.cfg.max_daily_loss_pct:.1%}"
        approved = []
        # Sells first so they free cash for buys.
        for o in sorted(orders, key=lambda o: o.qty):
            if o.value < self.cfg.min_order_value:
                continue
            if self.state.halted_reason and o.qty > 0:
                self._note(f"blocked buy {o.symbol}: {self.state.halted_reason}")
                continue  # risk-reducing sells are still allowed
            if self.state.orders_today >= self.cfg.max_orders_per_day:
                self._note(f"blocked {o.symbol}: max orders per day reached")
                continue
            approved.append(o)
            self.state.orders_today += 1
        return approved

    def _note(self, msg: str) -> None:
        self.state.log.append(f"{self.state.day}: {msg}")
