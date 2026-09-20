from datetime import datetime, timedelta, timezone

import pandas as pd

from data.alpaca_client import get_minute_bars
from data.db_writer import insert_candles
from data.validator import validate_candles


def download_range(
    ticker: str,
    start: datetime,
    end: datetime,
    chunk_days: int = 7,
) -> None:
    """
    Download historical 1-minute bars in manageable chunks.

    chunk_days controls the size of each API request.
    """

    current_start = start

    total_retrieved = 0
    total_processed = 0

    while current_start < end:

        current_end = min(
            current_start + timedelta(days=chunk_days),
            end,
        )

        print()
        print("=" * 60)
        print(f"{ticker}")
        print(f"{current_start} → {current_end}")
        print("=" * 60)

        bars = get_minute_bars(
            ticker=ticker,
            start=current_start,
            end=current_end,
        )

        df = bars.df.reset_index()

        if df.empty:
            print("No rows returned.")
        else:

            total_retrieved += len(df)

            df = df.rename(
                columns={
                    "symbol": "ticker",
                }
            )

            df["timestamp"] = (
                pd.to_datetime(
                    df["timestamp"],
                    utc=True,
                )
            )

            columns = [
                "ticker",
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "trade_count",
                "vwap",
            ]

            df = df[columns]

            validate_candles(df)

            processed = insert_candles(df)

            total_processed += processed

            print(
                f"Retrieved: {len(df)}"
            )

            print(
                f"Processed: {processed}"
            )

        current_start = current_end

    print()
    print("=" * 60)
    print("DOWNLOAD COMPLETE")
    print("=" * 60)

    print(
        f"Total retrieved: {total_retrieved}"
    )

    print(
        f"Total processed: {total_processed}"
    )