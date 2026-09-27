import pytest

from backtest.position_sizing import (
    calculate_execution_result,
    calculate_risk_per_share,
    calculate_round_trip_execution_costs,
    calculate_share_quantity,
    calculate_trade_pnl_per_share,
)


def test_calculate_risk_per_share_long_and_short():
    assert calculate_risk_per_share("LONG", 100.0, 98.5) == 1.5
    assert calculate_risk_per_share("SHORT", 100.0, 102.25) == 2.25


def test_calculate_risk_per_share_rejects_invalid_risk():
    with pytest.raises(ValueError, match="Risk per share"):
        calculate_risk_per_share("LONG", 100.0, 101.0)

    with pytest.raises(ValueError, match="Risk per share"):
        calculate_risk_per_share("SHORT", 100.0, 99.0)


def test_calculate_share_quantity_risk_limited():
    size = calculate_share_quantity(
        account_equity=10_000.0,
        risk_fraction=0.01,
        direction="LONG",
        entry_price=100.0,
        stop_price=98.0,
    )

    assert size.shares == 50
    assert size.risk_per_share == 2.0
    assert size.planned_risk_dollars == 100.0
    assert size.notional_dollars == 5_000.0
    assert size.risk_fraction == 0.01


def test_calculate_share_quantity_respects_notional_limit():
    size = calculate_share_quantity(
        account_equity=10_000.0,
        risk_fraction=0.02,
        direction="LONG",
        entry_price=100.0,
        stop_price=99.0,
        max_notional_fraction=0.5,
    )

    assert size.shares == 50
    assert size.planned_risk_dollars == 50.0
    assert size.notional_dollars == 5_000.0
    assert size.risk_fraction == 0.005


def test_calculate_share_quantity_returns_zero_when_risk_is_too_small():
    size = calculate_share_quantity(
        account_equity=1_000.0,
        risk_fraction=0.001,
        direction="LONG",
        entry_price=100.0,
        stop_price=98.0,
    )

    assert size.shares == 0
    assert size.planned_risk_dollars == 0.0
    assert size.risk_fraction == 0.0


def test_calculate_trade_pnl_per_share_long_and_short():
    assert calculate_trade_pnl_per_share("LONG", 100.0, 103.0) == 3.0
    assert calculate_trade_pnl_per_share("SHORT", 100.0, 97.0) == 3.0


def test_calculate_round_trip_execution_costs():
    commission, slippage = calculate_round_trip_execution_costs(
        entry_price=100.0,
        exit_price=102.0,
        shares=50,
        commission_per_share=0.005,
        slippage_bps=1.0,
    )

    assert commission == pytest.approx(0.5)
    assert slippage == pytest.approx(1.01)


def test_calculate_execution_result_long_net_r():
    result = calculate_execution_result(
        direction="LONG",
        entry_price=100.0,
        stop_price=98.0,
        exit_price=104.0,
        shares=50,
        commission_per_share=0.005,
        slippage_bps=1.0,
    )

    assert result.gross_pnl_dollars == 200.0
    assert result.commission_dollars == pytest.approx(0.5)
    assert result.slippage_dollars == pytest.approx(1.02)
    assert result.net_pnl_dollars == pytest.approx(198.48)
    assert result.gross_r_multiple == 2.0
    assert result.net_r_multiple == pytest.approx(1.9848)


def test_calculate_execution_result_short_net_r():
    result = calculate_execution_result(
        direction="SHORT",
        entry_price=100.0,
        stop_price=102.0,
        exit_price=96.0,
        shares=50,
        commission_per_share=0.005,
        slippage_bps=1.0,
    )

    assert result.gross_pnl_dollars == 200.0
    assert result.net_r_multiple == pytest.approx(1.9852)
