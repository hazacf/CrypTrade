"""CrypTrade — a chart-pattern-driven crypto futures trading bot.

Modules:
    indicators  - technical indicators (EMA/RSI/ATR/MACD/ADX/Bollinger)
    patterns    - candlestick + classic chart pattern recognition
    strategy    - blends patterns with indicators into a Signal
    risk        - position sizing, leverage, liquidation-safe stops, daily limits
    exchange    - live (ccxt) and paper exchange implementations
    backtest    - event-driven backtester
    trader      - live/paper trading loop
"""

__version__ = "0.1.0"
