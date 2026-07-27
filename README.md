# CrypTrade

A chart-pattern–driven crypto **futures** trading bot for small accounts.
Built around three things you asked for: **reading chart patterns to predict
direction**, **5x leverage with liquidation-safe stops**, and **compounding**.

> ⚠️ **Read this first — honest expectations.**
> Your target of *"gain RM20–80 per day on RM400"* is a **5%–20% daily return**.
> Compounded, 5%/day would turn RM400 into millions in a year. **No bot, fund,
> or trader achieves this consistently.** Anyone who guarantees it is lucky
> (until they aren't) or scamming you. This bot does **not** promise profit.
> What it does: give you a disciplined, tested framework with strict risk
> controls so you can trade *methodically* and, above all, *not blow up your
> account*. Treat RM20–80/day as a **"take profit and stop for the day"
> target**, not a guarantee. **You can lose money, including all of it.**

---

## What it does

| Requirement | How it's handled |
|---|---|
| Read chart patterns to predict direction | `patterns.py` — candlesticks (engulfing, hammer, shooting star, marubozu) **and** structural patterns (double top/bottom, head & shoulders, triangles, support/resistance breakouts) |
| Futures trading | USDT-margined perpetuals via [ccxt](https://github.com/ccxt/ccxt) (Bybit, Binance USD-M, etc.) |
| 5x leverage, minimize liquidation | `risk.py` sizes every trade and **guarantees the stop-loss sits inside the liquidation price** — a rejected trade is better than a liquidated one |
| Low fees | Uses low-fee venues; fee tier is configurable and included in backtest P/L |
| Compounding | Position size is a % of **current equity**, so profits automatically grow the next trade |
| Protect the RM400 | Per-trade risk cap (2% default), **daily profit target**, and **daily loss limit** that stops trading for the day |

## Safety-first workflow (do these in order)

1. **Backtest** on historical data — no money, no keys.
2. **Paper trade** on live market data — real prices, simulated fills.
3. **Testnet** — real exchange, fake money (`testnet: true`).
4. **Live, tiny** — only after the above look sane, and only money you can lose.

The bot **defaults to paper mode and testnet**. Live mode refuses to start
without API keys and requires you to type `I UNDERSTAND`.

## Install

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml     # edit to taste
cp .env.example .env                   # only needed for testnet/live
```

## Backtest

```bash
# from a CSV: timestamp_ms,open,high,low,close,volume
python scripts/run_backtest.py --config config.yaml --csv data/btc_15m.csv

# or pull recent candles from the exchange
python scripts/run_backtest.py --config config.yaml --fetch 1500
```

Output reports trades, win rate, return, and **max drawdown** (how deep the
account dipped — watch this more than the return).

## Paper / live

```bash
python scripts/run_bot.py --config config.yaml
```

Set `mode: paper` (default) or `mode: live` in `config.yaml`. For live/testnet,
put keys in `.env` and keep `exchange.testnet: true` until you're confident.

## How a trade is decided

1. `strategy.py` asks `patterns.py` for the chart-pattern direction score.
2. It confirms with trend (EMA stack), momentum (MACD), and RSI, and only
   trades when a trend actually exists (ADX filter).
3. If pattern + context agree with enough confidence → a `Signal`.
4. `risk.py` turns the signal into a concrete `Plan`: entry, ATR-based stop,
   take-profit (reward:risk 1.8), size from current equity, and an explicit
   liquidation-price check. **No agreement, no trade.**

## Configuration highlights (`config.yaml`)

- `risk.leverage` — 5 by default.
- `risk.risk_per_trade` — fraction of equity risked per trade (0.02 = 2%).
- `risk.daily_profit_target` / `daily_loss_limit` — RM amounts that end the day.
- `strategy.min_confidence` — raise it for fewer, higher-quality trades.
- `exchange.testnet` — **keep `true`** until you've proven the bot.

## Project layout

```
cryptrade/
  indicators.py   EMA / RSI / ATR / MACD / ADX / Bollinger
  patterns.py     candlestick + chart-pattern recognition  ← the "read charts" part
  strategy.py     blends patterns + indicators into a Signal
  risk.py         sizing, leverage, liquidation-safe stops, daily limits
  exchange.py     LiveExchange (ccxt) + PaperExchange (simulator)
  backtest.py     event-driven backtester (no look-ahead)
  trader.py       live/paper loop
scripts/          run_backtest.py, run_bot.py
tests/            pytest suite
```

## Tests

```bash
python -m pytest -q
```

## Disclaimer

This is educational software, **not financial advice**. Crypto futures are
extremely risky; leverage amplifies losses; you can lose your entire deposit.
The authors accept no liability. Start on testnet, risk only what you can
afford to lose, and never trade money you need.
