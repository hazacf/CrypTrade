"""Risk management: the part that actually protects your RM400.

Responsibilities:
  * Position sizing from *current* equity  -> compounding is automatic.
  * Leverage cap (default 5x per the requirement).
  * ATR-based stop loss placed well inside the liquidation price.
  * Daily profit target (take RM20-80 and stop) and daily loss limit.

Nothing here promises profit. It bounds losses so one bad trade or one bad
day cannot wipe the account.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Plan:
    side: str            # "long" | "short"
    entry: float
    stop: float
    take_profit: float
    qty: float           # contracts / base units
    notional: float      # entry * qty
    margin: float        # notional / leverage
    liquidation: float   # approx liquidation price
    risk_amount: float   # currency at risk if stop is hit


class RiskManager:
    def __init__(self, cfg: dict):
        self.leverage = float(cfg.get("leverage", 5))
        self.risk_per_trade = float(cfg.get("risk_per_trade", 0.02))  # 2% equity
        self.atr_stop_mult = float(cfg.get("atr_stop_mult", 1.5))
        self.rr = float(cfg.get("reward_risk", 1.8))                  # TP = RR * risk
        self.max_leverage_used = float(cfg.get("max_leverage_used", self.leverage))
        # Daily controls (in account currency, e.g. RM)
        self.daily_profit_target = float(cfg.get("daily_profit_target", 40))
        self.daily_loss_limit = float(cfg.get("daily_loss_limit", 40))
        # maintenance margin rate used for the liquidation estimate
        self.maint_margin_rate = float(cfg.get("maint_margin_rate", 0.005))

    # ---- daily gate --------------------------------------------------- #
    def day_should_stop(self, realized_today: float) -> tuple[bool, str]:
        if realized_today >= self.daily_profit_target:
            return True, (
                f"Daily profit target hit (+{realized_today:.2f}). "
                "Stopping to lock gains."
            )
        if realized_today <= -self.daily_loss_limit:
            return True, (
                f"Daily loss limit hit ({realized_today:.2f}). "
                "Stopping to protect capital."
            )
        return False, ""

    # ---- position sizing --------------------------------------------- #
    def liquidation_price(self, side: str, entry: float) -> float:
        """Approximate isolated-margin liquidation price.

        For isolated margin, liquidation happens roughly when loss ~= margin.
        Move fraction ~= 1/leverage minus maintenance margin.
        """
        adverse = (1.0 / self.leverage) - self.maint_margin_rate
        if side == "long":
            return entry * (1 - adverse)
        return entry * (1 + adverse)

    def build_plan(
        self, side: str, entry: float, atr: float, equity: float
    ) -> Plan | None:
        if entry <= 0 or atr <= 0 or equity <= 0:
            return None

        stop_dist = self.atr_stop_mult * atr
        if side == "long":
            stop = entry - stop_dist
            take_profit = entry + self.rr * stop_dist
        else:
            stop = entry + stop_dist
            take_profit = entry - self.rr * stop_dist

        liq = self.liquidation_price(side, entry)

        # Safety: the stop MUST trigger before liquidation, otherwise the
        # position gets liquidated (max loss) instead of stopped out.
        if side == "long" and stop <= liq:
            return None
        if side == "short" and stop >= liq:
            return None

        # Risk-based sizing: currency at risk = equity * risk_per_trade
        risk_amount = equity * self.risk_per_trade
        qty = risk_amount / stop_dist
        notional = entry * qty

        # Respect leverage cap: notional can't exceed equity * max_leverage.
        max_notional = equity * self.max_leverage_used
        if notional > max_notional:
            qty = max_notional / entry
            notional = entry * qty
            risk_amount = qty * stop_dist  # recompute actual risk

        margin = notional / self.leverage
        return Plan(
            side=side,
            entry=entry,
            stop=stop,
            take_profit=take_profit,
            qty=qty,
            notional=notional,
            margin=margin,
            liquidation=liq,
            risk_amount=risk_amount,
        )
