"""Event-driven backtester. Signal at bar t's close -> order at bar t+1's open. No look-ahead."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .brokers.sim import SimBroker
from .config import BacktestConfig, RiskConfig
from .data import align
from .portfolio import target_orders
from .risk import RiskManager
from .strategies.base import Strategy

PERIODS_PER_YEAR = {"1Day": 252, "1Hour": 252 * 7, "15Min": 252 * 26, "5Min": 252 * 78, "1Min": 252 * 390}


@dataclass
class BacktestResult:
    equity: pd.Series
    benchmark: pd.Series
    fills: pd.DataFrame
    metrics: dict
    benchmark_metrics: dict
    risk_log: list[str]


def compute_metrics(equity: pd.Series, periods_per_year: int) -> dict:
    rets = equity.pct_change().dropna()
    years = len(rets) / periods_per_year if len(rets) else 0
    total = equity.iloc[-1] / equity.iloc[0] - 1
    cagr = (1 + total) ** (1 / years) - 1 if years > 0 else 0.0
    dd = equity / equity.cummax() - 1
    std = rets.std()
    sharpe = float(rets.mean() / std * np.sqrt(periods_per_year)) if std > 0 else 0.0
    return {
        "total_return": float(total),
        "cagr": float(cagr),
        "max_drawdown": float(dd.min()),
        "sharpe": sharpe,
        "final_equity": float(equity.iloc[-1]),
    }


def run_backtest(bars: dict[str, pd.DataFrame], strategy: Strategy, bt: BacktestConfig,
                 risk_cfg: RiskConfig, timeframe: str = "1Day") -> BacktestResult:
    bars = align(bars)
    symbols = list(bars)
    index = bars[symbols[0]].index
    weights = strategy.weights(bars).reindex(index).fillna(0.0)[symbols]
    opens = pd.DataFrame({s: bars[s]["open"] for s in symbols})
    closes = pd.DataFrame({s: bars[s]["close"] for s in symbols})

    broker = SimBroker(cash=bt.initial_cash, fee_bps=bt.fee_bps, slippage_bps=bt.slippage_bps)
    risk = RiskManager(risk_cfg)
    equity_curve = [bt.initial_cash]

    for i in range(1, len(index)):
        t = index[i]
        open_px = opens.iloc[i].to_dict()
        risk.start_bar(t.date(), equity_curve[-1])
        eq_open = broker.equity(open_px)
        w = weights.iloc[i - 1].to_dict()
        orders = target_orders(w, open_px, broker.positions, eq_open, risk)
        for order in risk.approve(orders, eq_open):
            broker.submit(order, open_px[order.symbol], time=t)
        equity_curve.append(broker.equity(closes.iloc[i].to_dict()))

    equity = pd.Series(equity_curve, index=index, name="strategy")
    # Benchmark: equal-weight buy-and-hold, bought at the first close, no fees.
    norm = closes / closes.iloc[0]
    benchmark = (norm.mean(axis=1) * bt.initial_cash).rename("buy_and_hold")

    fills = pd.DataFrame([f.__dict__ for f in broker.fills])
    ppy = PERIODS_PER_YEAR.get(timeframe, 252)
    metrics = compute_metrics(equity, ppy)
    metrics["trades"] = len(fills)
    metrics["fees_paid"] = float(fills["fee"].sum()) if len(fills) else 0.0
    metrics["avg_invested"] = float(weights.sum(axis=1).iloc[strategy.warmup:].mean())
    return BacktestResult(equity, benchmark, fills, metrics, compute_metrics(benchmark, ppy), risk.state.log)


def save_report(result: BacktestResult, out_dir: str = "reports") -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pathlib import Path

    Path(out_dir).mkdir(exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    result.equity.plot(ax=ax1, label="Strategy")
    result.benchmark.plot(ax=ax1, label="Buy & hold", alpha=0.7)
    ax1.set_ylabel("Equity ($)")
    ax1.legend()
    ax1.set_title("Backtest equity curve")
    dd = result.equity / result.equity.cummax() - 1
    dd.plot(ax=ax2, color="tab:red")
    ax2.set_ylabel("Drawdown")
    fig.tight_layout()
    path = f"{out_dir}/equity.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    result.equity.to_csv(f"{out_dir}/equity.csv")
    result.fills.to_csv(f"{out_dir}/fills.csv", index=False)
    return path
