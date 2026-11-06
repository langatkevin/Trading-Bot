"""Command line entry point.

    python -m bot backtest               # real Alpaca data (needs keys in .env)
    python -m bot backtest --synthetic   # offline demo on random data
    python -m bot paper                  # run the paper-trading loop
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    parser = argparse.ArgumentParser(prog="bot")
    parser.add_argument("command", choices=["backtest", "paper"])
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--synthetic", action="store_true", help="backtest on random data, no API keys")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    _load_dotenv()

    from .config import load_settings

    settings = load_settings(args.config)

    if args.command == "backtest":
        from .backtest import run_backtest, save_report
        from .data import fetch_alpaca_bars, synthetic_bars
        from .strategies import make_strategy

        bars = (synthetic_bars(settings.symbols) if args.synthetic else
                fetch_alpaca_bars(settings.symbols, settings.timeframe, settings.start, settings.end))
        strategy = make_strategy(settings.strategy.name, settings.strategy.params)
        res = run_backtest(bars, strategy, settings.backtest, settings.risk, settings.timeframe)
        print(f"\n{'metric':<16}{'strategy':>14}{'buy & hold':>14}")
        for k in ["total_return", "cagr", "max_drawdown", "sharpe"]:
            fmt = "{:>14.2f}" if k == "sharpe" else "{:>14.2%}"
            print(f"{k:<16}" + fmt.format(res.metrics[k]) + fmt.format(res.benchmark_metrics[k]))
        print(f"{'trades':<16}{res.metrics['trades']:>14}")
        print(f"{'fees_paid':<16}{res.metrics['fees_paid']:>14.2f}")
        print(f"{'time_in_market':<16}{res.metrics['time_in_market']:>14.1%}")
        print(f"\nChart saved to {save_report(res)}")
    else:
        from .runner import run_forever

        if settings.mode == "backtest":
            settings.mode = "paper"
        run_forever(settings)


if __name__ == "__main__":
    main()
