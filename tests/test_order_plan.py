import pytest

from paper_trading.order_plan import (
    build_fixed_risk_bracket_order_plan,
    build_bracket_order_plan,
    normalize_direction,
)


def test_normalize_direction():
    assert normalize_direction("LONG") == "long"
    assert normalize_direction("short") == "short"


def test_normalize_direction_rejects_unknown_direction():
    with pytest.raises(ValueError, match="Invalid direction"):
        normalize_direction("FLAT")


def test_build_long_bracket_order_plan():
    plan = build_bracket_order_plan(
        symbol="aapl",
        strategy_version="ORB_RETEST_RECLAIM_BODY_2R",
        direction="LONG",
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        account_equity=10_000.0,
        risk_fraction=0.01,
    )

    assert plan.symbol == "AAPL"
    assert plan.position_side == "long"
    assert plan.entry_side == "buy"
    assert plan.exit_side == "sell"
    assert plan.quantity == 50
    assert plan.is_tradeable
    assert plan.planned_risk_dollars == 100.0
    assert plan.order_class == "bracket"


def test_build_short_bracket_order_plan():
    plan = build_bracket_order_plan(
        symbol="AAPL",
        strategy_version="ORB_RETEST_RECLAIM_BODY_2R",
        direction="SHORT",
        entry_price=100.0,
        stop_price=102.0,
        target_price=96.0,
        account_equity=10_000.0,
        risk_fraction=0.01,
    )

    assert plan.position_side == "short"
    assert plan.entry_side == "sell"
    assert plan.exit_side == "buy"
    assert plan.quantity == 50
    assert plan.planned_risk_dollars == 100.0


def test_build_bracket_order_plan_respects_notional_cap():
    plan = build_bracket_order_plan(
        symbol="AAPL",
        strategy_version="ORB_RETEST_RECLAIM_BODY_2R",
        direction="LONG",
        entry_price=100.0,
        stop_price=99.0,
        target_price=102.0,
        account_equity=10_000.0,
        risk_fraction=0.02,
        max_notional_fraction=0.5,
    )

    assert plan.quantity == 50
    assert plan.planned_risk_dollars == 50.0
    assert plan.risk_fraction == 0.005


def test_build_bracket_order_plan_can_return_untradeable_zero_quantity():
    plan = build_bracket_order_plan(
        symbol="AAPL",
        strategy_version="ORB_RETEST_RECLAIM_BODY_2R",
        direction="LONG",
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        account_equity=1_000.0,
        risk_fraction=0.001,
    )

    assert plan.quantity == 0
    assert not plan.is_tradeable


def test_build_long_bracket_order_plan_rejects_wrong_target_side():
    with pytest.raises(ValueError, match="Long target"):
        build_bracket_order_plan(
            symbol="AAPL",
            strategy_version="ORB_RETEST_RECLAIM_BODY_2R",
            direction="LONG",
            entry_price=100.0,
            stop_price=98.0,
            target_price=99.0,
            account_equity=10_000.0,
            risk_fraction=0.01,
        )


def test_build_short_bracket_order_plan_rejects_wrong_target_side():
    with pytest.raises(ValueError, match="Short target"):
        build_bracket_order_plan(
            symbol="AAPL",
            strategy_version="ORB_RETEST_RECLAIM_BODY_2R",
            direction="SHORT",
            entry_price=100.0,
            stop_price=102.0,
            target_price=101.0,
            account_equity=10_000.0,
            risk_fraction=0.01,
        )


def test_build_fixed_risk_bracket_order_plan_long():
    plan = build_fixed_risk_bracket_order_plan(
        symbol="NVDA",
        strategy_version="HTF_BREAKOUT_RETEST_2R",
        direction="LONG",
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        risk_dollars=100.0,
    )

    assert plan.quantity == 50
    assert plan.planned_risk_dollars == 100.0
    assert plan.entry_side == "buy"
    assert plan.exit_side == "sell"


def test_build_fixed_risk_bracket_order_plan_short():
    plan = build_fixed_risk_bracket_order_plan(
        symbol="AAPL",
        strategy_version="ORB_RETEST_RECLAIM_BODY_2R",
        direction="SHORT",
        entry_price=100.0,
        stop_price=102.0,
        target_price=96.0,
        risk_dollars=100.0,
    )

    assert plan.quantity == 50
    assert plan.planned_risk_dollars == 100.0
    assert plan.entry_side == "sell"
    assert plan.exit_side == "buy"
