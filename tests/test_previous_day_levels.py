from datetime import date

import pandas as pd

from scripts.run_backtest import strategy_requires_previous_day_levels
from strategy.daily_levels import calculate_previous_session_levels
from strategy.market_calendar import get_expected_regular_session_minutes
from scripts.run_backtest import prepare_calendar_session, is_strategy_session_eligible


NY = "America/New_York"


def make_session_rows(session_date: str, *, high_base=100.0, low_base=90.0, extras=()):
    rows = []
    minutes = get_expected_regular_session_minutes(session_date)
    for index, ts in enumerate(minutes):
        rows.append(
            {
                "timestamp": ts.tz_convert("UTC"),
                "timestamp_ny": ts,
                "open": high_base - 1.0,
                "high": high_base + index * 0.01,
                "low": low_base - index * 0.01,
                "close": high_base - 0.5,
                "volume": 1000,
            }
        )
    for row in extras:
        rows.append(row)
    return rows


def make_df(rows):
    return pd.DataFrame(rows).sort_values("timestamp_ny").reset_index(drop=True)


def extended_row(timestamp: str, *, high: float, low: float):
    ts = pd.Timestamp(timestamp, tz=NY)
    return {
        "timestamp": ts.tz_convert("UTC"),
        "timestamp_ny": ts,
        "open": (high + low) / 2,
        "high": high,
        "low": low,
        "close": (high + low) / 2,
        "volume": 1000,
    }


def test_fixed_r_strategies_do_not_require_previous_day_levels():
    assert not strategy_requires_previous_day_levels("ORB_BASELINE_2R")
    assert not strategy_requires_previous_day_levels("ORB_RETEST_2R")
    assert not strategy_requires_previous_day_levels("ORB_RETEST_RECLAIM_2R")
    assert not strategy_requires_previous_day_levels("ORB_RETEST_RECLAIM_BODY_2R")


def test_first_2024_session_can_be_calendar_eligible_for_fixed_r_without_pdh_pdl():
    df = make_df(make_session_rows("2024-01-02"))
    _, report = prepare_calendar_session(df, date(2024, 1, 2))
    assert is_strategy_session_eligible(report)
    assert not strategy_requires_previous_day_levels("ORB_BASELINE_2R")


def test_previous_day_levels_use_previous_exchange_session():
    df = make_df(make_session_rows("2024-01-04", high_base=120.0, low_base=80.0))
    levels = calculate_previous_session_levels(df, date(2024, 1, 5))
    assert levels["previous_session"] == date(2024, 1, 4)
    assert levels["pdh"] > 120.0
    assert levels["pdl"] < 80.0


def test_friday_uses_thursday_as_previous_trading_session_when_applicable():
    df = make_df(make_session_rows("2024-01-04", high_base=130.0, low_base=70.0))
    levels = calculate_previous_session_levels(df, date(2024, 1, 5))
    assert levels["previous_session"] == date(2024, 1, 4)
    assert levels["pdh"] > 130.0
    assert levels["pdl"] < 70.0


def test_weekend_boundary_uses_prior_friday():
    df = make_df(make_session_rows("2024-01-05", high_base=140.0, low_base=60.0))
    levels = calculate_previous_session_levels(df, date(2024, 1, 8))
    assert levels["previous_session"] == date(2024, 1, 5)
    assert levels["pdh"] > 140.0
    assert levels["pdl"] < 60.0


def test_market_holiday_boundary_uses_previous_exchange_session():
    df = make_df(make_session_rows("2024-07-03", high_base=150.0, low_base=50.0))
    levels = calculate_previous_session_levels(df, date(2024, 7, 5))
    assert levels["previous_session"] == date(2024, 7, 3)
    assert levels["pdh"] > 150.0
    assert levels["pdl"] < 50.0


def test_scheduled_early_close_previous_session_can_supply_levels():
    df = make_df(make_session_rows("2023-11-24", high_base=160.0, low_base=40.0))
    levels = calculate_previous_session_levels(df, date(2023, 11, 27))
    assert levels["previous_session"] == date(2023, 11, 24)
    assert levels["pdh"] > 160.0
    assert levels["pdl"] < 40.0


def test_previous_session_levels_ignore_extended_hours():
    rows = make_session_rows(
        "2024-01-04",
        high_base=120.0,
        low_base=80.0,
        extras=[
            extended_row("2024-01-04 08:00", high=999.0, low=1.0),
            extended_row("2024-01-04 16:30", high=888.0, low=2.0),
        ],
    )
    df = make_df(rows)
    levels = calculate_previous_session_levels(df, date(2024, 1, 5))
    assert levels["pdh"] < 999.0
    assert levels["pdl"] > 2.0


def test_current_day_high_low_are_not_used_as_previous_day_levels():
    rows = []
    rows.extend(make_session_rows("2024-01-04", high_base=120.0, low_base=80.0))
    rows.extend(make_session_rows("2024-01-05", high_base=1000.0, low_base=1.0))
    df = make_df(rows)
    levels = calculate_previous_session_levels(df, date(2024, 1, 5))
    assert levels["previous_session"] == date(2024, 1, 4)
    assert levels["pdh"] < 1000.0
    assert levels["pdl"] > 1.0


def test_backtest_date_range_does_not_prevent_previous_session_lookup_when_data_exists():
    # Simulates a backtest beginning on 2024-01-02 while the dataframe still
    # contains the 2023-12-29 previous exchange session loaded separately.
    rows = []
    rows.extend(make_session_rows("2023-12-29", high_base=170.0, low_base=30.0))
    rows.extend(make_session_rows("2024-01-02", high_base=100.0, low_base=90.0))
    df = make_df(rows)
    levels = calculate_previous_session_levels(df, date(2024, 1, 2))
    assert levels["previous_session"] == date(2023, 12, 29)
    assert levels["pdh"] > 170.0
    assert levels["pdl"] < 30.0


def test_missing_previous_session_data_returns_no_pdh_pdl():
    df = make_df(make_session_rows("2024-01-02", high_base=100.0, low_base=90.0))
    levels = calculate_previous_session_levels(df, date(2024, 1, 2))
    assert levels["previous_session"] == date(2023, 12, 29)
    assert pd.isna(levels["pdh"])
    assert pd.isna(levels["pdl"])
