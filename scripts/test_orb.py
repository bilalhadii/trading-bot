import pandas as pd
from sqlalchemy import text
from strategy.trade_setup import calculate_trade_setup

from database.connection import engine
from strategy.daily_levels import calculate_daily_levels
from strategy.orb import calculate_opening_range
from strategy.session import add_new_york_time, regular_session
from strategy.signals import find_first_orb_breakout


def load_date_range(
    ticker: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:

    query = text("""
        SELECT
            ticker,
            timestamp,
            open,
            high,
            low,
            close,
            volume,
            trade_count,
            vwap
        FROM market_candles
        WHERE ticker = :ticker
          AND DATE(
              timestamp AT TIME ZONE 'America/New_York'
          ) BETWEEN :start_date AND :end_date
        ORDER BY timestamp;
    """)

    with engine.connect() as conn:
        df = pd.read_sql(
            query,
            conn,
            params={
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    if df.empty:
        raise ValueError(
            f"No data found for {ticker} "
            f"between {start_date} and {end_date}"
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
    )

    return df


def main() -> None:

    ticker = "AAPL"

    # We load Jan 2 AND Jan 3 because
    # Jan 2 is needed to calculate Jan 3 PDH/PDL.
    start_date = "2024-01-02"
    end_date = "2024-01-03"

    target_date = "2024-01-03"

    df = load_date_range(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
    )

    print(f"Total rows loaded: {len(df)}")

    df = add_new_york_time(df)

    regular = regular_session(df)

    print(
        f"Regular-session rows: {len(regular)}"
    )

    # --------------------------------------------------
    # DAILY LEVELS
    # --------------------------------------------------

    daily_levels = calculate_daily_levels(
        regular
    )

    print()
    print("DAILY LEVELS")
    print("-" * 40)

    print(
        daily_levels.to_string()
    )

    # --------------------------------------------------
    # TARGET DAY
    # --------------------------------------------------

    target_session = regular[
        regular["timestamp_ny"].dt.date
        == pd.Timestamp(target_date).date()
    ].copy()

    if len(target_session) != 390:
        raise ValueError(
            f"Expected 390 bars for {target_date}, "
            f"found {len(target_session)}."
        )

    # --------------------------------------------------
    # OPENING RANGE
    # --------------------------------------------------

    orb = calculate_opening_range(
        target_session,
        opening_minutes=5,
    )

    print()
    print("OPENING RANGE")
    print("-" * 40)

    for key, value in orb.items():
        print(f"{key}: {value}")

    # --------------------------------------------------
    # FIRST ORB BREAKOUT
    # --------------------------------------------------

    breakout = find_first_orb_breakout(
        target_session,
        or_high=orb["or_high"],
        or_low=orb["or_low"],
    )

    print()
    print("FIRST ORB BREAKOUT")
    print("-" * 40)

    if breakout is None:
        print("No breakout found.")
    else:
        for key, value in breakout.items():
            print(f"{key}: {value}")

        trade_setup = None

    if breakout is not None:

        target_date_levels = daily_levels.loc[
            daily_levels.index
            == target_session.iloc[0]["timestamp_ny"].date()
        ]

        row = target_date_levels.iloc[0]

        trade_setup = calculate_trade_setup(
            direction=breakout["direction"],
            entry=breakout["entry_price"],
            or_high=orb["or_high"],
            or_low=orb["or_low"],
            pdh=row["pdh"],
            pdl=row["pdl"],
            minimum_rr=2.0,
        )

    print()
    print("TRADE SETUP")
    print("-" * 40)

    if trade_setup is None:
        print("No valid trade setup.")

    else:
        for key, value in trade_setup.items():
            print(f"{key}: {value}")

    # --------------------------------------------------
    # PDH / PDL FOR TARGET DATE
    # --------------------------------------------------

    target_levels = daily_levels.loc[
        daily_levels.index == target_session.iloc[0]["timestamp_ny"].date()
    ]

    print()
    print("TARGET DAY PDH / PDL")
    print("-" * 40)

    print(
        target_levels.to_string()
    )


if __name__ == "__main__":
    main()