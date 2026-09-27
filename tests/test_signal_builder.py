import pandas as pd

from paper_trading.config import PaperTradingConfig
from paper_trading.signal_builder import build_retest_body_paper_trade_decision


def _session(candles):
    base = pd.Timestamp("2024-01-02 09:30", tz="America/New_York")
    rows = []
    for index, candle in enumerate(candles):
        rows.append(
            {
                "timestamp_ny": base + pd.Timedelta(minutes=index),
                "open": candle[0],
                "high": candle[1],
                "low": candle[2],
                "close": candle[3],
                "volume": 1000,
            }
        )
    return pd.DataFrame(rows)


def test_build_retest_body_paper_trade_decision_for_long_signal():
    df = _session(
        [
            (100.0, 101.0, 99.0, 100.5),
            (100.5, 101.2, 99.5, 100.7),
            (100.7, 101.3, 99.8, 100.9),
            (100.9, 101.4, 99.9, 101.0),
            (101.0, 101.5, 100.0, 101.1),
            (101.2, 102.0, 101.1, 101.8),
            (101.6, 101.8, 101.4, 101.7),
            (101.9, 102.4, 101.8, 102.2),
        ]
    )

    decision = build_retest_body_paper_trade_decision(
        session_df=df,
        symbol="AAPL",
        account_equity=10_000.0,
        config=PaperTradingConfig(risk_fraction=0.01, max_trade_risk_fraction=0.01),
    )

    assert decision.approved
    assert decision.reason == "APPROVED"
    assert decision.plan is not None
    assert decision.plan.position_side == "long"
    assert decision.plan.quantity == 24
    assert decision.signal["confirmation_timestamp"] == df.loc[6, "timestamp_ny"]


def test_build_retest_body_paper_trade_decision_for_short_signal():
    df = _session(
        [
            (100.0, 101.0, 99.0, 99.8),
            (99.8, 100.5, 98.8, 99.2),
            (99.2, 100.0, 98.7, 99.0),
            (99.0, 100.2, 98.6, 98.9),
            (98.9, 100.0, 98.5, 98.8),
            (98.4, 98.6, 97.8, 98.0),
            (98.2, 98.7, 98.0, 98.1),
            (97.9, 98.0, 97.5, 97.7),
        ]
    )

    decision = build_retest_body_paper_trade_decision(
        session_df=df,
        symbol="AAPL",
        account_equity=10_000.0,
        config=PaperTradingConfig(risk_fraction=0.01, max_trade_risk_fraction=0.01),
    )

    assert decision.approved
    assert decision.reason == "APPROVED"
    assert decision.plan is not None
    assert decision.plan.position_side == "short"
    assert decision.signal["confirmation_timestamp"] == df.loc[6, "timestamp_ny"]


def test_build_retest_body_paper_trade_decision_returns_no_signal():
    df = _session(
        [
            (100.0, 101.0, 99.0, 100.5),
            (100.5, 101.2, 99.5, 100.7),
            (100.7, 101.3, 99.8, 100.9),
            (100.9, 101.4, 99.9, 101.0),
            (101.0, 101.5, 100.0, 101.1),
            (101.1, 101.4, 100.2, 101.0),
        ]
    )

    decision = build_retest_body_paper_trade_decision(
        session_df=df,
        symbol="AAPL",
        account_equity=10_000.0,
        config=PaperTradingConfig(),
    )

    assert not decision.approved
    assert decision.reason == "NO_VALID_SIGNAL"


def test_build_retest_body_paper_trade_decision_applies_risk_lockout():
    df = _session(
        [
            (100.0, 101.0, 99.0, 100.5),
            (100.5, 101.2, 99.5, 100.7),
            (100.7, 101.3, 99.8, 100.9),
            (100.9, 101.4, 99.9, 101.0),
            (101.0, 101.5, 100.0, 101.1),
            (101.2, 102.0, 101.1, 101.8),
            (101.6, 101.8, 101.4, 101.7),
            (101.9, 102.4, 101.8, 102.2),
        ]
    )

    decision = build_retest_body_paper_trade_decision(
        session_df=df,
        symbol="AAPL",
        account_equity=10_000.0,
        config=PaperTradingConfig(risk_fraction=0.01, max_trade_risk_fraction=0.01),
        realized_daily_pnl=-100.0,
    )

    assert not decision.approved
    assert decision.reason == "DAILY_LOSS_LIMIT"
