from datetime import datetime, timezone

from data.alpaca_client import get_minute_bars
from data.db_writer import insert_candles
from data.validator import validate_candles


def download(
    ticker: str,
    start: datetime,
    end: datetime,
) -> None:

    print("=" * 60)
    print(f"Downloading {ticker}")
    print(f"Start: {start}")
    print(f"End:   {end}")
    print("=" * 60)

    bars = get_minute_bars(
        ticker=ticker,
        start=start,
        end=end,
    )

    df = bars.df.reset_index()

    if df.empty:
        print("No data returned.")
        return

    print(
        f"Rows retrieved from Alpaca: {len(df)}"
    )

    df = df.rename(
        columns={
            "symbol": "ticker",
        }
    )

    df["timestamp"] = (
        df["timestamp"].dt.tz_convert("UTC")
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

    print("Validation: PASSED")

    inserted = insert_candles(df)

    print(
        f"Rows processed: {inserted}"
    )


if __name__ == "__main__":
    download(
        ticker="AAPL",
        start=datetime(
            2024,
            1,
            2,
            tzinfo=timezone.utc,
        ),
        end=datetime(
            2024,
            2,
            1,
            tzinfo=timezone.utc,
        ),
    )