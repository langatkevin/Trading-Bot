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
python -m bot backtest                 # backtest the strategy in settings.yaml on real Alpaca data
python -m bot compare                  # backtest every strategy in settings.yaml `compare:` side by side
python -m bot paper                    # run the paper-trading loop
pytest                                 # run the tests
```

Backtests print strategy vs. equal-weight buy-and-hold and save `reports/equity.png`.

## How it works

| Part | File | What it does |
|---|---|---|
| Config | `config/settings.yaml` | Symbols, timeframe, strategy params, costs, risk limits |
| Data | `bot/data.py` | Adjusted bars from Alpaca (free IEX feed), cached in `data_cache/` |
| Strategy | `bot/strategies/` | Turns bars into target portfolio weights per bar (see below) |
| Sizing | `bot/portfolio.py` | Equal weight across symbols, ignores small drifts to avoid churn |
| Risk | `bot/risk.py` | Per-symbol and total exposure caps, daily loss halt, max orders/day, kill switch |
| Backtest | `bot/backtest.py` | Signal at bar close → trade at next bar open (no look-ahead), fees + slippage |
| Brokers | `bot/brokers/` | Simulated broker for backtests, Alpaca adapter for paper |
| Runner | `bot/runner.py` | Always-on loop; trades once per new bar, remembers state across restarts |

**Kill switch:** create a file named `KILL_SWITCH` in the working directory and the bot places no orders.

## Strategies

| Name | Idea |
|---|---|
| `buy_and_hold` | Always invested, equal weight. The benchmark. |
| `sma_crossover` | Long while fast SMA > slow SMA and price > trend SMA. |
| `trend_filter` | Hold each symbol while it's above its 200-day SMA, checked monthly. |
| `dual_momentum` | Each month, hold the `top_n` symbols with the best trailing return, but only if that return is positive; otherwise cash. |

Pick the one to trade under `strategy:` in `config/settings.yaml`, and the symbols under `symbols:`.

To add one, subclass `bot.strategies.base.Strategy`, implement `weights(bars) -> DataFrame` (or the
simpler per-symbol `signal(bars) -> Series`), using only data up to each bar, and register it in
`bot/strategies/__init__.py`.

## Paper trading

1. Pick a strategy (run `python -m bot compare` first) and set it under `strategy:` and `symbols:`.
2. Make sure `.env` has your **paper** keys and `ALPACA_PAPER=true`.
3. Run `python -m bot paper`. Leave it running: while the market is open it checks every minute and
   trades once per new daily bar, shortly after the open. Stop it with Ctrl+C.
4. Watch orders and positions at https://app.alpaca.markets (Paper account).

## Deploying

See [deploy/gcp-setup.md](deploy/gcp-setup.md).

> Backtest results are not a promise of future returns. The starter strategy exists to prove the
> pipeline, not to make money.
