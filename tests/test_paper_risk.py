import pytest

from paper_trading.order_plan import build_bracket_order_plan
from paper_trading.risk import RiskLimits, check_order_risk


def _plan():
    return build_bracket_order_plan(
        symbol="AAPL",
        strategy_version="ORB_RETEST_RECLAIM_BODY_2R",
        direction="LONG",
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        account_equity=10_000.0,
        risk_fraction=0.01,
    )


def test_check_order_risk_approves_valid_plan():
    result = check_order_risk(
        plan=_plan(),
        account_equity=10_000.0,
        limits=RiskLimits(
            max_trade_risk_fraction=0.01,
            max_notional_fraction=1.0,
            max_daily_loss_fraction=0.03,
        ),
    )

    assert result.approved
    assert result.reason == "APPROVED"


def test_check_order_risk_rejects_zero_quantity():
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

    result = check_order_risk(
        plan=plan,
        account_equity=1_000.0,
        limits=RiskLimits(
            max_trade_risk_fraction=0.01,
            max_notional_fraction=1.0,
            max_daily_loss_fraction=0.03,
        ),
    )

    assert not result.approved
    assert result.reason == "ZERO_QUANTITY"


def test_check_order_risk_rejects_short_when_disabled():
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

    result = check_order_risk(
        plan=plan,
        account_equity=10_000.0,
        limits=RiskLimits(
            max_trade_risk_fraction=0.01,
            max_notional_fraction=1.0,
            max_daily_loss_fraction=0.03,
            allow_short_selling=False,
        ),
    )

    assert not result.approved
    assert result.reason == "SHORT_SELLING_DISABLED"


def test_check_order_risk_rejects_trade_risk_over_limit():
    result = check_order_risk(
        plan=_plan(),
        account_equity=10_000.0,
        limits=RiskLimits(
            max_trade_risk_fraction=0.005,
            max_notional_fraction=1.0,
            max_daily_loss_fraction=0.03,
        ),
    )

    assert not result.approved
    assert result.reason == "TRADE_RISK_LIMIT"


def test_check_order_risk_rejects_notional_over_limit():
    result = check_order_risk(
        plan=_plan(),
        account_equity=10_000.0,
        limits=RiskLimits(
            max_trade_risk_fraction=0.01,
            max_notional_fraction=0.25,
            max_daily_loss_fraction=0.03,
        ),
    )

    assert not result.approved
    assert result.reason == "NOTIONAL_LIMIT"


def test_check_order_risk_rejects_daily_loss_lockout():
    result = check_order_risk(
        plan=_plan(),
        account_equity=10_000.0,
        limits=RiskLimits(
            max_trade_risk_fraction=0.01,
            max_notional_fraction=1.0,
            max_daily_loss_fraction=0.03,
        ),
        realized_daily_pnl=-300.0,
    )

    assert not result.approved
    assert result.reason == "DAILY_LOSS_LIMIT"


def test_check_order_risk_rejects_invalid_account_equity():
    with pytest.raises(ValueError, match="Account equity"):
        check_order_risk(
            plan=_plan(),
            account_equity=0.0,
            limits=RiskLimits(
                max_trade_risk_fraction=0.01,
                max_notional_fraction=1.0,
                max_daily_loss_fraction=0.03,
            ),
        )
