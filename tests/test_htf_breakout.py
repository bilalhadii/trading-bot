import pandas as pd

from paper_trading.config import PaperTradingConfig
from paper_trading.htf_breakout import (
    HTFBreakoutConfig,
    build_htf_breakout_paper_trade_decision,
    classify_trend,
    detect_resistance_level,
    find_intraday_breakout_retest_signal,
)


def _daily(rows=45):
    base = pd.Timestamp("2024-01-01", tz="UTC")
    data = []
    for index in range(rows):
        close = 100 + index * 0.25
        high = close + 1
        if index in {30, 36}:
            high = 114.0
        data.append(
            {
                "timestamp": base + pd.Timedelta(days=index),
                "open": close - 0.2,
                "high": high,
                "low": close - 1,
                "close": close,
                "volume": 1000,
            }
        )
    return pd.DataFrame(data)


def _session(candles):
    base = pd.Timestamp("2024-03-01 09:30", tz="America/New_York")
    return pd.DataFrame(
        [
            {
                "timestamp_ny": base + pd.Timedelta(minutes=index),
                "open": candle[0],
                "high": candle[1],
                "low": candle[2],
                "close": candle[3],
                "volume": 1000,
            }
            for index, candle in enumerate(candles)
        ]
    )


def test_classify_trend_strong_bullish():
    state, details = classify_trend(_daily())

    assert state == "STRONG_BULLISH"
    assert details["daily_close"] > details["ema21"]


def test_detect_resistance_level_requires_touches():
    resistance, touches = detect_resistance_level(
        _daily(),
        HTFBreakoutConfig(),
    )

    assert resistance == 114.0
    assert touches >= 2


def test_find_intraday_breakout_retest_signal():
    df = _session(
        [
            (113.8, 114.0, 113.5, 113.9),
            (114.2, 115.0, 114.1, 114.8),
            (114.7, 114.8, 113.9, 114.3),
            (114.4, 115.0, 114.3, 114.9),
            (115.0, 115.4, 114.9, 115.2),
        ]
    )

    signal, reason = find_intraday_breakout_retest_signal(
        session_df=df,
        resistance=114.0,
        config=HTFBreakoutConfig(),
    )

    assert reason == "APPROVED"
    assert signal["direction"] == "LONG"
    assert signal["entry_price"] == 115.0


def test_build_htf_breakout_paper_trade_decision():
    session_df = _session(
        [
            (113.8, 114.0, 113.5, 113.9),
            (114.2, 115.0, 114.1, 114.8),
            (114.7, 114.8, 113.9, 114.3),
            (114.4, 115.0, 114.3, 114.9),
            (115.0, 115.4, 114.9, 115.2),
        ]
    )

    decision = build_htf_breakout_paper_trade_decision(
        daily_df=_daily(),
        session_df=session_df,
        symbol="AAPL",
        account_equity=10_000.0,
        paper_config=PaperTradingConfig(
            risk_fraction=0.01,
            max_trade_risk_fraction=0.01,
        ),
    )

    assert decision.approved
    assert decision.reason == "APPROVED"
    assert decision.plan.strategy_version == "HTF_BREAKOUT_RETEST_2R"
    assert decision.plan.position_side == "long"
