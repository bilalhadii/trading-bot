import pandas as pd
from sqlalchemy import text

from database.connection import engine


def main():

    query = text("""
        SELECT
            trade_date,
            direction,
            entry_price,
            stop_price,
            target_price,
            r_multiple,
            outcome
        FROM backtest_trades
        WHERE strategy_version = 'ORB_BASELINE_PDH'
          AND ticker = 'AAPL'
        ORDER BY trade_date;
    """)

    with engine.connect() as conn:
        trades = pd.read_sql(query, conn)

    print()
    print("ORB_BASELINE_PDH TRADES")
    print("-" * 70)

    print(trades.to_string(index=False))

    print()
    print(f"Total PDH/PDL trades: {len(trades)}")


if __name__ == "__main__":
    main()