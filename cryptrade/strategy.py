"""Signal generation: blend chart patterns with technical indicators.

Produces a Signal(direction, confidence, reasons, atr, price). The trader/
backtester consumes it. Confidence in [0, 1] gates whether we trade and
scales position size.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import indicators, patterns


@dataclass
class Signal:
    direction: str                     # "long" | "short" | "flat"
    confidence: float                  # 0..1
    price: float
    atr: float
    reasons: list[str] = field(default_factory=list)


class Strategy:
    """Combines pattern direction with trend/momentum confirmation.

    We deliberately require agreement between *pattern* and *indicator*
    context before taking a trade. This reduces false signals — the whole
    point of "reading the chart" rather than blindly following one metric.
    """

    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or {}
        self.min_confidence = self.cfg.get("min_confidence", 0.55)
        self.adx_trend_min = self.cfg.get("adx_trend_min", 18)

    def generate(self, df: pd.DataFrame) -> Signal:
        df = indicators.add_indicators(df, self.cfg)
        last = df.iloc[-1]
        pat = patterns.analyze(df)

        reasons: list[str] = []
        long_score = 0.0
        short_score = 0.0

        # 1) Pattern contribution (the "highly insisted" chart reading)
        if pat.direction == "bullish":
            long_score += 0.4 * abs(pat.score)
            reasons.append(f"patterns bullish: {', '.join(pat.bullish)}")
        elif pat.direction == "bearish":
            short_score += 0.4 * abs(pat.score)
            reasons.append(f"patterns bearish: {', '.join(pat.bearish)}")

        # 2) Trend via EMA stack
        if last["ema_fast"] > last["ema_slow"] > last["ema_trend"]:
            long_score += 0.25
            reasons.append("EMA stack up")
        elif last["ema_fast"] < last["ema_slow"] < last["ema_trend"]:
            short_score += 0.25
            reasons.append("EMA stack down")

        # 3) Momentum via MACD histogram
        if last["macd_hist"] > 0:
            long_score += 0.15
        elif last["macd_hist"] < 0:
            short_score += 0.15

        # 4) RSI - avoid buying overbought / selling oversold extremes
        rsi = last["rsi"]
        if 45 <= rsi <= 68:
            long_score += 0.1
        elif 32 <= rsi <= 55:
            short_score += 0.1
        if rsi > 78:
            long_score *= 0.5      # too hot to chase longs
        if rsi < 22:
            short_score *= 0.5     # too cold to chase shorts

        # 5) Trend strength gate — only trade when there IS a trend
        trend_ok = last["adx"] >= self.adx_trend_min
        if not trend_ok:
            reasons.append(f"weak trend (ADX={last['adx']:.1f}) - dampened")
            long_score *= 0.6
            short_score *= 0.6

        if long_score >= short_score and long_score >= self.min_confidence:
            return Signal("long", min(long_score, 1.0), last["close"],
                          last["atr"], reasons)
        if short_score > long_score and short_score >= self.min_confidence:
            return Signal("short", min(short_score, 1.0), last["close"],
                          last["atr"], reasons)
        return Signal("flat", max(long_score, short_score), last["close"],
                      last["atr"], reasons + ["no confident setup"])
