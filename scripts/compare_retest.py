import pandas as pd
from sqlalchemy import text

from database.connection import engine


BASELINE_VERSION = "ORB_BASELINE_2R"
RETEST_VERSION = "ORB_RETEST_2R"
VARIANT_VERSIONS = [
    "ORB_RETEST_2R",
    "ORB_RETEST_RECLAIM_2R",
    "ORB_RETEST_RECLAIM_BODY_2R",
]
TICKER = "AAPL"
START_DATE = "2024-01-02"
END_DATE = "2024-12-31"


def load_trades(strategy_version: str) -> pd.DataFrame:
    query = text("""
        SELECT
            trade_date,
            direction,
            signal_time,
            entry_time,
            entry_price,
            stop_price,
            target_price,
            exit_price,
            risk_amount,
            r_multiple,
            outcome
        FROM backtest_trades
        WHERE strategy_version = :strategy_version
          AND ticker = :ticker
          AND trade_date BETWEEN :start_date AND :end_date
        ORDER BY trade_date, entry_time;
    """)

    with engine.connect() as conn:
        return pd.read_sql(
            query,
            conn,
            params={
                "strategy_version": strategy_version,
                "ticker": TICKER,
                "start_date": START_DATE,
                "end_date": END_DATE,
            },
        )


def summarize(name: str, trades: pd.DataFrame) -> None:
    print()
    print(name)
    print("-" * 40)
    if trades.empty:
        print("No trades.")
        return

    positive_r = trades.loc[trades["r_multiple"] > 0, "r_multiple"].sum()
    negative_r = abs(trades.loc[trades["r_multiple"] < 0, "r_multiple"].sum())
    profit_factor = positive_r / negative_r if negative_r else float("inf")
    print(f"Trades:        {len(trades)}")
    print(f"Total R:       {trades['r_multiple'].sum():.4f}")
    print(f"Average R:     {trades['r_multiple'].mean():.4f}")
    print(f"Positive:      {(trades['r_multiple'] > 0).sum()}")
    print(f"Negative:      {(trades['r_multiple'] < 0).sum()}")
    print(f"Target hits:   {(trades['outcome'] == 'WIN').sum()}")
    print(f"Stop hits:     {(trades['outcome'] == 'LOSS').sum()}")
    print(f"Session close: {(trades['outcome'] == 'SESSION_CLOSE').sum()}")
    print(f"Profit factor: {profit_factor:.4f}")


def main() -> None:
    baseline = load_trades(BASELINE_VERSION)
    variants = {
        version: load_trades(version)
        for version in VARIANT_VERSIONS
    }

    summarize(BASELINE_VERSION, baseline)
    for version, trades in variants.items():
        summarize(version, trades)

    print()
    print("VARIANT COMPARISON")
    print("-" * 40)
    rows = []
    for version, trades in variants.items():
        comparison = baseline.merge(
            trades,
            on="trade_date",
            how="outer",
            suffixes=("_baseline", "_variant"),
            indicator=True,
        ).sort_values("trade_date")

        overlap = comparison[comparison["_merge"] == "both"].copy()
        baseline_only = comparison[comparison["_merge"] == "left_only"].copy()
        if overlap.empty:
            r_delta_sum = 0.0
            r_delta_avg = 0.0
            same_direction = 0
        else:
            overlap["r_delta"] = (
                overlap["r_multiple_variant"]
                - overlap["r_multiple_baseline"]
            )
            r_delta_sum = overlap["r_delta"].sum()
            r_delta_avg = overlap["r_delta"].mean()
            same_direction = (
                overlap["direction_baseline"]
                == overlap["direction_variant"]
            ).sum()

        rows.append({
            "strategy": version,
            "trades": len(trades),
            "total_r": trades["r_multiple"].sum() if not trades.empty else 0.0,
            "avg_r": trades["r_multiple"].mean() if not trades.empty else 0.0,
            "overlap": len(overlap),
            "baseline_only": len(baseline_only),
            "same_direction": same_direction,
            "overlap_delta_r": r_delta_sum,
            "overlap_avg_delta_r": r_delta_avg,
        })

    print(pd.DataFrame(rows).to_string(index=False))

    retest = variants[RETEST_VERSION]
    comparison = baseline.merge(
        retest,
        on="trade_date",
        how="outer",
        suffixes=("_baseline", "_retest"),
        indicator=True,
    ).sort_values("trade_date")

    overlap = comparison[comparison["_merge"] == "both"].copy()
    baseline_only = comparison[comparison["_merge"] == "left_only"].copy()
    retest_only = comparison[comparison["_merge"] == "right_only"].copy()

    print()
    print("OVERLAP")
    print("-" * 40)
    print(f"Both traded:       {len(overlap)}")
    print(f"Baseline only:     {len(baseline_only)}")
    print(f"Retest only:       {len(retest_only)}")
    if not overlap.empty:
        same_direction = (
            overlap["direction_baseline"]
            == overlap["direction_retest"]
        ).sum()
        overlap["r_delta"] = (
            overlap["r_multiple_retest"]
            - overlap["r_multiple_baseline"]
        )
        print(f"Same direction:    {same_direction}")
        print(f"Direction changed: {len(overlap) - same_direction}")
        print(f"Retest R delta:    {overlap['r_delta'].sum():.4f}")
        print(f"Average R delta:   {overlap['r_delta'].mean():.4f}")

    if not baseline_only.empty:
        summarize("BASELINE TRADES FILTERED OUT BY RETEST", pd.DataFrame({
            "r_multiple": baseline_only["r_multiple_baseline"],
            "outcome": baseline_only["outcome_baseline"],
        }))

    print()
    print("MONTHLY R")
    print("-" * 40)
    monthly = pd.DataFrame({
        "baseline_r": baseline.groupby(
            pd.to_datetime(baseline["trade_date"]).dt.to_period("M")
        )["r_multiple"].sum(),
        "retest_r": retest.groupby(
            pd.to_datetime(retest["trade_date"]).dt.to_period("M")
        )["r_multiple"].sum(),
    }).fillna(0)
    monthly["delta"] = monthly["retest_r"] - monthly["baseline_r"]
    print(monthly.to_string())

    print()
    print("WORST RETEST DELTAS ON OVERLAP")
    print("-" * 40)
    if overlap.empty:
        print("No overlap.")
    else:
        cols = [
            "trade_date",
            "direction_baseline",
            "r_multiple_baseline",
            "direction_retest",
            "r_multiple_retest",
            "r_delta",
        ]
        print(overlap.nsmallest(15, "r_delta")[cols].to_string(index=False))


if __name__ == "__main__":
    main()
