"""Backtest several strategies on the same period and print a side-by-side table."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .backtest import PERIODS_PER_YEAR, compute_metrics, run_backtest
from dataclasses import replace

from .config import Settings
from .data import align
from .strategies import make_strategy


def compare(settings: Settings, bars: dict[str, pd.DataFrame], out_dir: str = "reports") -> pd.DataFrame:
    entries = settings.compare or [{"label": settings.strategy.name, "name": settings.strategy.name,
                                    "params": settings.strategy.params}]
    # Every entry is judged on the same dates: those all needed symbols share.
    needed = {s for e in entries for s in e.get("symbols", settings.symbols)}
    common = align({s: bars[s] for s in needed})
    ppy = PERIODS_PER_YEAR.get(settings.timeframe, 252)

    rows, curves = [], {}
    for e in entries:
        syms = e.get("symbols", settings.symbols)
        strat = make_strategy(e["name"], e.get("params"))
        risk = replace(settings.risk, **e.get("risk", {}))
        res = run_backtest({s: common[s] for s in syms}, strat, settings.backtest, risk,
                           settings.timeframe)
        eq = res.equity.iloc[strat.warmup:]  # judge only after the strategy can trade
        curves[e["label"]] = res.equity
        half = len(eq) // 2
        first, second = compute_metrics(eq.iloc[:half], ppy), compute_metrics(eq.iloc[half:], ppy)
        m = compute_metrics(eq, ppy)
        rows.append({
            "strategy": e["label"],
            "CAGR": m["cagr"],
            "max DD": m["max_drawdown"],
            "Sharpe": m["sharpe"],
            "CAGR 1st half": first["cagr"],
            "CAGR 2nd half": second["cagr"],
            "trades": res.metrics["trades"],
            "invested": res.metrics["avg_invested"],
        })
    table = pd.DataFrame(rows).set_index("strategy")
    _plot(curves, out_dir)
    return table


def format_table(table: pd.DataFrame, start, end) -> str:
    fmt = table.copy()
    for col in ["CAGR", "max DD", "CAGR 1st half", "CAGR 2nd half", "invested"]:
        fmt[col] = fmt[col].map("{:.1%}".format)
    fmt["Sharpe"] = fmt["Sharpe"].map("{:.2f}".format)
    return f"Period: {start:%Y-%m-%d} to {end:%Y-%m-%d} (after each strategy's warm-up)\n\n" + fmt.to_string()


def _plot(curves: dict[str, pd.Series], out_dir: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    Path(out_dir).mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 6))
    for label, eq in curves.items():
        eq.plot(ax=ax, label=label, logy=True)
    ax.set_ylabel("Equity ($, log scale)")
    ax.set_title("Strategy comparison")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(f"{out_dir}/compare.png", dpi=110)
    plt.close(fig)
