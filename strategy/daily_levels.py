import pandas as pd

from strategy.market_calendar import (
    SessionQuality,
    compare_session_minutes,
    get_expected_regular_session_minutes,
    get_previous_exchange_session,
)


def calculate_daily_levels(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate regular-session daily high/low and
    previous-day high/low.

    Input must contain:
        timestamp_ny
        high
        low
    """

    data = df.copy()

    if "timestamp_ny" not in data.columns:
        raise ValueError(
            "timestamp_ny column is required."
        )

    data["trading_date"] = (
        data["timestamp_ny"].dt.date
    )

    daily = (
        data.groupby("trading_date")
        .agg(
            day_high=("high", "max"),
            day_low=("low", "min"),
        )
        .sort_index()
    )

    daily["pdh"] = daily["day_high"].shift(1)
    daily["pdl"] = daily["day_low"].shift(1)

    return daily


def calculate_previous_session_levels(
    df: pd.DataFrame,
    trading_date,
) -> dict:
    """
    Calculate PDH/PDL from the previous XNYS exchange session.

    Only scheduled regular-session minutes from the previous exchange
    session are used. Extended-hours candles, current-day candles, and
    future sessions are ignored. Missing or incomplete previous-session
    data returns pd.NA levels rather than fabricated values.

    TODO: raw/unadjusted candles across split-effective dates need explicit
    research treatment before PDH/PDL-dependent strategies use them live.
    """

    data = df.copy()

    if "timestamp_ny" not in data.columns:
        raise ValueError(
            "timestamp_ny column is required."
        )

    data["timestamp_ny"] = pd.to_datetime(
        data["timestamp_ny"],
        utc=True,
    ).dt.tz_convert("America/New_York")

    previous_session = get_previous_exchange_session(
        trading_date,
    )

    expected_minutes = get_expected_regular_session_minutes(
        previous_session,
    )

    if expected_minutes.empty:
        return {
            "previous_session": previous_session,
            "pdh": pd.NA,
            "pdl": pd.NA,
        }

    day_data = data[
        data["timestamp_ny"].dt.date == previous_session
    ].copy()

    expected_set = set(expected_minutes)
    regular_data = day_data[
        day_data["timestamp_ny"].dt.floor("min").isin(expected_set)
    ].copy()

    report = compare_session_minutes(
        previous_session,
        regular_data["timestamp_ny"],
    )

    if report.quality not in {
        SessionQuality.COMPLETE,
        SessionQuality.SCHEDULED_EARLY_CLOSE,
    }:
        return {
            "previous_session": previous_session,
            "pdh": pd.NA,
            "pdl": pd.NA,
        }

    if regular_data.empty:
        return {
            "previous_session": previous_session,
            "pdh": pd.NA,
            "pdl": pd.NA,
        }

    return {
        "previous_session": previous_session,
        "pdh": float(regular_data["high"].max()),
        "pdl": float(regular_data["low"].min()),
    }
