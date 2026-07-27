#!/usr/bin/env python3
"""Backtest CrypTrade on historical data.

Usage:
    # from a CSV of OHLCV (timestamp_ms,open,high,low,close,volume)
    python scripts/run_backtest.py --config config.yaml --csv data/btc_15m.csv

    # or pull recent candles live from the configured exchange
    python scripts/run_backtest.py --config config.yaml --fetch 1000
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptrade import data  # noqa: E402
from cryptrade.backtest import run_backtest  # noqa: E402
from cryptrade.config import load_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--csv", default=None, help="OHLCV CSV path")
    ap.add_argument("--fetch", type=int, default=0,
                    help="fetch N recent candles from exchange instead of CSV")
    args = ap.parse_args()

    cfg = load_config(args.config)

    if args.csv:
        df = data.load_csv(args.csv)
    elif args.fetch:
        from cryptrade.exchange import LiveExchange
        ex = LiveExchange(cfg)
        df = data.fetch_ohlcv(ex.client, cfg["exchange"]["market"],
                              cfg["exchange"]["timeframe"], args.fetch)
    else:
        ap.error("provide --csv PATH or --fetch N")

    print(f"Loaded {len(df)} candles "
          f"({df.index[0]} -> {df.index[-1]})")
    result = run_backtest(df, cfg)
    print("\n=== Backtest result ===")
    print(result.summary())
    cur = cfg["account"]["currency"]
    print(f"\nStart: {cur}{result.start_equity:.2f}  "
          f"End: {cur}{result.end_equity:.2f}  "
          f"P/L: {cur}{result.end_equity - result.start_equity:+.2f}")

    daily_target = cfg["risk"]["daily_profit_target"]
    print(f"\nNote: daily profit target is {cur}{daily_target:.0f}. "
          "Backtest realism depends on your data quality, fees, and slippage. "
          "Past performance does NOT guarantee future results.")


if __name__ == "__main__":
    main()
