"""Chart-pattern recognition.

Two families:
  1. Candlestick patterns   -> single/dual-bar reversal & continuation signals.
  2. Classic chart patterns  -> derived from swing highs/lows: double top/bottom,
     head & shoulders, triangles, and support/resistance breakouts.

Each detector returns a signed score in [-1, +1] where positive is bullish
(expect price up) and negative is bearish (expect price down). The strategy
layer blends these with the technical indicators.

This is the module that satisfies the "read chart patterns to predict market
direction" requirement.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class PatternResult:
    """Aggregated pattern read for the most recent candle."""

    score: float                       # net direction in [-1, +1]
    bullish: list[str] = field(default_factory=list)
    bearish: list[str] = field(default_factory=list)

    @property
    def direction(self) -> str:
        if self.score > 0.15:
            return "bullish"
        if self.score < -0.15:
            return "bearish"
        return "neutral"


# --------------------------------------------------------------------------- #
# Candlestick patterns (evaluated on the last closed candle)
# --------------------------------------------------------------------------- #
def _body(o, c):
    return abs(c - o)


def _range(h, l):
    return max(h - l, 1e-12)


def detect_candlesticks(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return (bullish_names, bearish_names) for the last candle."""
    if len(df) < 2:
        return [], []
    bull, bear = [], []
    o, h, l, c = (
        df["open"].iloc[-1],
        df["high"].iloc[-1],
        df["low"].iloc[-1],
        df["close"].iloc[-1],
    )
    po, ph, pl, pc = (
        df["open"].iloc[-2],
        df["high"].iloc[-2],
        df["low"].iloc[-2],
        df["close"].iloc[-2],
    )
    rng = _range(h, l)
    body = _body(o, c)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    # Doji - indecision
    if body <= 0.1 * rng:
        # not directional on its own; skip
        pass

    # Hammer / Hanging man (long lower wick, small body near top)
    if lower_wick >= 2 * body and upper_wick <= body and body > 0:
        if c >= o:
            bull.append("hammer")
        else:
            bear.append("hanging_man")

    # Inverted hammer / Shooting star (long upper wick)
    if upper_wick >= 2 * body and lower_wick <= body and body > 0:
        if c < o:
            bear.append("shooting_star")
        else:
            bull.append("inverted_hammer")

    # Bullish / Bearish engulfing
    if c > o and pc < po and c >= po and o <= pc:
        bull.append("bullish_engulfing")
    if c < o and pc > po and o >= pc and c <= po:
        bear.append("bearish_engulfing")

    # Marubozu-ish strong candle (momentum)
    if body >= 0.85 * rng:
        if c > o:
            bull.append("strong_bull_candle")
        else:
            bear.append("strong_bear_candle")

    return bull, bear


# --------------------------------------------------------------------------- #
# Swing point detection (fractals) for structural chart patterns
# --------------------------------------------------------------------------- #
def swing_points(df: pd.DataFrame, left: int = 3, right: int = 3):
    """Return (highs, lows) as lists of (index_position, price)."""
    highs, lows = [], []
    h, l = df["high"].values, df["low"].values
    n = len(df)
    for i in range(left, n - right):
        window_h = h[i - left : i + right + 1]
        window_l = l[i - left : i + right + 1]
        if h[i] == window_h.max() and (window_h.argmax() == left):
            highs.append((i, h[i]))
        if l[i] == window_l.min() and (window_l.argmin() == left):
            lows.append((i, l[i]))
    return highs, lows


def _pct(a, b):
    return abs(a - b) / max(abs(b), 1e-12)


def detect_chart_patterns(
    df: pd.DataFrame, tol: float = 0.02
) -> tuple[list[str], list[str]]:
    """Structural patterns from swing points. tol = price tolerance (2%)."""
    bull, bear = [], []
    if len(df) < 25:
        return bull, bear
    highs, lows = swing_points(df)
    close = df["close"].iloc[-1]

    # ---- Double top (bearish) / Double bottom (bullish) ----
    if len(highs) >= 2:
        (_, h1), (_, h2) = highs[-2], highs[-1]
        if _pct(h1, h2) <= tol and close < min(h1, h2):
            bear.append("double_top")
    if len(lows) >= 2:
        (_, l1), (_, l2) = lows[-2], lows[-1]
        if _pct(l1, l2) <= tol and close > max(l1, l2):
            bull.append("double_bottom")

    # ---- Head & Shoulders (bearish) / Inverse H&S (bullish) ----
    if len(highs) >= 3:
        (_, a), (_, b), (_, c) = highs[-3], highs[-2], highs[-1]
        if b > a and b > c and _pct(a, c) <= tol * 1.5:
            bear.append("head_and_shoulders")
    if len(lows) >= 3:
        (_, a), (_, b), (_, c) = lows[-3], lows[-2], lows[-1]
        if b < a and b < c and _pct(a, c) <= tol * 1.5:
            bull.append("inverse_head_and_shoulders")

    # ---- Triangles / trend of swings ----
    if len(highs) >= 2 and len(lows) >= 2:
        hh = highs[-1][1] > highs[-2][1]
        lh = highs[-1][1] < highs[-2][1]
        hl = lows[-1][1] > lows[-2][1]
        ll = lows[-1][1] < lows[-2][1]
        if hh and hl:
            bull.append("ascending_structure")
        if lh and ll:
            bear.append("descending_structure")
        if lh and hl:
            # symmetrical triangle - breakout direction decides
            if close > df["high"].iloc[-5:-1].max():
                bull.append("symmetrical_triangle_breakout_up")
            elif close < df["low"].iloc[-5:-1].min():
                bear.append("symmetrical_triangle_breakout_down")

    # ---- Support / resistance breakout ----
    lookback = min(50, len(df) - 1)
    recent_high = df["high"].iloc[-lookback:-1].max()
    recent_low = df["low"].iloc[-lookback:-1].min()
    if close > recent_high:
        bull.append("resistance_breakout")
    if close < recent_low:
        bear.append("support_breakdown")

    return bull, bear


# Weight table: how much each pattern nudges the direction score.
_WEIGHTS = {
    # candlesticks
    "hammer": 0.35,
    "inverted_hammer": 0.2,
    "bullish_engulfing": 0.5,
    "strong_bull_candle": 0.25,
    "hanging_man": -0.35,
    "shooting_star": -0.35,
    "bearish_engulfing": -0.5,
    "strong_bear_candle": -0.25,
    # chart structures
    "double_bottom": 0.6,
    "inverse_head_and_shoulders": 0.7,
    "ascending_structure": 0.4,
    "symmetrical_triangle_breakout_up": 0.5,
    "resistance_breakout": 0.55,
    "double_top": -0.6,
    "head_and_shoulders": -0.7,
    "descending_structure": -0.4,
    "symmetrical_triangle_breakout_down": -0.5,
    "support_breakdown": -0.55,
}


def analyze(df: pd.DataFrame) -> PatternResult:
    """Full pattern read for the latest candle -> PatternResult."""
    cs_bull, cs_bear = detect_candlesticks(df)
    ch_bull, ch_bear = detect_chart_patterns(df)
    bullish = cs_bull + ch_bull
    bearish = cs_bear + ch_bear

    score = 0.0
    for name in bullish:
        score += _WEIGHTS.get(name, 0.2)
    for name in bearish:
        score += _WEIGHTS.get(name, -0.2)
    # squash into [-1, 1]
    score = float(np.tanh(score))
    return PatternResult(score=score, bullish=bullish, bearish=bearish)
