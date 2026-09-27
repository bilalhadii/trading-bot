from dataclasses import dataclass

import pytest

from scripts.paper_trade import format_approved_message, parse_strategies, parse_symbols


@dataclass
class FakeArgs:
    symbol: str = "AAPL"


@dataclass
class FakePlan:
    entry_side: str = "buy"
    quantity: int = 13
    entry_price_reference: float = 182.675
    stop_price: float = 181.75
    target_price: float = 184.525
    planned_risk_dollars: float = 12.025
    notional_dollars: float = 2374.775


@dataclass
class FakeDecision:
    plan: FakePlan
    signal: dict


def test_format_approved_message_is_readable_for_manual_execution():
    message = format_approved_message(
        args=FakeArgs(),
        decision=FakeDecision(
            plan=FakePlan(),
            signal={
                "breakout_timestamp": "2024-01-05 09:35",
                "retest_timestamp": "2024-01-05 09:36",
                "confirmation_timestamp": "2024-01-05 09:36",
            },
        ),
        dry_run=True,
    )

    assert "DRY RUN TRADE ALERT - AAPL" in message
    assert "Suggested action: BUY / go LONG" in message
    assert "Shares: 13" in message
    assert "Entry reference: 182.68" in message
    assert "Stop loss: 181.75" in message
    assert "Take profit: 184.53" in message
    assert "This GitHub alert does not place the trade" in message


def test_parse_symbols_accepts_comma_separated_symbols():
    assert parse_symbols(
        "AAPL",
        "aapl, nvda, SNDK, intc, googl, aapl",
    ) == ["AAPL", "NVDA", "SNDK", "INTC", "GOOGL"]


def test_parse_symbols_falls_back_to_single_symbol():
    assert parse_symbols("nvda") == ["NVDA"]


def test_parse_symbols_rejects_empty_list():
    with pytest.raises(ValueError, match="At least one symbol"):
        parse_symbols("AAPL", " , ")


def test_parse_strategies_accepts_known_lanes():
    assert parse_strategies(
        "ORB_RETEST_RECLAIM_BODY_2R, htf_breakout_retest_2r"
    ) == [
        "ORB_RETEST_RECLAIM_BODY_2R",
        "HTF_BREAKOUT_RETEST_2R",
    ]


def test_parse_strategies_rejects_unknown_lanes():
    with pytest.raises(ValueError, match="Unknown strategy"):
        parse_strategies("NOPE")
