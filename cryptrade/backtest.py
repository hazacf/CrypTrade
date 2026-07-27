"""Event-driven backtester.

Walks candle-by-candle so there is no look-ahead: the strategy only ever sees
data up to and including the last *closed* candle, and exits are checked
against the *next* candle's high/low. Compounding is automatic because sizing
uses live equity.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .exchange import PaperExchange
from .risk import RiskManager
from .strategy import Strategy


@dataclass
class BacktestResult:
    start_equity: float
    end_equity: float
    trades: list[dict]
    equity_curve: list[float]

    @property
    def n_trades(self) -> int:
        return sum(1 for t in self.trades if t.get("event") == "close")

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades
                   if t.get("event") == "close" and t.get("pnl", 0) > 0)

    @property
    def win_rate(self) -> float:
        return self.wins / self.n_trades if self.n_trades else 0.0

    @property
    def return_pct(self) -> float:
        return (self.end_equity / self.start_equity - 1) * 100

    @property
    def max_drawdown_pct(self) -> float:
        peak, mdd = self.equity_curve[0], 0.0
        for e in self.equity_curve:
            peak = max(peak, e)
            mdd = max(mdd, (peak - e) / peak)
        return mdd * 100

    def summary(self) -> str:
        return (
            f"Trades: {self.n_trades} | Win rate: {self.win_rate*100:.1f}% | "
            f"Return: {self.return_pct:+.1f}% | "
            f"Equity: {self.start_equity:.2f} -> {self.end_equity:.2f} | "
            f"Max drawdown: {self.max_drawdown_pct:.1f}%"
        )


def run_backtest(df: pd.DataFrame, cfg: dict, warmup: int = 60) -> BacktestResult:
    strat = Strategy(cfg.get("strategy", {}))
    risk = RiskManager(cfg.get("risk", {}))
    start_equity = float(cfg["account"]["initial_capital"])
    ex = PaperExchange(start_equity, cfg.get("fees", {}).get("taker", 0.00055))

    equity_curve = [start_equity]
    current_day = None
    realized_today = 0.0

    for i in range(warmup, len(df)):
        window = df.iloc[: i + 1]
        candle = df.iloc[i]
        day = window.index[-1].date()
        if day != current_day:
            current_day = day
            realized_today = 0.0

        # 1) manage an open position against THIS candle
        if ex.has_position():
            hit, price, reason = ex.check_exit(candle["high"], candle["low"])
            if hit:
                pnl = ex.close(price, reason)
                realized_today += pnl
            equity_curve.append(ex.get_equity())
            continue

        # 2) daily gate
        stop, _ = risk.day_should_stop(realized_today)
        if stop:
            equity_curve.append(ex.get_equity())
            continue

        # 3) look for a new entry (use data up to previous close, act at open)
        sig = strat.generate(window.iloc[:-1] if i > warmup else window)
        if sig.direction in ("long", "short"):
            plan = risk.build_plan(sig.direction, candle["open"], sig.atr,
                                   ex.get_equity())
            if plan is not None:
                ex.open(plan)
        equity_curve.append(ex.get_equity())

    if ex.has_position():
        ex.close(df.iloc[-1]["close"], "end_of_data")

    return BacktestResult(
        start_equity=start_equity,
        end_equity=ex.get_equity(),
        trades=ex.trades,
        equity_curve=equity_curve,
    )
