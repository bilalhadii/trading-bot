import pandas as pd


REQUIRED_COLUMNS = [
    "ticker",
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
]


def validate_candles(df: pd.DataFrame) -> None:
    """
    Validate the market candle DataFrame.
    Raises ValueError if a problem is found.
    """

    if df.empty:
        raise ValueError("DataFrame is empty.")

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing columns: {missing}"
        )

    if df["timestamp"].isna().any():
        raise ValueError(
            "Found null timestamps."
        )

    if not df["timestamp"].is_monotonic_increasing:
        raise ValueError(
            "Timestamps are not sorted."
        )

    if df.duplicated(
        subset=["ticker", "timestamp"]
    ).any():
        raise ValueError(
            "Duplicate ticker/timestamp rows found."
        )

    if (df["high"] < df["low"]).any():
        raise ValueError(
            "Found candle where high < low."
        )

    if (df["volume"] < 0).any():
        raise ValueError(
            "Found negative volume."
        )