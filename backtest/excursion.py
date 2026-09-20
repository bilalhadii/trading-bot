import pandas as pd


def calculate_excursion(
    session_df: pd.DataFrame,
    entry_time: pd.Timestamp,
    exit_time: pd.Timestamp,
    entry_price: float,
    direction: str,
    stop_price: float,
    target_price: float,
) -> dict:
    """
    Calculate Maximum Adverse Excursion (MAE)
    and Maximum Favorable Excursion (MFE)
    only while the trade is actually open.

    MAE:
        Maximum movement against the position.

    MFE:
        Maximum movement in favor of the position.
    """

    df = (
        session_df[
            (session_df["timestamp_ny"] >= entry_time)
            & (session_df["timestamp_ny"] <= exit_time)
        ]
        .copy()
        .sort_values("timestamp_ny")
    )

    if df.empty:
        return {
            "mae_price": 0.0,
            "mfe_price": 0.0,
            "mae_r": 0.0,
            "mfe_r": 0.0,
        }

    direction = direction.upper()

    risk = abs(entry_price - stop_price)

    if risk <= 0:
        raise ValueError(
            "Risk must be greater than zero."
        )

    if direction == "LONG":

        lowest = float(df["low"].min())
        highest = float(df["high"].max())

        adverse_distance = max(
            entry_price - lowest,
            0.0,
        )

        favorable_distance = max(
            highest - entry_price,
            0.0,
        )

    elif direction == "SHORT":

        highest = float(df["high"].max())
        lowest = float(df["low"].min())

        adverse_distance = max(
            highest - entry_price,
            0.0,
        )

        favorable_distance = max(
            entry_price - lowest,
            0.0,
        )

    else:
        raise ValueError(
            f"Invalid direction: {direction}"
        )

    mae_price = -adverse_distance
    mfe_price = favorable_distance

    return {
        "mae_price": mae_price,
        "mfe_price": mfe_price,
        "mae_r": mae_price / risk,
        "mfe_r": mfe_price / risk,
    }