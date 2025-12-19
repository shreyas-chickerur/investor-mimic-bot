from decimal import Decimal

from services.execution.planner import TradePlanner, TradePlannerConfig


def test_generate_buy_plan_basic():
    planner = TradePlanner(
        TradePlannerConfig(share_increment=Decimal("0.01"), min_trade_notional=Decimal("10"))
    )
    target_weights = {"AAA": Decimal("0.5"), "BBB": Decimal("0.5")}
    prices = {"AAA": Decimal("100"), "BBB": Decimal("50")}
    current_positions = {"AAA": Decimal("0"), "BBB": Decimal("0")}

    plan = planner.generate_buy_plan(
        target_weights=target_weights,
        prices=prices,
        current_positions=current_positions,
        total_equity=Decimal("1000"),
        limit_offset_bps=10,
    )

    assert len(plan.orders) == 2
    by_sym = {o.symbol: o for o in plan.orders}
    assert by_sym["AAA"].qty == Decimal("5.00")
    assert by_sym["BBB"].qty == Decimal("10.00")


def test_generate_buy_plan_respects_current_position():
    planner = TradePlanner(
        TradePlannerConfig(share_increment=Decimal("0.01"), min_trade_notional=Decimal("10"))
    )
    target_weights = {"AAA": Decimal("1")}
    prices = {"AAA": Decimal("100")}
    current_positions = {"AAA": Decimal("9")}

    plan = planner.generate_buy_plan(
        target_weights=target_weights,
        prices=prices,
        current_positions=current_positions,
        total_equity=Decimal("1000"),
        limit_offset_bps=10,
    )

    assert len(plan.orders) == 1
    assert plan.orders[0].symbol == "AAA"
    assert plan.orders[0].qty == Decimal("1.00")


def test_generate_buy_plan_skips_missing_price():
    planner = TradePlanner()
    target_weights = {"AAA": Decimal("1")}
    prices = {}
    current_positions = {}

    plan = planner.generate_buy_plan(
        target_weights=target_weights,
        prices=prices,
        current_positions=current_positions,
        total_equity=Decimal("1000"),
        limit_offset_bps=10,
    )

    assert len(plan.orders) == 0
    assert "AAA" in plan.skipped
