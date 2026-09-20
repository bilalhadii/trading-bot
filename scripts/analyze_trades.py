import pandas as pd
from sqlalchemy import text

from database.connection import engine


def load_trades() -> pd.DataFrame:
    query = text("""
        SELECT
            trade_date,
            direction,
            signal_time,
            entry_time,
            exit_time,
            entry_price,
            stop_price,
            target_price,
            exit_price,
            r_multiple,
            outcome
        FROM backtest_trades
        WHERE strategy_version = 'ORB_V0'
          AND ticker = 'AAPL'
        ORDER BY trade_date;
    """)

    with engine.connect() as conn:
        return pd.read_sql(query, conn)


def main():

    trades = load_trades()

    if trades.empty:
        print("No trades found.")
        return

    print("=" * 70)
    print("AAPL ORB V0 TRADE ANALYSIS")
    print("=" * 70)

    print()
    print(trades.to_string(index=False))

    print()
    print("SUMMARY")
    print("-" * 40)

    print(
        f"Total trades: {len(trades)}"
    )

    print(
        f"Total R: {trades['r_multiple'].sum():.4f}"
    )

    print(
        f"Average R: {trades['r_multiple'].mean():.4f}"
    )

    wins = (trades["r_multiple"] > 0).sum()
    losses = (trades["r_multiple"] < 0).sum()

    print(f"Positive trades: {wins}")
    print(f"Negative trades: {losses}")

    print()
    print("OUTCOMES")
    print("-" * 40)

    print(
        trades["outcome"]
        .value_counts()
        .to_string()
    )


if __name__ == "__main__":
    main()