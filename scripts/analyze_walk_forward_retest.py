from __future__ import annotations

import pandas as pd

from backtest.engine import simulate_trade
from backtest.metrics import summarize_trades
from scripts.compare_multisymbol_retest import (
    SYMBOLS,
    prepare_sessions,
)
from scripts.run_backtest import (
    is_strategy_session_eligible,
    load_data,
)
from strategy.orb import calculate_opening_range
from strategy.session import add_new_york_time
from strategy.signals import (
    find_first_orb_breakout,
    find_first_orb_retest_reclaim_body,
)


START_DATE = "2018-01-01"
END_DATE = "2026-12-31"
STRATEGIES = (
    "ORB_BASELINE_2R",
    "ORB_RETEST_RECLAIM_BODY_2R",
)
TARGET_R = 2.0
RETEST_MAX_BARS = 5
RETEST_TOLERANCE_OR_FRACTION = 0.10


def run_strategy_trades(
    ticker: str,
    sessions: list[tuple[object, pd.DataFrame, object]],
    strategy: str,
) -> pd.DataFrame:
    rows = []

    for trading_date, day_df, report in sessions:
        if not is_strategy_session_eligible(report):
            continue

        orb = calculate_opening_range(day_df, opening_minutes=5)
        signal = find_first_orb_breakout(
            day_df,
            or_high=orb["or_high"],
            or_low=orb["or_low"],
        )
        if signal is None:
            continue

        if strategy == "ORB_RETEST_RECLAIM_BODY_2R":
            signal = find_first_orb_retest_reclaim_body(
                day_df,
                or_high=orb["or_high"],
                or_low=orb["or_low"],
                max_bars=RETEST_MAX_BARS,
                tolerance_or_fraction=RETEST_TOLERANCE_OR_FRACTION,
            )
            if signal is None:
                continue
        elif strategy != "ORB_BASELINE_2R":
            raise ValueError(f"Unsupported strategy: {strategy}")

        entry_price = float(signal["entry_price"])
        if signal["direction"] == "LONG":
            stop_price = float(orb["or_low"])
            risk = entry_price - stop_price
            target_price = entry_price + risk * TARGET_R
        else:
            stop_price = float(orb["or_high"])
            risk = stop_price - entry_price
            target_price = entry_price - risk * TARGET_R

        if risk <= 0:
            continue

        result = simulate_trade(
            session_df=day_df,
            entry_time=signal["entry_timestamp"],
            direction=signal["direction"],
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            break_even_r=None,
        )
        rows.append({
            "ticker": ticker,
            "strategy": strategy,
            "trade_date": trading_date,
            "year": pd.Timestamp(trading_date).year,
            "direction": signal["direction"],
            "r_multiple": result["r_multiple"],
            "outcome": result["outcome"],
        })

    if not rows:
        return pd.DataFrame(columns=[
            "ticker",
            "strategy",
            "trade_date",
            "year",
            "direction",
            "r_multiple",
            "outcome",
        ])
    return pd.DataFrame(rows)


def max_drawdown(r_values: pd.Series) -> float:
    if r_values.empty:
        return 0.0
    equity = r_values.cumsum()
    return float((equity - equity.cummax()).min())


def summarize_group(group: pd.DataFrame) -> pd.Series:
    metrics = summarize_trades(group)
    return pd.Series({
        "trades": metrics["trades"],
        "total_r": metrics["total_r"],
        "average_r": metrics["average_r"],
        "profit_factor": metrics["profit_factor"],
        "max_drawdown": metrics["max_drawdown"],
        "positive_trades": metrics["wins"],
        "negative_trades": metrics["losses"],
        "target_hits": int((group["outcome"] == "WIN").sum()),
        "stop_hits": int((group["outcome"] == "LOSS").sum()),
        "session_closes": int((group["outcome"] == "SESSION_CLOSE").sum()),
        "long_r": group.loc[group["direction"] == "LONG", "r_multiple"].sum(),
        "short_r": group.loc[group["direction"] == "SHORT", "r_multiple"].sum(),
        "long_trades": int((group["direction"] == "LONG").sum()),
        "short_trades": int((group["direction"] == "SHORT").sum()),
    })


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

    by_symbol_year = (
        trades
        .groupby(["year", "ticker", "strategy"], as_index=False)
        .apply(summarize_group, include_groups=False)
    )

    print()
    print("WALK-FORWARD BY SYMBOL/YEAR")
    print("-" * 120)
    print(by_symbol_year.to_string(index=False))

    basket_year = (
        trades
        .sort_values(["trade_date", "ticker"])
        .groupby(["year", "strategy"], as_index=False)
        .apply(summarize_group, include_groups=False)
    )

    positive_symbols = (
        by_symbol_year
        .assign(is_positive=lambda df: df["total_r"] > 0)
        .groupby(["year", "strategy"])["is_positive"]
        .sum()
        .rename("positive_symbols")
        .reset_index()
    )
    basket_year = basket_year.merge(
        positive_symbols,
        on=["year", "strategy"],
        how="left",
    )

    print()
    print("WALK-FORWARD BASKET BY YEAR")
    print("-" * 120)
    print(basket_year.to_string(index=False))

    pivot = basket_year.pivot(
        index="year",
        columns="strategy",
        values=[
            "trades",
            "total_r",
            "average_r",
            "profit_factor",
            "max_drawdown",
            "positive_symbols",
            "long_r",
            "short_r",
        ],
    )
    print()
    print("BASKET STRATEGY COMPARISON")
    print("-" * 120)
    print(pivot.to_string())

    totals = (
        trades
        .sort_values(["trade_date", "ticker"])
        .groupby("strategy")
        .apply(summarize_group, include_groups=False)
        .reset_index()
    )
    print()
    print("FULL PERIOD TOTALS")
    print("-" * 120)
    print(totals.to_string(index=False))


if __name__ == "__main__":
    main()
