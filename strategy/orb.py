import pandas as pd


def calculate_opening_range(
    session_df: pd.DataFrame,
    opening_minutes: int = 5,
) -> dict:
    """
    Calculate the opening range for one trading session.

    For a 5-minute ORB:
        09:30
        09:31
        09:32
        09:33
        09:34

    The breakout evaluation begins at 09:35.
    """

    if session_df.empty:
        raise ValueError("Session data is empty.")

    df = session_df.copy()

    df = df.sort_values("timestamp_ny")

    opening_end = (
        pd.Timestamp("09:30")
        + pd.Timedelta(minutes=opening_minutes)
    ).time()

    opening = df[
        (df["timestamp_ny"].dt.time >= pd.Timestamp("09:30").time())
        & (df["timestamp_ny"].dt.time < opening_end)
    ].copy()

    if len(opening) != opening_minutes:
        raise ValueError(
            f"Expected {opening_minutes} opening candles, "
            f"found {len(opening)}."
        )

    return {
        "or_open": opening.iloc[0]["open"],
        "or_close": opening.iloc[-1]["close"],
        "or_high": opening["high"].max(),
        "or_low": opening["low"].min(),
        "or_range": (
            opening["high"].max()
            - opening["low"].min()
        ),
        "or_volume": opening["volume"].sum(),
        "opening_candles": len(opening),
    }
