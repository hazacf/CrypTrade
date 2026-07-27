"""Technical indicators implemented on top of pandas/numpy.

Kept dependency-free (no TA-Lib) so the bot installs cleanly anywhere.
All functions take a pandas Series/DataFrame of OHLCV data and return
Series aligned to the input index.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential moving average."""
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average."""
    return series.rolling(window=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing)."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50.0)


def true_range(df: pd.DataFrame) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range - core of our stop / liquidation-distance logic."""
    tr = true_range(df)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": hist}
    )


def bollinger(
    series: pd.Series, period: int = 20, std: float = 2.0
) -> pd.DataFrame:
    mid = sma(series, period)
    dev = series.rolling(window=period).std(ddof=0)
    return pd.DataFrame(
        {"mid": mid, "upper": mid + std * dev, "lower": mid - std * dev}
    )


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index - trend strength (0-100)."""
    high, low = df["high"], df["low"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = true_range(df)
    atr_ = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False
    ).mean() / atr_.replace(0.0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False
    ).mean() / atr_.replace(0.0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0.0)


def add_indicators(df: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    """Attach the full indicator set the strategy relies on."""
    cfg = cfg or {}
    out = df.copy()
    out["ema_fast"] = ema(out["close"], cfg.get("ema_fast", 9))
    out["ema_slow"] = ema(out["close"], cfg.get("ema_slow", 21))
    out["ema_trend"] = ema(out["close"], cfg.get("ema_trend", 50))
    out["rsi"] = rsi(out["close"], cfg.get("rsi_period", 14))
    out["atr"] = atr(out, cfg.get("atr_period", 14))
    macd_df = macd(out["close"])
    out["macd"] = macd_df["macd"]
    out["macd_signal"] = macd_df["signal"]
    out["macd_hist"] = macd_df["hist"]
    bb = bollinger(out["close"])
    out["bb_upper"] = bb["upper"]
    out["bb_lower"] = bb["lower"]
    out["adx"] = adx(out, cfg.get("adx_period", 14))
    return out
