import numpy as np
import pandas as pd

from cryptrade.backtest import run_backtest


def _synthetic(n=500, seed=7):
    rng = np.random.default_rng(seed)
    # trending + noisy series so some patterns/trends appear
    trend = np.linspace(0, 20, n)
    close = 100 + trend + np.cumsum(rng.normal(0, 0.8, n))
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)
    open_ = np.concatenate([[close[0]], close[:-1]])
    vol = rng.uniform(1, 10, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": vol}, index=idx)


CFG = {
    "account": {"initial_capital": 400.0, "currency": "RM"},
    "fees": {"taker": 0.00055},
    "strategy": {"min_confidence": 0.5},
    "risk": {"leverage": 5, "max_leverage_used": 5, "risk_per_trade": 0.02,
             "atr_stop_mult": 1.5, "reward_risk": 1.8,
             "daily_profit_target": 40, "daily_loss_limit": 40},
}


def test_backtest_runs_and_preserves_invariants():
    df = _synthetic()
    res = run_backtest(df, CFG)
    assert res.start_equity == 400.0
    assert len(res.equity_curve) > 0
    # equity should never go negative (isolated margin, capped loss)
    assert min(res.equity_curve) >= 0
    assert res.n_trades >= 0
    # summary string builds without error
    assert "Return" in res.summary()
