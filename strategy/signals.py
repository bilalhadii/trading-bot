from typing import Optional

import pandas as pd


def find_first_orb_breakout(
    session_df: pd.DataFrame,
    or_high: float,
    or_low: float,
) -> Optional[dict]:
    """
    Find the first confirmed ORB breakout after the
    opening range.

    A breakout is confirmed by candle CLOSE.

    Entry is assumed at the NEXT candle's OPEN,
    because the breakout candle's close is only
    known after that candle finishes.

    Returns None if no breakout occurs.
    """

    df = (
        session_df
        .copy()
        .sort_values("timestamp_ny")
        .reset_index(drop=True)
    )

    # Only evaluate candles from 09:35 onward.
    eligible_indices = df.index[
        df["timestamp_ny"].dt.time
        >= pd.Timestamp("09:35").time()
    ]

    for index in eligible_indices:

        # We need a NEXT candle for execution.
        if index + 1 >= len(df):
            return None

        candle = df.loc[index]
        next_candle = df.loc[index + 1]

        close = float(candle["close"])

        # Bullish breakout
        if close > or_high:
            return {
                "direction": "LONG",
                "breakout_timestamp": candle["timestamp_ny"],
                "breakout_close": close,
                "entry_timestamp": next_candle["timestamp_ny"],
                "entry_price": float(next_candle["open"]),
                "breakout_high": or_high,
                "breakout_low": or_low,
            }

        # Bearish breakout
        if close < or_low:
            return {
                "direction": "SHORT",
                "breakout_timestamp": candle["timestamp_ny"],
                "breakout_close": close,
                "entry_timestamp": next_candle["timestamp_ny"],
                "entry_price": float(next_candle["open"]),
                "breakout_high": or_high,
                "breakout_low": or_low,
            }

    return None