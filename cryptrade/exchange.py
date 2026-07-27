"""Exchange abstraction.

`LiveExchange`  -> thin ccxt wrapper for real/testnet futures trading.
`PaperExchange` -> in-memory simulator with the same interface so paper and
                   live modes share the trader code path exactly.

Live trading is intentionally gated behind explicit config + API keys and
defaults to testnet.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Position:
    side: str            # "long" | "short"
    qty: float
    entry: float
    stop: float
    take_profit: float
    liquidation: float


class PaperExchange:
    """Simulates an isolated-margin futures account for paper/backtest.

    Balance is the free equity (USDT). We track a single open position at a
    time — matching the bot's one-trade-at-a-time policy.
    """

    def __init__(self, balance: float, taker_fee: float = 0.00055):
        self.balance = float(balance)
        self.taker_fee = taker_fee
        self.position: Position | None = None
        self.trades: list[dict] = []

    # ---- interface mirrored by LiveExchange ---- #
    def get_equity(self) -> float:
        return self.balance

    def has_position(self) -> bool:
        return self.position is not None

    def open(self, plan) -> None:
        fee = plan.notional * self.taker_fee
        self.balance -= fee
        self.position = Position(
            side=plan.side, qty=plan.qty, entry=plan.entry,
            stop=plan.stop, take_profit=plan.take_profit,
            liquidation=plan.liquidation,
        )
        self.trades.append({"event": "open", "side": plan.side,
                            "price": plan.entry, "qty": plan.qty, "fee": fee})

    def close(self, price: float, reason: str = "") -> float:
        pos = self.position
        if pos is None:
            return 0.0
        if pos.side == "long":
            pnl = (price - pos.entry) * pos.qty
        else:
            pnl = (pos.entry - price) * pos.qty
        fee = price * pos.qty * self.taker_fee
        pnl -= fee
        self.balance += pnl
        self.trades.append({"event": "close", "price": price, "pnl": pnl,
                            "fee": fee, "reason": reason})
        self.position = None
        return pnl

    def check_exit(self, high: float, low: float) -> tuple[bool, float, str]:
        """Given a candle's high/low, did stop / TP / liquidation trigger?"""
        pos = self.position
        if pos is None:
            return False, 0.0, ""
        if pos.side == "long":
            if low <= pos.liquidation:
                return True, pos.liquidation, "liquidation"
            if low <= pos.stop:
                return True, pos.stop, "stop_loss"
            if high >= pos.take_profit:
                return True, pos.take_profit, "take_profit"
        else:
            if high >= pos.liquidation:
                return True, pos.liquidation, "liquidation"
            if high >= pos.stop:
                return True, pos.stop, "stop_loss"
            if low <= pos.take_profit:
                return True, pos.take_profit, "take_profit"
        return False, 0.0, ""


class LiveExchange:
    """ccxt-backed futures exchange (real or testnet)."""

    def __init__(self, cfg: dict):
        import ccxt  # imported lazily so paper/backtest need no ccxt install

        ex_cfg = cfg["exchange"]
        secrets = cfg.get("secrets", {})
        klass = getattr(ccxt, ex_cfg["id"])
        self.client = klass({
            "apiKey": secrets.get("api_key", ""),
            "secret": secrets.get("api_secret", ""),
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })
        if ex_cfg.get("testnet", True) and hasattr(self.client, "set_sandbox_mode"):
            self.client.set_sandbox_mode(True)
        self.symbol = ex_cfg["market"]
        self.leverage = cfg["risk"]["leverage"]
        self.taker_fee = cfg["fees"]["taker"]
        try:
            self.client.set_leverage(self.leverage, self.symbol)
        except Exception:
            pass  # some venues set leverage per-order

    def fetch_ohlcv(self, symbol, timeframe, limit):
        return self.client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    def get_equity(self) -> float:
        bal = self.client.fetch_balance()
        usdt = bal.get("total", {}).get("USDT")
        return float(usdt) if usdt is not None else 0.0

    def has_position(self) -> bool:
        try:
            positions = self.client.fetch_positions([self.symbol])
            return any(abs(float(p.get("contracts") or 0)) > 0 for p in positions)
        except Exception:
            return False

    def open(self, plan) -> None:
        side = "buy" if plan.side == "long" else "sell"
        self.client.create_order(self.symbol, "market", side, plan.qty)
        # Attach protective stop + take-profit as reduce-only orders.
        opp = "sell" if plan.side == "long" else "buy"
        params_sl = {"stopLossPrice": plan.stop, "reduceOnly": True}
        params_tp = {"takeProfitPrice": plan.take_profit, "reduceOnly": True}
        try:
            self.client.create_order(self.symbol, "market", opp, plan.qty, None, params_sl)
            self.client.create_order(self.symbol, "market", opp, plan.qty, None, params_tp)
        except Exception:
            pass  # venue may require a different SL/TP call; leave as manual guard

    def close(self, price: float = None, reason: str = "") -> float:
        try:
            positions = self.client.fetch_positions([self.symbol])
            for p in positions:
                contracts = float(p.get("contracts") or 0)
                if abs(contracts) > 0:
                    side = "sell" if p.get("side") == "long" else "buy"
                    self.client.create_order(
                        self.symbol, "market", side, abs(contracts),
                        None, {"reduceOnly": True})
        except Exception:
            pass
        return 0.0
