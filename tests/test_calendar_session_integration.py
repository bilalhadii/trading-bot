from datetime import time

import pandas as pd

from backtest.engine import simulate_trade
from scripts.run_backtest import prepare_calendar_session, is_strategy_session_eligible
from strategy.market_calendar import SessionQuality, get_expected_regular_session_minutes

NY = "America/New_York"


def make_df(date: str, missing=(), extras=()):
    minutes = list(get_expected_regular_session_minutes(date))
    rows = []
    missing_set = set(missing)
    for i, ts in enumerate(minutes):
        if ts.time() in missing_set:
            continue
        rows.append({
            "timestamp": ts.tz_convert("UTC"),
            "timestamp_ny": ts,
            "open": 100.0 + i * 0.01,
            "high": 101.0 + i * 0.01,
            "low": 99.0 + i * 0.01,
            "close": 100.5 + i * 0.01,
            "volume": 1000,
        })
    for ts in extras:
        rows.append({
            "timestamp": ts.tz_convert("UTC"),
            "timestamp_ny": ts,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000,
        })
    return pd.DataFrame(rows).sort_values("timestamp_ny").reset_index(drop=True)


def test_normal_390_minute_session_processed_normally():
    df = make_df("2023-07-05")
    session_df, report = prepare_calendar_session(df, pd.Timestamp("2023-07-05").date())
    assert report.quality == SessionQuality.COMPLETE
    assert is_strategy_session_eligible(report)
    assert len(session_df) == 390
    assert session_df.iloc[0]["timestamp_ny"].time() == time(9, 30)
    assert session_df.iloc[-1]["timestamp_ny"].time() == time(15, 59)


def test_scheduled_early_close_is_eligible_when_expected_minutes_present():
    df = make_df("2023-07-03")
    session_df, report = prepare_calendar_session(df, pd.Timestamp("2023-07-03").date())
    assert report.quality == SessionQuality.SCHEDULED_EARLY_CLOSE
    assert is_strategy_session_eligible(report)
    assert len(session_df) == 210


def test_early_close_session_dataframe_ends_at_scheduled_close_minus_one_minute():
    df = make_df("2023-07-03", extras=[pd.Timestamp("2023-07-03 13:00", tz=NY)])
    session_df, report = prepare_calendar_session(df, pd.Timestamp("2023-07-03").date())
    assert report.quality == SessionQuality.SCHEDULED_EARLY_CLOSE
    assert report.unexpected_extra_count == 0
    assert len(session_df) == 210
    assert session_df.iloc[-1]["timestamp_ny"].time() == time(12, 59)


def test_session_close_exit_uses_scheduled_early_close_session_end():
    df = make_df("2023-07-03")
    session_df, report = prepare_calendar_session(df, pd.Timestamp("2023-07-03").date())
    entry_time = session_df.iloc[5]["timestamp_ny"]
    result = simulate_trade(
        session_df=session_df,
        entry_time=entry_time,
        direction="LONG",
        entry_price=100.0,
        stop_price=1.0,
        target_price=1000.0,
    )
    assert result["outcome"] == "SESSION_CLOSE"
    assert result["exit_time"].time() == time(12, 59)


def test_early_close_not_rejected_for_fewer_than_390_bars():
    df = make_df("2023-11-24")
    session_df, report = prepare_calendar_session(df, pd.Timestamp("2023-11-24").date())
    assert len(session_df) < 390
    assert report.quality == SessionQuality.SCHEDULED_EARLY_CLOSE
    assert is_strategy_session_eligible(report)


def test_data_gap_session_is_excluded():
    df = make_df("2023-07-05", missing=[time(12, 42)])
    _, report = prepare_calendar_session(df, pd.Timestamp("2023-07-05").date())
    assert report.quality == SessionQuality.DATA_GAP
    assert not is_strategy_session_eligible(report)


def test_large_data_gap_session_is_excluded():
    # Missing a contiguous block at the scheduled open is structural.
    missing = [time(9, minute) for minute in range(30, 45)]
    df = make_df("2023-07-05", missing=missing)
    _, report = prepare_calendar_session(df, pd.Timestamp("2023-07-05").date())
    assert report.quality == SessionQuality.LARGE_DATA_GAP
    assert not is_strategy_session_eligible(report)


def test_missing_orb_minute_makes_session_unusable():
    df = make_df("2023-07-05", missing=[time(9, 34)])
    _, report = prepare_calendar_session(df, pd.Timestamp("2023-07-05").date())
    assert not report.opening_range_complete
    assert not is_strategy_session_eligible(report)


def test_weekend_and_holiday_are_excluded():
    weekend_df = make_df("2023-07-05")
    _, weekend_report = prepare_calendar_session(weekend_df, pd.Timestamp("2023-07-01").date())
    _, holiday_report = prepare_calendar_session(weekend_df, pd.Timestamp("2023-07-04").date())
    assert weekend_report.quality == SessionQuality.NO_SESSION
    assert holiday_report.quality == SessionQuality.NO_SESSION
    assert not is_strategy_session_eligible(weekend_report)
    assert not is_strategy_session_eligible(holiday_report)
