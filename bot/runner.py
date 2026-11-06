"""Paper-trading loop. Runs forever (e.g. on a GCP VM); rebalances once per new completed bar."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


from .config import Settings
from .data import align, fetch_alpaca_bars
from .portfolio import target_orders
from .risk import RiskManager
from .strategies import make_strategy

log = logging.getLogger("bot.runner")


class StateStore:
    """Tiny JSON file so a restart doesn't trade the same bar twice."""

    def __init__(self, state_dir: str):
        self.path = Path(state_dir) / "runner_state.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def save(self, state: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, default=str))
        tmp.replace(self.path)


def run_once(settings: Settings, broker, risk: RiskManager, store: StateStore) -> None:
    strategy = make_strategy(settings.strategy.name, settings.strategy.params)
    # Enough history for the strategy's warmup (calendar days ~ 1.6x trading bars for daily data).
    lookback_days = int(max(strategy.warmup, 50) * 1.6) + 10
    start = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    bars = fetch_alpaca_bars(settings.symbols, settings.timeframe, start, use_cache=False)
    if settings.timeframe == "1Day":
        # Drop today's still-forming daily bar: decisions use completed bars only, like the backtest.
        today = datetime.now(timezone.utc).date()
        bars = {s: df[df.index.date < today] for s, df in bars.items()}
    bars = align(bars)

    state = store.load()
    last_bar = {s: str(df.index[-1]) for s, df in bars.items()}
    if state.get("last_bar") == last_bar:
        log.info("No new completed bar yet; nothing to do")
        return

    signals = {s: float(v) for s, v in strategy.weights(bars).iloc[-1].items()}
    prices = {s: float(df["close"].iloc[-1]) for s, df in bars.items()}
    equity = broker.equity()
    risk.start_bar(datetime.now(timezone.utc).date(), equity)
    orders = target_orders(signals, prices, broker.positions(), equity, risk)
    approved = risk.approve(orders, equity)
    log.info("signals=%s equity=%.2f orders=%d approved=%d", signals, equity, len(orders), len(approved))
    for order in approved:
        broker.submit(order)
    for note in risk.state.log:
        log.warning("risk: %s", note)
    risk.state.log.clear()

    state.update(last_bar=last_bar, last_run=datetime.now(timezone.utc).isoformat(), equity=equity,
                 signals=signals)
    store.save(state)


def run_forever(settings: Settings) -> None:
    from .brokers.alpaca_broker import AlpacaBroker

    broker = AlpacaBroker(allow_live=settings.allow_live)
    risk = RiskManager(settings.risk)
    store = StateStore(settings.paper.state_dir)
    log.info("Runner started: symbols=%s timeframe=%s paper=%s", settings.symbols, settings.timeframe,
             broker.paper)
    while True:
        try:
            if broker.market_is_open():
                run_once(settings, broker, risk, store)
            else:
                log.info("heartbeat: market closed")
        except Exception:  # keep running; Cloud Logging alerts on ERROR
            log.exception("Runner iteration failed")
        time.sleep(settings.paper.poll_seconds)


