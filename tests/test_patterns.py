import pandas as pd

from cryptrade import patterns


def _mk(rows):
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"])


def test_bullish_engulfing_detected():
    # prev bearish, current larger bullish body engulfing it
    df = _mk([
        [10, 10.2, 9.5, 9.6, 1],   # bearish
        [9.5, 10.6, 9.4, 10.5, 1],  # bullish engulfing
    ])
    bull, bear = patterns.detect_candlesticks(df)
    assert "bullish_engulfing" in bull


def test_bearish_engulfing_detected():
    df = _mk([
        [9.6, 10.2, 9.5, 10.1, 1],  # bullish
        [10.2, 10.3, 9.3, 9.4, 1],  # bearish engulfing
    ])
    bull, bear = patterns.detect_candlesticks(df)
    assert "bearish_engulfing" in bear


def test_hammer_detected():
    # small body near top, long lower wick
    df = _mk([
        [10, 10.1, 9.9, 10.0, 1],
        [10.0, 10.1, 9.0, 10.05, 1],
    ])
    bull, bear = patterns.detect_candlesticks(df)
    assert "hammer" in bull


def test_resistance_breakout():
    rows = [[10, 10.5, 9.8, 10.0, 1] for _ in range(30)]
    rows.append([10, 12.5, 10.0, 12.4, 1])  # breaks above prior highs
    df = _mk(rows)
    bull, bear = patterns.detect_chart_patterns(df)
    assert "resistance_breakout" in bull


def test_analyze_returns_score_in_range():
    rows = [[10, 10.5, 9.8, 10.0, 1] for _ in range(40)]
    df = _mk(rows)
    res = patterns.analyze(df)
    assert -1.0 <= res.score <= 1.0
    assert res.direction in ("bullish", "bearish", "neutral")
