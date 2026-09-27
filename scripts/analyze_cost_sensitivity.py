from __future__ import annotations

import pandas as pd

from scripts.analyze_walk_forward_retest import (
    END_DATE,
    START_DATE,
    STRATEGIES,
    run_strategy_trades,
    summarize_group,
)
from scripts.compare_multisymbol_retest import SYMBOLS, prepare_sessions
from scripts.run_backtest import load_data
from strategy.session import add_new_york_time


COSTS_R = (0.0, 0.01, 0.02, 0.05, 0.10)


def main() -> None:
    all_trades = []
    for ticker in SYMBOLS:
        print(f"Loading {ticker} {START_DATE} through {END_DATE}...", flush=True)
        df = add_new_york_time(load_data(ticker, START_DATE, END_DATE))
        sessions = prepare_sessions(df) if not df.empty else []
        for strategy in STRATEGIES:
            print(f"  Running {strategy}...", flush=True)
            all_trades.append(run_strategy_trades(ticker, sessions, strategy))

    trades = pd.concat(all_trades, ignore_index=True)
    rows = []
    for cost_r in COSTS_R:
        net = trades.copy()
        net["r_multiple"] = net["r_multiple"] - cost_r
        by_year = (
            net
            .sort_values(["trade_date", "ticker"])
            .groupby(["year", "strategy"], as_index=False)
            .apply(summarize_group, include_groups=False)
        )
        by_year["cost_r"] = cost_r
        rows.append(by_year)

    yearly = pd.concat(rows, ignore_index=True)
    print()
    print("YEARLY COST SENSITIVITY")
    print("-" * 100)
    print(yearly[[
        "cost_r",
        "year",
        "strategy",
        "trades",
        "total_r",
        "average_r",
        "profit_factor",
        "max_drawdown",
    ]].to_string(index=False))

    totals = []
    for cost_r in COSTS_R:
        net = trades.copy()
        net["r_multiple"] = net["r_multiple"] - cost_r
        summary = (
            net
            .sort_values(["trade_date", "ticker"])
            .groupby("strategy")
            .apply(summarize_group, include_groups=False)
            .reset_index()
        )
        summary["cost_r"] = cost_r
        totals.append(summary)

    totals_df = pd.concat(totals, ignore_index=True)
    print()
    print("FULL PERIOD COST SENSITIVITY")
    print("-" * 100)
    print(totals_df[[
        "cost_r",
        "strategy",
        "trades",
        "total_r",
        "average_r",
        "profit_factor",
        "max_drawdown",
    ]].to_string(index=False))

    pivot = totals_df.pivot(
        index="cost_r",
        columns="strategy",
        values=["total_r", "average_r", "profit_factor", "max_drawdown"],
    )
    print()
    print("FULL PERIOD COMPARISON")
    print("-" * 100)
    print(pivot.to_string())


if __name__ == "__main__":
    main()
