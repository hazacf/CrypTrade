"""Live / paper trading loop.

Same decision logic as the backtester. In `paper` mode it uses a
PaperExchange fed by real market data; in `live` mode it routes orders to a
real (or testnet) exchange via ccxt.

Run this only after you are satisfied with backtest + paper results.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from . import data
from .exchange import LiveExchange, PaperExchange
from .risk import RiskManager
from .strategy import Strategy

log = logging.getLogger("cryptrade")


class Trader:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.mode = cfg.get("mode", "paper")
        self.strat = Strategy(cfg.get("strategy", {}))
        self.risk = RiskManager(cfg.get("risk", {}))
        self.symbol = cfg["exchange"]["market"]
        self.timeframe = cfg["exchange"]["timeframe"]
        self.candles = cfg["loop"]["candles"]
        self.poll = cfg["loop"]["poll_seconds"]

        # Data source is always a real exchange client (read-only for paper).
        self.market = LiveExchange(cfg)
        if self.mode == "live":
            self.ex = self.market
        else:
            equity = float(cfg["account"]["initial_capital"])
            self.ex = PaperExchange(equity, cfg["fees"]["taker"])

        self._day = None
        self._realized_today = 0.0

    def _roll_day(self):
        today = datetime.now(timezone.utc).date()
        if today != self._day:
            self._day = today
            self._realized_today = 0.0
            log.info("New trading day %s - counters reset", today)

    def step(self):
        self._roll_day()
        df = data.fetch_ohlcv(self.market.client, self.symbol,
                              self.timeframe, self.candles)
        price = df["close"].iloc[-1]

        # Daily gate first.
        stop, msg = self.risk.day_should_stop(self._realized_today)
        if stop:
            log.info(msg)
            return

        if self.ex.has_position():
            log.info("Position open — letting stop/TP manage it. Price=%.2f", price)
            return

        sig = self.strat.generate(df)
        log.info("Signal: %s conf=%.2f | %s", sig.direction, sig.confidence,
                 "; ".join(sig.reasons))
        if sig.direction in ("long", "short"):
            plan = self.risk.build_plan(sig.direction, price, sig.atr,
                                        self.ex.get_equity())
            if plan is None:
                log.info("Signal rejected by risk manager (stop too close to "
                         "liquidation or sizing failed).")
                return
            log.info(
                "OPEN %s qty=%.6f entry=%.2f stop=%.2f tp=%.2f liq=%.2f "
                "risk=%.2f margin=%.2f",
                plan.side, plan.qty, plan.entry, plan.stop, plan.take_profit,
                plan.liquidation, plan.risk_amount, plan.margin,
            )
            self.ex.open(plan)

    def run(self):
        log.info("Starting trader in %s mode on %s %s", self.mode,
                 self.symbol, self.timeframe)
        if self.mode == "live":
            log.warning("LIVE MODE — real orders will be placed. Ctrl+C to stop.")
        while True:
            try:
                self.step()
            except KeyboardInterrupt:
                log.info("Stopped by user.")
                break
            except Exception as exc:  # keep the loop alive on transient errors
                log.exception("step error: %s", exc)
            time.sleep(self.poll)
