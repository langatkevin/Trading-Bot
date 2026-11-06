"""Alpaca broker adapter. Paper trading by default; live is refused unless explicitly unlocked."""
from __future__ import annotations

import logging
import os

from ..risk import Order

log = logging.getLogger(__name__)


class LiveTradingNotAllowed(RuntimeError):
    pass


class AlpacaBroker:
    def __init__(self, allow_live: bool = False):
        from alpaca.trading.client import TradingClient

        paper = os.environ.get("ALPACA_PAPER", "true").lower() != "false"
        if not paper and not allow_live:
            raise LiveTradingNotAllowed(
                "ALPACA_PAPER=false but allow_live is not set in settings.yaml. Refusing to trade live.")
        self.paper = paper
        self.client = TradingClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"], paper=paper)
        log.info("Connected to Alpaca (%s)", "PAPER" if paper else "LIVE")

    def equity(self) -> float:
        return float(self.client.get_account().equity)

    def cash(self) -> float:
        return float(self.client.get_account().cash)

    def positions(self) -> dict[str, float]:
        return {p.symbol: float(p.qty) for p in self.client.get_all_positions()}

    def market_is_open(self) -> bool:
        return bool(self.client.get_clock().is_open)

    def submit(self, order: Order):
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        qty = round(abs(order.qty), 6)  # fractional shares are supported for most US equities
        req = MarketOrderRequest(
            symbol=order.symbol,
            qty=qty,
            side=OrderSide.BUY if order.qty > 0 else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        result = self.client.submit_order(req)
        log.info("Submitted %s %s %s -> id=%s", req.side.value, qty, order.symbol, result.id)
        return result
