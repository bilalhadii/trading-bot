import pandas as pd


NEW_YORK_TZ = "America/New_York"


def add_new_york_time(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add a New York timezone-aware timestamp column.
    """

    result = df.copy()

    result["timestamp_ny"] = (
        result["timestamp"]
        .dt.tz_convert(NEW_YORK_TZ)
    )

    return result


def regular_session(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Keep only regular NYSE/Nasdaq trading hours:
    09:30 inclusive through 16:00 exclusive.
    """

    result = df.copy()

    if "timestamp_ny" not in result.columns:
        result = add_new_york_time(result)

    times = result["timestamp_ny"].dt.time

    market_open = pd.Timestamp("09:30").time()
    market_close = pd.Timestamp("16:00").time()

    result = result[
        (times >= market_open)
        & (times < market_close)
    ].copy()

    return result