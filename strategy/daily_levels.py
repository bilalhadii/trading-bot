import pandas as pd


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