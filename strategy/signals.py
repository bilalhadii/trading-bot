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


def find_first_orb_retest(
    session_df: pd.DataFrame,
    or_high: float,
    or_low: float,
    max_bars: int,
    tolerance_or_fraction: float,
) -> Optional[dict]:
    """Find a retest/confirmation of only the first confirmed ORB breakout.

    Both retest and confirmation must occur in the next ``max_bars`` bars.
    The first candle whose high/low overlaps the inclusive boundary band
    fixes the retest high/low. Confirmation must be on a later candle and
    close strictly beyond that extreme. Invalidation is checked first on
    every setup candle, including a possible retest or confirmation candle.

    Entry is the next available candle's open, which may be outside the
    setup window but must remain in this session. Input is one sorted or
    unsorted regular session of one-minute candles. No second breakout or
    replacement retest is considered. The breakout's immediate entry fields
    are ignored and replaced only after confirmation.
    """
    if isinstance(max_bars, bool) or not isinstance(max_bars, int) or max_bars < 1:
        raise ValueError("max_bars must be a positive integer.")
    if not 0 <= tolerance_or_fraction < float("inf"):
        raise ValueError("tolerance_or_fraction must be finite and nonnegative.")
    or_high, or_low = float(or_high), float(or_low)
    if not 0 < or_high - or_low < float("inf"):
        raise ValueError("Opening range must be finite and positive.")

    df = session_df.sort_values("timestamp_ny").reset_index(drop=True)
    breakout = find_first_orb_breakout(df, or_high, or_low)
    if breakout is None:
        return None

    is_long = breakout["direction"] == "LONG"
    boundary = or_high if is_long else or_low
    tolerance = (or_high - or_low) * tolerance_or_fraction
    lower, upper = boundary - tolerance, boundary + tolerance
    breakout_index = df.index[
        df["timestamp_ny"] == breakout["breakout_timestamp"]
    ][0]
    retest = None

    for index in range(breakout_index + 1, min(breakout_index + max_bars + 1, len(df))):
        candle = df.iloc[index]
        close = float(candle["close"])
        if (is_long and close < lower) or (not is_long and close > upper):
            return None

        if retest is None:
            if float(candle["low"]) <= upper and float(candle["high"]) >= lower:
                retest = candle
            continue

        confirmed = (
            close > float(retest["high"])
            if is_long else close < float(retest["low"])
        )
        if confirmed:
            if index + 1 >= len(df):
                return None
            entry = df.iloc[index + 1]
            return {
                **breakout,
                "retest_timestamp": retest["timestamp_ny"],
                "confirmation_timestamp": candle["timestamp_ny"],
                "retest_tolerance": tolerance,
                "entry_timestamp": entry["timestamp_ny"],
                "entry_price": float(entry["open"]),
            }

    return None


def find_first_orb_retest_reclaim(
    session_df: pd.DataFrame,
    or_high: float,
    or_low: float,
    max_bars: int,
    tolerance_or_fraction: float,
) -> Optional[dict]:
    """Confirm on the first retest itself, then enter at the next open.

    Use only the first breakout and its next max_bars candles. Invalidation
    precedes inclusive band-overlap detection, exactly as in the original
    retest strategy. The first overlap must close strictly beyond the broken
    OR boundary in the breakout direction; otherwise fail immediately.
    There is no replacement retest or additional confirmation candle.
    Input is one regular session of one-minute candles. Entry may be outside
    the setup window, but must still have a candle in the same session.
    """
    if isinstance(max_bars, bool) or not isinstance(max_bars, int) or max_bars < 1:
        raise ValueError("max_bars must be a positive integer.")
    if not 0 <= tolerance_or_fraction < float("inf"):
        raise ValueError("tolerance_or_fraction must be finite and nonnegative.")
    or_high, or_low = float(or_high), float(or_low)
    if not 0 < or_high - or_low < float("inf"):
        raise ValueError("Opening range must be finite and positive.")

    df = session_df.sort_values("timestamp_ny").reset_index(drop=True)
    breakout = find_first_orb_breakout(df, or_high, or_low)
    if breakout is None:
        return None

    is_long = breakout["direction"] == "LONG"
    boundary = or_high if is_long else or_low
    tolerance = (or_high - or_low) * tolerance_or_fraction
    lower, upper = boundary - tolerance, boundary + tolerance
    breakout_index = df.index[
        df["timestamp_ny"] == breakout["breakout_timestamp"]
    ][0]
    window_end = min(breakout_index + max_bars + 1, len(df))
    for index in range(breakout_index + 1, window_end):
        candle = df.iloc[index]
        close = float(candle["close"])
        if (is_long and close < lower) or (not is_long and close > upper):
            return None
        if float(candle["low"]) <= upper and float(candle["high"]) >= lower:
            reclaimed = close > boundary if is_long else close < boundary
            if not reclaimed or index + 1 >= len(df):
                return None
            entry = df.iloc[index + 1]
            return {
                **breakout,
                "retest_timestamp": candle["timestamp_ny"],
                "confirmation_timestamp": candle["timestamp_ny"],
                "retest_tolerance": tolerance,
                "entry_timestamp": entry["timestamp_ny"],
                "entry_price": float(entry["open"]),
            }
    return None
