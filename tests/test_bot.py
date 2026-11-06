import os

import numpy as np
import pandas as pd
import pytest

from bot.backtest import run_backtest
from bot.brokers.sim import SimBroker
from bot.config import BacktestConfig, RiskConfig, load_settings
from bot.data import synthetic_bars
from bot.portfolio import target_orders
from bot.risk import Order, RiskManager
from bot.strategies import SmaCrossover
from bot.strategies.base import Strategy


def test_settings_file_loads():
    s = load_settings("config/settings.yaml")
    assert s.mode == "backtest" and s.allow_live is False


def test_sma_signal_uses_only_past_data():
    bars = synthetic_bars(["AAA"], n=400)["AAA"]
    strat = SmaCrossover(fast=5, slow=20, trend=50)
    full = strat.signal(bars)
    partial = strat.signal(bars.iloc[:300])
    # Changing the future must not change past signals.
    pd.testing.assert_series_equal(full.iloc[:300], partial)
    assert (full.iloc[:50] == 0).all()


class PeekAhead(Strategy):
    """Cheating strategy: long exactly on bars where tomorrow's close is higher."""

    def signal(self, bars):
        return (bars["close"].shift(-1) > bars["close"]).astype(float)


class Honest(Strategy):
    def signal(self, bars):
        return pd.Series(1.0, index=bars.index)


def test_engine_trades_next_open_so_lookahead_is_not_free():
    # If the engine traded on the same bar's close, PeekAhead would be impossibly profitable.
    bars = synthetic_bars(["AAA"], n=300, seed=3)
    risk = RiskConfig(max_position_pct=1.0)
    bt = BacktestConfig(fee_bps=0, slippage_bps=0)
    cheat = run_backtest(bars, PeekAhead(), bt, risk)
    assert cheat.metrics["sharpe"] < 5


def test_always_long_tracks_buy_and_hold():
    bars = synthetic_bars(["AAA"], n=300, seed=5)
    res = run_backtest(bars, Honest(), BacktestConfig(fee_bps=0, slippage_bps=0), RiskConfig(max_position_pct=1.0))
    assert res.metrics["total_return"] == pytest.approx(res.benchmark_metrics["total_return"], abs=0.03)


def test_risk_caps_position_and_gross_exposure():
    rm = RiskManager(RiskConfig(max_position_pct=0.3, max_gross_exposure=0.5))
    capped = rm.cap_targets({"A": 80_000, "B": 80_000, "C": -5_000}, equity=100_000)
    assert capped["C"] == 0
    assert max(capped.values()) <= 30_000
    assert sum(capped.values()) == pytest.approx(50_000)


def test_kill_switch_blocks_everything(tmp_path):
    ks = tmp_path / "KILL"
    rm = RiskManager(RiskConfig(kill_switch_file=str(ks)))
    rm.start_bar("d1", 100_000)
    ks.write_text("stop")
    assert rm.approve([Order("A", 10, 100)], 100_000) == []


def test_daily_loss_blocks_buys_but_allows_sells():
    rm = RiskManager(RiskConfig(max_daily_loss_pct=0.02, kill_switch_file="/nonexistent"))
    rm.start_bar("d1", 100_000)
    approved = rm.approve([Order("A", 10, 100), Order("B", -10, 100)], equity=97_000)
    assert [o.symbol for o in approved] == ["B"]
    rm.start_bar("d2", 97_000)  # new day resets the halt
    assert rm.approve([Order("A", 10, 100)], equity=97_000)


def test_max_orders_per_day():
    rm = RiskManager(RiskConfig(max_orders_per_day=2, kill_switch_file="/nonexistent"))
    rm.start_bar("d1", 100_000)
    approved = rm.approve([Order(s, 10, 100) for s in "ABC"], 100_000)
    assert len(approved) == 2


def test_sim_broker_no_margin_no_shorting():
    b = SimBroker(cash=1_000, fee_bps=10, slippage_bps=0)
    b.submit(Order("A", 100, 100), price=100)  # wants $10k, only has $1k
    assert b.cash >= -1e-9 and b.positions["A"] < 10
    b.submit(Order("A", -50, 100), price=100)  # sell more than held
    assert b.positions["A"] == pytest.approx(0)


def test_fees_and_slippage_reduce_returns():
    bars = synthetic_bars(["AAA", "BBB"], n=600)
    strat = SmaCrossover(5, 20, 0)
    free = run_backtest(bars, strat, BacktestConfig(fee_bps=0, slippage_bps=0), RiskConfig())
    costly = run_backtest(bars, strat, BacktestConfig(fee_bps=10, slippage_bps=10), RiskConfig())
    assert costly.metrics["final_equity"] < free.metrics["final_equity"]


def test_target_orders_close_position_when_signal_is_zero():
    rm = RiskManager(RiskConfig())
    orders = target_orders({"A": 0.0}, {"A": 100.0}, {"A": 5.0}, 100_000, rm)
    assert len(orders) == 1 and orders[0].qty == -5.0


def test_live_trading_refused_without_flag(monkeypatch):
    pytest.importorskip("alpaca")
    from bot.brokers.alpaca_broker import AlpacaBroker, LiveTradingNotAllowed

    monkeypatch.setenv("ALPACA_PAPER", "false")
    monkeypatch.setenv("ALPACA_API_KEY", "x")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "y")
    with pytest.raises(LiveTradingNotAllowed):
        AlpacaBroker(allow_live=False)
