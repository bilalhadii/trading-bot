from typing import Optional

import pandas as pd


def simulate_trade(
    session_df: pd.DataFrame,
    entry_time: pd.Timestamp,
    direction: str,
    entry_price: float,
    stop_price: float,
    target_price: float,
    break_even_r: Optional[float] = None,
) -> dict:
    """
    Simulate a trade candle-by-candle.

    Optional break-even rule:

        When price reaches +break_even_r * initial_risk,
        move the stop to the entry price.

    Conservative same-candle rule:

        If both stop and target are touched and the order
        of events cannot be determined from OHLC data,
        stop is assumed to occur first.
    """

    df = (
        session_df[
            session_df["timestamp_ny"] >= entry_time
        ]
        .copy()
        .sort_values("timestamp_ny")
        .reset_index(drop=True)
    )

    if df.empty:
        return {
            "exit_time": entry_time,
            "exit_price": entry_price,
            "outcome": "NO_DATA",
            "r_multiple": 0.0,
        }

    direction = direction.upper()

    if direction == "LONG":
        initial_risk = entry_price - stop_price

        if initial_risk <= 0:
            raise ValueError("Invalid LONG risk.")

        break_even_price = (
            entry_price
            + initial_risk * break_even_r
            if break_even_r is not None
            else None
        )

    elif direction == "SHORT":
        initial_risk = stop_price - entry_price

        if initial_risk <= 0:
            raise ValueError("Invalid SHORT risk.")

        break_even_price = (
            entry_price
            - initial_risk * break_even_r
            if break_even_r is not None
            else None
        )

    else:
        raise ValueError(
            f"Invalid direction: {direction}"
        )

    current_stop = stop_price
    break_even_activated = False

    for _, candle in df.iterrows():

        candle_high = float(candle["high"])
        candle_low = float(candle["low"])
        timestamp = candle["timestamp_ny"]

        # --------------------------------------------------
        # LONG
        # --------------------------------------------------
        if direction == "LONG":

            # Determine whether +1R / chosen threshold was reached.
            if (
                break_even_price is not None
                and not break_even_activated
                and candle_high >= break_even_price
            ):
                break_even_activated = True
                current_stop = entry_price

            stop_hit = candle_low <= current_stop
            target_hit = candle_high >= target_price

            # Conservative ordering.
            if stop_hit:
                if break_even_activated:
                    return {
                        "exit_time": timestamp,
                        "exit_price": entry_price,
                        "outcome": "BREAKEVEN",
                        "r_multiple": 0.0,
                    }

                return {
                    "exit_time": timestamp,
                    "exit_price": current_stop,
                    "outcome": "LOSS",
                    "r_multiple": -1.0,
                }

            if target_hit:

                pnl = target_price - entry_price

                return {
                    "exit_time": timestamp,
                    "exit_price": target_price,
                    "outcome": "WIN",
                    "r_multiple": pnl / initial_risk,
                }

        # --------------------------------------------------
        # SHORT
        # --------------------------------------------------
        else:

            if (
                break_even_price is not None
                and not break_even_activated
                and candle_low <= break_even_price
            ):
                break_even_activated = True
                current_stop = entry_price

            stop_hit = candle_high >= current_stop
            target_hit = candle_low <= target_price

            if stop_hit:
                if break_even_activated:
                    return {
                        "exit_time": timestamp,
                        "exit_price": entry_price,
                        "outcome": "BREAKEVEN",
                        "r_multiple": 0.0,
                    }

                return {
                    "exit_time": timestamp,
                    "exit_price": current_stop,
                    "outcome": "LOSS",
                    "r_multiple": -1.0,
                }

            if target_hit:

                pnl = entry_price - target_price

                return {
                    "exit_time": timestamp,
                    "exit_price": target_price,
                    "outcome": "WIN",
                    "r_multiple": pnl / initial_risk,
                }

    # ------------------------------------------------------
    # SESSION CLOSE
    # ------------------------------------------------------

    final_candle = df.iloc[-1]

    exit_price = float(final_candle["close"])

    if direction == "LONG":
        pnl = exit_price - entry_price
    else:
        pnl = entry_price - exit_price

    return {
        "exit_time": final_candle["timestamp_ny"],
        "exit_price": exit_price,
        "outcome": "SESSION_CLOSE",
        "r_multiple": pnl / initial_risk,
    }