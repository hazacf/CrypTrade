import numpy as np
import pandas as pd

from cryptrade import indicators


def _df(n=100, seed=1):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0, 1, n)
    low = close - rng.uniform(0, 1, n)
    open_ = close + rng.normal(0, 0.5, n)
    vol = rng.uniform(1, 10, n)
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": vol})


def test_ema_length_and_finite():
    df = _df()
    e = indicators.ema(df["close"], 10)
    assert len(e) == len(df)
    assert np.isfinite(e.iloc[-1])


def test_rsi_bounds():
    df = _df()
    r = indicators.rsi(df["close"], 14)
    assert (r.dropna() >= 0).all() and (r.dropna() <= 100).all()


def test_atr_positive():
    df = _df()
    a = indicators.atr(df, 14)
    assert (a.dropna() >= 0).all()


def test_add_indicators_columns():
    df = _df()
    out = indicators.add_indicators(df)
    for col in ["ema_fast", "ema_slow", "rsi", "atr", "macd", "adx"]:
        assert col in out.columns
