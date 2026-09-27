from __future__ import annotations

import pandas as pd

from scripts.compare_multisymbol_retest import (
    PERIODS,
    SYMBOLS,
    prepare_sessions,
)
from scripts.run_backtest import load_data
from strategy.session import add_new_york_time


STRATEGIES = (
    "ORB_BASELINE_2R",
    "ORB_RETEST_RECLAIM_BODY_2R",
)


def equity_stats(r_values: pd.Series) -> dict:
    if r_values.empty:
        return {
            "total_r": 0.0,
            "max_drawdown": 0.0,
            "worst_month": 0.0,
            "best_month": 0.0,
            "positive_months": 0,
            "negative_months": 0,
            "months": 0,
        }

    cumulative = r_values.cumsum()
    drawdown = cumulative - cumulative.cummax()
    return {
        "total_r": float(r_values.sum()),
        "max_drawdown": float(drawdown.min()),
        "worst_month": float(r_values.min()),
        "best_month": float(r_values.max()),
        "positive_months": int((r_values > 0).sum()),
        "negative_months": int((r_values < 0).sum()),
        "months": int(len(r_values)),
    }


def load_strategy_monthly(
    ticker: str,
    period: str,
    sessions,
    strategy: str,
) -> pd.DataFrame:
    from backtest.engine import simulate_trade
    from scripts.run_backtest import is_strategy_session_eligible
    from strategy.orb import calculate_opening_range
    from strategy.signals import (
        find_first_orb_breakout,
        find_first_orb_retest_reclaim_body,
    )

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
                max_bars=5,
                tolerance_or_fraction=0.10,
            )
            if signal is None:
                continue

        entry_price = float(signal["entry_price"])
        if signal["direction"] == "LONG":
            stop_price = float(orb["or_low"])
            risk = entry_price - stop_price
            target_price = entry_price + risk * 2.0
        else:
            stop_price = float(orb["or_high"])
            risk = stop_price - entry_price
            target_price = entry_price - risk * 2.0

        if risk <= 0:
            continue

        trade = simulate_trade(
            session_df=day_df,
            entry_time=signal["entry_timestamp"],
            direction=signal["direction"],
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            break_even_r=None,
        )
        rows.append({
            "period": period,
            "ticker": ticker,
            "strategy": strategy,
            "trade_date": trading_date,
            "month": pd.Period(trading_date, freq="M"),
            "r_multiple": trade["r_multiple"],
        })

    if not rows:
        return pd.DataFrame(columns=[
            "period",
            "ticker",
            "strategy",
            "trade_date",
            "month",
            "r_multiple",
        ])

    return pd.DataFrame(rows)


def main() -> None:
    all_trades = []
    for period, (start_date, end_date) in PERIODS.items():
        for ticker in SYMBOLS:
            print(f"Loading {ticker} {period}...", flush=True)
            df = add_new_york_time(load_data(ticker, start_date, end_date))
            sessions = prepare_sessions(df) if not df.empty else []
            for strategy in STRATEGIES:
                print(f"  Analyzing {strategy}...", flush=True)
                all_trades.append(
                    load_strategy_monthly(ticker, period, sessions, strategy)
                )

    trades = pd.concat(all_trades, ignore_index=True)
    monthly = (
        trades
        .groupby(["period", "ticker", "strategy", "month"], as_index=False)
        ["r_multiple"]
        .sum()
    )

    rows = []
    for (period, ticker, strategy), group in monthly.groupby(
        ["period", "ticker", "strategy"]
    ):
        stats = equity_stats(group.sort_values("month")["r_multiple"])
        stats.update({
            "period": period,
            "ticker": ticker,
            "strategy": strategy,
        })
        rows.append(stats)

    symbol_stats = pd.DataFrame(rows)
    print()
    print("SYMBOL MONTHLY STABILITY")
    print("-" * 100)
    print(symbol_stats[[
        "period",
        "ticker",
        "strategy",
        "total_r",
        "max_drawdown",
        "worst_month",
        "best_month",
        "positive_months",
        "negative_months",
        "months",
    ]].to_string(index=False))

    basket_monthly = (
        monthly
        .groupby(["period", "strategy", "month"], as_index=False)
        ["r_multiple"]
        .sum()
    )
    rows = []
    for (period, strategy), group in basket_monthly.groupby(["period", "strategy"]):
        stats = equity_stats(group.sort_values("month")["r_multiple"])
        stats.update({
            "period": period,
            "strategy": strategy,
            "positive_symbols": int(
                (
                    symbol_stats[
                        (symbol_stats["period"] == period)
                        & (symbol_stats["strategy"] == strategy)
                    ]["total_r"] > 0
                ).sum()
            ),
        })
        rows.append(stats)

    basket_stats = pd.DataFrame(rows)
    print()
    print("BASKET MONTHLY STABILITY")
    print("-" * 100)
    print(basket_stats[[
        "period",
        "strategy",
        "total_r",
        "max_drawdown",
        "worst_month",
        "best_month",
        "positive_months",
        "negative_months",
        "months",
        "positive_symbols",
    ]].to_string(index=False))

    comparison = basket_stats.pivot(
        index="period",
        columns="strategy",
        values=[
            "total_r",
            "max_drawdown",
            "worst_month",
            "positive_months",
            "negative_months",
            "positive_symbols",
        ],
    )
    print()
    print("BASKET COMPARISON")
    print("-" * 100)
    print(comparison.to_string())


if __name__ == "__main__":
    main()
