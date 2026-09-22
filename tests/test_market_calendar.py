from datetime import time

import pandas as pd
import pytest

from strategy.market_calendar import (
    SessionQuality,
    compare_session_minutes,
    get_expected_market_close,
    get_expected_market_open,
    get_expected_regular_session_minutes,
    get_session_type,
)

NY = "America/New_York"


def minutes_for(date: str):
    return list(get_expected_regular_session_minutes(date))


def remove_times(minutes, *times):
    remove = set(times)
    return [ts for ts in minutes if ts.time() not in remove]


def test_normal_390_minute_session():
    actual = minutes_for("2023-07-05")
    report = compare_session_minutes("2023-07-05", actual)
    assert report.quality == SessionQuality.COMPLETE
    assert report.expected_bar_count == 390
    assert report.actual_bar_count == 390
    assert report.usable_for_orb is True


def test_scheduled_early_close():
    actual = minutes_for("2023-07-03")
    report = compare_session_minutes("2023-07-03", actual)
    assert report.quality == SessionQuality.SCHEDULED_EARLY_CLOSE
    assert report.expected_bar_count == 210
    assert report.expected_close.time() == time(13, 0)
    assert report.usable_for_orb is True


def test_weekend_no_session():
    report = compare_session_minutes("2023-07-01", [])
    assert report.quality == SessionQuality.NO_SESSION
    assert report.usable_for_orb is False


def test_exchange_holiday_no_session():
    report = compare_session_minutes("2023-07-04", [])
    assert report.quality == SessionQuality.NO_SESSION
    assert get_session_type("2023-07-04") == SessionQuality.NO_SESSION


def test_one_missing_minute():
    actual = remove_times(minutes_for("2023-07-05"), time(12, 42))
    report = compare_session_minutes("2023-07-05", actual)
    assert report.quality == SessionQuality.DATA_GAP
    assert report.missing_bar_count == 1
    assert report.gap_blocks[0].minutes == 1
    assert report.usable_for_orb is False


def test_multiple_isolated_missing_minutes():
    actual = remove_times(minutes_for("2023-07-05"), time(12, 1), time(13, 2), time(14, 3))
    report = compare_session_minutes("2023-07-05", actual)
    assert report.quality == SessionQuality.DATA_GAP
    assert report.missing_bar_count == 3
    assert [block.minutes for block in report.gap_blocks] == [1, 1, 1]


def test_large_contiguous_data_gap_with_explicit_reporting_boundary():
    actual = remove_times(minutes_for("2023-07-05"), *[time(10, m) for m in range(0, 45)])
    report = compare_session_minutes("2023-07-05", actual, large_gap_min_minutes=30)
    assert report.quality == SessionQuality.LARGE_DATA_GAP
    assert report.gap_blocks[0].minutes == 45
    assert report.usable_for_orb is False


def test_missing_0930_opening_range_bar():
    actual = remove_times(minutes_for("2023-07-05"), time(9, 30))
    report = compare_session_minutes("2023-07-05", actual)
    assert report.opening_range_complete is False
    assert report.unusable_reason == "MISSING_OPENING_RANGE_MINUTE"


def test_missing_0934_opening_range_bar():
    actual = remove_times(minutes_for("2023-07-05"), time(9, 34))
    report = compare_session_minutes("2023-07-05", actual)
    assert report.opening_range_complete is False
    assert report.unusable_reason == "MISSING_OPENING_RANGE_MINUTE"


def test_extra_bar_after_scheduled_close_is_reported_without_invalidating_schedule():
    actual = minutes_for("2023-07-03") + [pd.Timestamp("2023-07-03 13:00", tz=NY)]
    report = compare_session_minutes("2023-07-03", actual)
    assert report.quality == SessionQuality.SCHEDULED_EARLY_CLOSE
    assert report.missing_bar_count == 0
    assert report.unexpected_extra_count == 1
    assert report.usable_for_orb is True


def test_daylight_saving_time_transition_offsets():
    before = get_expected_market_open("2023-03-10")
    after = get_expected_market_open("2023-03-13")
    assert before.tzinfo is not None
    assert after.tzinfo is not None
    assert before.time() == time(9, 30)
    assert after.time() == time(9, 30)
    assert str(before.utcoffset()) == "-1 day, 19:00:00"
    assert str(after.utcoffset()) == "-1 day, 20:00:00"


def test_timezone_handling_accepts_utc_and_returns_new_york():
    actual_utc = get_expected_regular_session_minutes("2023-07-05").tz_convert("UTC")
    report = compare_session_minutes("2023-07-05", actual_utc)
    assert report.quality == SessionQuality.COMPLETE
    assert report.expected_open.tz.zone if hasattr(report.expected_open.tz, "zone") else str(report.expected_open.tz)
    assert report.expected_open.time() == time(9, 30)


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValueError):
        compare_session_minutes("2023-07-05", [pd.Timestamp("2023-07-05 09:30")])


def test_2020_halt_day_is_not_scheduled_early_close():
    actual = remove_times(minutes_for("2020-03-09"), *[time(9, m) for m in range(35, 49)])
    report = compare_session_minutes("2020-03-09", actual)
    assert report.is_scheduled_early_close is False
    assert report.expected_bar_count == 390
    assert report.quality == SessionQuality.DATA_GAP
