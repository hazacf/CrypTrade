"""OHLCV data access via ccxt, returned as a tidy pandas DataFrame."""
from __future__ import annotations

import pandas as pd


def ohlcv_to_df(raw: list[list]) -> pd.DataFrame:
    df = pd.DataFrame(
        raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("datetime")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    return df


def fetch_ohlcv(exchange, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    return ohlcv_to_df(raw)


def load_csv(path: str) -> pd.DataFrame:
    """Load historical OHLCV from CSV for backtesting.

    Expected columns: timestamp(ms),open,high,low,close,volume
    """
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    df = df.rename(columns={cols.get(k, k): k for k in
                            ["timestamp", "open", "high", "low", "close", "volume"]})
    return ohlcv_to_df(df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist())
