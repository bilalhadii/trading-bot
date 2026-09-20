import pandas as pd
from sqlalchemy import text

from database.connection import engine


def insert_candles(df: pd.DataFrame) -> int:
    """
    Insert market candles into PostgreSQL.

    Duplicate (ticker, timestamp) rows are ignored.
    """

    if df.empty:
        return 0

    required_columns = [
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

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    records = df[required_columns].to_dict(
        orient="records"
    )

    sql = text(
        """
        INSERT INTO market_candles (
            ticker,
            timestamp,
            open,
            high,
            low,
            close,
            volume,
            trade_count,
            vwap
        )
        VALUES (
            :ticker,
            :timestamp,
            :open,
            :high,
            :low,
            :close,
            :volume,
            :trade_count,
            :vwap
        )
        ON CONFLICT (ticker, timestamp)
        DO NOTHING
        """
    )

    with engine.begin() as conn:
        conn.execute(sql, records)

    return len(records)