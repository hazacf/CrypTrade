from cryptrade.risk import RiskManager

CFG = {
    "leverage": 5,
    "max_leverage_used": 5,
    "risk_per_trade": 0.02,
    "atr_stop_mult": 1.5,
    "reward_risk": 1.8,
    "daily_profit_target": 40,
    "daily_loss_limit": 40,
}


def test_long_plan_geometry():
    rm = RiskManager(CFG)
    plan = rm.build_plan("long", entry=100.0, atr=1.0, equity=400.0)
    assert plan is not None
    assert plan.stop < plan.entry < plan.take_profit
    # stop must sit above the liquidation price for a long
    assert plan.stop > plan.liquidation
    # risked amount ~ 2% of equity
    assert abs(plan.risk_amount - 8.0) < 1e-6


def test_short_plan_geometry():
    rm = RiskManager(CFG)
    plan = rm.build_plan("short", entry=100.0, atr=1.0, equity=400.0)
    assert plan is not None
    assert plan.take_profit < plan.entry < plan.stop
    assert plan.stop < plan.liquidation


def test_leverage_cap_enforced():
    rm = RiskManager(CFG)
    # tiny ATR would size a huge position; cap must bind
    plan = rm.build_plan("long", entry=100.0, atr=0.01, equity=400.0)
    assert plan is not None
    assert plan.notional <= 400.0 * 5 + 1e-6


def test_daily_gates():
    rm = RiskManager(CFG)
    stop, _ = rm.day_should_stop(45)
    assert stop
    stop, _ = rm.day_should_stop(-45)
    assert stop
    stop, _ = rm.day_should_stop(10)
    assert not stop


def test_reject_when_stop_inside_liquidation():
    # huge ATR pushes the stop beyond liquidation -> reject the trade
    rm = RiskManager(CFG)
    plan = rm.build_plan("long", entry=100.0, atr=50.0, equity=400.0)
    assert plan is None
