"""Configuration loading: YAML file + environment overrides for secrets."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv optional
    pass


DEFAULT_CONFIG = {
    "exchange": {
        "id": "bybit",            # ccxt id; bybit/binanceusdm = low-fee futures
        "market": "BTC/USDT:USDT",
        "timeframe": "15m",
        "testnet": True,          # SAFETY: default to testnet
    },
    "mode": "paper",              # paper | backtest | live
    "account": {
        "currency": "RM",
        "initial_capital": 400.0,
        # RM<->USD is only for display; trading happens in USDT.
        "usd_per_currency": 0.21,
    },
    "strategy": {
        "min_confidence": 0.55,
        "adx_trend_min": 18,
        "ema_fast": 9,
        "ema_slow": 21,
        "ema_trend": 50,
        "rsi_period": 14,
        "atr_period": 14,
    },
    "risk": {
        "leverage": 5,
        "max_leverage_used": 5,
        "risk_per_trade": 0.02,
        "atr_stop_mult": 1.5,
        "reward_risk": 1.8,
        "daily_profit_target": 40.0,   # RM
        "daily_loss_limit": 40.0,      # RM
        "maint_margin_rate": 0.005,
    },
    "fees": {
        # Typical maker/taker for major low-fee futures venues.
        "taker": 0.00055,
        "maker": 0.0002,
    },
    "loop": {
        "poll_seconds": 30,
        "candles": 200,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | None = None) -> dict:
    cfg = DEFAULT_CONFIG
    if path and Path(path).exists():
        with open(path) as f:
            user_cfg = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, user_cfg)
    # Secrets always come from the environment, never the YAML file.
    cfg["secrets"] = {
        "api_key": os.getenv("EXCHANGE_API_KEY", ""),
        "api_secret": os.getenv("EXCHANGE_API_SECRET", ""),
    }
    return cfg
