# Trading bot

An algorithmic trading bot for US stocks/ETFs on [Alpaca](https://alpaca.markets), built to run on Google Cloud.
**Paper trading only** until live trading is explicitly approved: the bot refuses to connect to a live
account unless `allow_live: true` is set in `config/settings.yaml` *and* `ALPACA_PAPER=false`.

## Quick start

```bash
python3 -m venv .venv                  # Ubuntu/Debian: sudo apt install python3-venv first
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m bot backtest --synthetic     # offline demo, no keys needed
cp .env.example .env                   # add your Alpaca PAPER keys
python -m bot backtest                 # backtest on real Alpaca data
python -m bot paper                    # run the paper-trading loop
pytest                                 # run the tests
```

Backtests print strategy vs. equal-weight buy-and-hold and save `reports/equity.png`.

## How it works

| Part | File | What it does |
|---|---|---|
| Config | `config/settings.yaml` | Symbols, timeframe, strategy params, costs, risk limits |
| Data | `bot/data.py` | Adjusted bars from Alpaca (free IEX feed), cached in `data_cache/` |
| Strategy | `bot/strategies/` | Turns bars into a 0–1 exposure per bar. Starter: SMA crossover with trend filter |
| Sizing | `bot/portfolio.py` | Equal weight across symbols, ignores small drifts to avoid churn |
| Risk | `bot/risk.py` | Per-symbol and total exposure caps, daily loss halt, max orders/day, kill switch |
| Backtest | `bot/backtest.py` | Signal at bar close → trade at next bar open (no look-ahead), fees + slippage |
| Brokers | `bot/brokers/` | Simulated broker for backtests, Alpaca adapter for paper |
| Runner | `bot/runner.py` | Always-on loop; trades once per new bar, remembers state across restarts |

**Kill switch:** create a file named `KILL_SWITCH` in the working directory and the bot places no orders.

## Adding a strategy

Subclass `bot.strategies.base.Strategy`, implement `signal(bars) -> pd.Series` (values 0–1, using only
data up to each bar), and register it in `bot/strategies/__init__.py`.

## Deploying

See [deploy/gcp-setup.md](deploy/gcp-setup.md).

> Backtest results are not a promise of future returns. The starter strategy exists to prove the
> pipeline, not to make money.
