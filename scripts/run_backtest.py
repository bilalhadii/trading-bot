import pandas as pd
from sqlalchemy import text
from backtest.storage import save_trades
from database.connection import engine
from strategy.daily_levels import calculate_daily_levels
from strategy.orb import calculate_opening_range
from strategy.session import add_new_york_time, regular_session
from strategy.signals import (
    find_first_orb_breakout,
    find_first_orb_retest,
    find_first_orb_retest_reclaim,
    find_first_orb_retest_reclaim_body,
    find_first_orb_retest_reclaim_body_rejection_reason,
)
from backtest.engine import simulate_trade
from backtest.excursion import calculate_excursion
from backtest.metrics import summarize_trades


TICKER = "AAPL"
START_DATE = "2024-01-02"
END_DATE = "2024-12-31"

STRATEGY_VERSION = "ORB_RETEST_RECLAIM_BODY_2R"
RETEST_MAX_BARS = 5
RETEST_TOLERANCE_OR_FRACTION = 0.10

EXIT_MODE = "FIXED_R"
TARGET_R = 2.0
EARLY_BREAKOUT_ONLY = False

def load_data(
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

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
    )

    return df


def main():

    is_reclaim = STRATEGY_VERSION == "ORB_RETEST_RECLAIM_2R"
    is_reclaim_body = STRATEGY_VERSION == "ORB_RETEST_RECLAIM_BODY_2R"
    is_retest = STRATEGY_VERSION == "ORB_RETEST_2R" or is_reclaim or is_reclaim_body
    if is_retest and (EXIT_MODE != "FIXED_R" or EARLY_BREAKOUT_ONLY):
        raise ValueError(f"{STRATEGY_VERSION} requires FIXED_R and no early-breakout filter.")

    print("=" * 60)
    print(f"{STRATEGY_VERSION} BACKTEST")
    print("=" * 60)
    print(f"Ticker: {TICKER}; dates: {START_DATE} through {END_DATE}")
    print(f"Exit mode: {EXIT_MODE}; target R: {TARGET_R}")
    if is_retest:
        print(f"Retest/confirmation window: {RETEST_MAX_BARS} bars after breakout")
        print(f"Tolerance / OR range: {RETEST_TOLERANCE_OR_FRACTION}")
        if is_reclaim_body:
            print("First band overlap must reclaim the OR boundary with a body aligned to the breakout.")
            print("Failed reclaim/body alignment ends setup; no later confirmation.")
        elif is_reclaim:
            print("First band overlap must close strictly beyond the broken OR boundary.")
            print("Retest is confirmation; failed reclaim ends setup; no later confirmation.")
        else:
            print("First band overlap fixes retest; later close beyond its high/low confirms.")
        print("Invalidation checked first; entry at next open; stop at opposite OR boundary.")

    df = load_data(
        TICKER,
        START_DATE,
        END_DATE,
    )

    df = add_new_york_time(df)
    regular = regular_session(df)

    daily_levels = calculate_daily_levels(
        regular
    )

    trading_dates = sorted(
        regular["timestamp_ny"]
        .dt.date
        .unique()
    )

    total_days = 0
    breakouts = 0
    valid_setups = 0
    reclaim_body_disagreement_rejects = 0
    trades = []

    for trading_date in trading_dates:

        total_days += 1

        day_df = regular[
            regular["timestamp_ny"].dt.date
            == trading_date
        ].copy()

        EXPECTED_REGULAR_BARS = 390

        if len(day_df) != EXPECTED_REGULAR_BARS:
            continue
        # Need previous day levels.
        levels = daily_levels.loc[
            daily_levels.index == trading_date
        ]

        if levels.empty:
            continue

        row = levels.iloc[0]

        pdh = row["pdh"]
        pdl = row["pdl"]

        if pd.isna(pdh) or pd.isna(pdl):
            continue

        # Opening range
        orb = calculate_opening_range(
            day_df,
            opening_minutes=5,
        )

        # First breakout
        breakout = find_first_orb_breakout(
            day_df,
            or_high=orb["or_high"],
            or_low=orb["or_low"],
        )

        if breakout is None:
            continue
        breakouts += 1

        if EARLY_BREAKOUT_ONLY:

            breakout_time = breakout["breakout_timestamp"]

            breakout_clock = breakout_time.time()

            if not (
                pd.Timestamp("09:35").time()
                <= breakout_clock
                < pd.Timestamp("09:45").time()
            ):
                continue

        if is_retest:
            if is_reclaim_body:
                find_signal = find_first_orb_retest_reclaim_body
            elif is_reclaim:
                find_signal = find_first_orb_retest_reclaim
            else:
                find_signal = find_first_orb_retest
            breakout = find_signal(
                day_df,
                or_high=orb["or_high"],
                or_low=orb["or_low"],
                max_bars=RETEST_MAX_BARS,
                tolerance_or_fraction=RETEST_TOLERANCE_OR_FRACTION,
            )
            if breakout is None:
                if is_reclaim_body:
                    reason = find_first_orb_retest_reclaim_body_rejection_reason(
                        day_df,
                        or_high=orb["or_high"],
                        or_low=orb["or_low"],
                        max_bars=RETEST_MAX_BARS,
                        tolerance_or_fraction=RETEST_TOLERANCE_OR_FRACTION,
                    )
                    if reason == "BODY_DISAGREEMENT":
                        reclaim_body_disagreement_rejects += 1
                continue

        signal_time = breakout.get("confirmation_timestamp", breakout["breakout_timestamp"])

        # TRADE SETUP: same opposite-OR stop and fixed-R framework.
        # --------------------------------------------------

        if breakout["direction"] == "LONG":

            entry_price = float(
                breakout["entry_price"]
            )

            stop_price = float(
                orb["or_low"]
            )

        else:

            entry_price = float(
                breakout["entry_price"]
            )

            stop_price = float(
                orb["or_high"]
            )

        risk = abs(
            entry_price - stop_price
        )
        if is_retest:
            risk = (
                entry_price - stop_price
                if breakout["direction"] == "LONG"
                else stop_price - entry_price
            )

        if risk <= 0:
            continue

        valid_setups += 1

        # --------------------------------------------------
        # TARGET
        # --------------------------------------------------

        if EXIT_MODE == "FIXED_R":

            if TARGET_R is None:
                raise ValueError(
                    "TARGET_R must be set when "
                    "EXIT_MODE='FIXED_R'"
                )

            if breakout["direction"] == "LONG":
                target_price = (
                    entry_price
                    + risk * TARGET_R
                )
            else:
                target_price = (
                    entry_price
                    - risk * TARGET_R
                )

        elif EXIT_MODE == "PDH_PDL":

            if breakout["direction"] == "LONG":

                target_price = float(pdh)

                if target_price <= entry_price:
                    continue

            else:

                target_price = float(pdl)

                if target_price >= entry_price:
                    continue

        else:

            raise ValueError(
                f"Unsupported EXIT_MODE: {EXIT_MODE}"
            )



        

        # --------------------------------------------------
        # SIMULATE TRADE
        # --------------------------------------------------

        result = simulate_trade(
            session_df=day_df,
            entry_time=breakout[
                "entry_timestamp"
            ],
            direction=breakout[
                "direction"
            ],
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            break_even_r=None,
        )

        if result is None:
            continue

        # --------------------------------------------------
        # MAE / MFE
        # --------------------------------------------------

        excursion = calculate_excursion(
            session_df=day_df,
            entry_time=breakout[
                "entry_timestamp"
            ],
            exit_time=result[
                "exit_time"
            ],
            entry_price=entry_price,
            direction=breakout[
                "direction"
            ],
            stop_price=stop_price,
            target_price=target_price,
        )

        # --------------------------------------------------
        # P&L
        # --------------------------------------------------

        pnl = (
            result["r_multiple"]
            * risk
        )

        # --------------------------------------------------
        # TRADE RECORD
        # --------------------------------------------------

        trade = {
            "strategy_version":
                STRATEGY_VERSION,

            "ticker":
                TICKER,

            "trade_date":
                trading_date,

            "direction":
                breakout["direction"],

            "signal_time":
                signal_time,

            "entry_time":
                breakout["entry_timestamp"],

            "exit_time":
                result["exit_time"],

            "entry_price":
                entry_price,

            "stop_price":
                stop_price,

            "target_price":
                target_price,

            "exit_price":
                result["exit_price"],

            "risk_amount":
                risk,

            "pnl":
                pnl,

            "r_multiple":
                result["r_multiple"],

            "outcome":
                result["outcome"],

            "mae_price":
                excursion["mae_price"],

            "mfe_price":
                excursion["mfe_price"],

            "mae_r":
                excursion["mae_r"],

            "mfe_r":
                excursion["mfe_r"],
        }


        
        result = simulate_trade(
            session_df=day_df,
            entry_time=breakout["entry_timestamp"],
            direction=breakout["direction"],
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            break_even_r=None,
        )

        excursion = calculate_excursion(
            session_df=day_df,
            entry_time=breakout["entry_timestamp"],
            exit_time=result["exit_time"],
            entry_price=entry_price,
            direction=breakout["direction"],
            stop_price=stop_price,
            target_price=target_price,
        )

        if result is None:
            continue

        pnl = (
            result["r_multiple"]
            * risk
        )

        trade = {
            "strategy_version": STRATEGY_VERSION,
            "ticker": TICKER,
            "trade_date": trading_date,
            "direction": breakout["direction"],
            "signal_time": signal_time,
            "entry_time": breakout["entry_timestamp"],
            "exit_time": result["exit_time"],
            "entry_price": entry_price,
            "stop_price": stop_price,
            "target_price": target_price,
            "exit_price": result["exit_price"],
            "risk_amount": risk,
            "pnl": pnl,
            "r_multiple": result["r_multiple"],
            "outcome": result["outcome"],
            "mae_price": excursion["mae_price"],
            "mfe_price": excursion["mfe_price"],
            "mae_r": excursion["mae_r"],
            "mfe_r": excursion["mfe_r"],
        }

        trades.append(trade)
    save_trades(trades)




    print()
    print("BACKTEST SUMMARY")
    print("-" * 40)

    print(f"Trading days:  {total_days}")
    print(f"Breakouts:     {breakouts}")
    print(f"Valid setups:  {valid_setups}")
    print(f"Executed:      {len(trades)}")
    if is_reclaim_body:
        print(f"Body disagreement rejects: {reclaim_body_disagreement_rejects}")

    if trades:

        results_df = pd.DataFrame(trades)

        metrics = summarize_trades(
            results_df
        )

        print()
        print(f"Trades:         {metrics['trades']}")
        print(f"Wins:           {metrics['wins']}")
        print(f"Losses:         {metrics['losses']}")
        print(f"Target hits:    {(results_df['outcome'] == 'WIN').sum()}")
        print(f"Stop hits:      {(results_df['outcome'] == 'LOSS').sum()}")
        print(f"Positive trades: {metrics['wins']}")
        print(
            f"Session closes: {metrics['session_closes']}"
        )
        print(
            f"Win rate:       {metrics['win_rate']:.2%}"
        )
        print(
            f"Total R:        {metrics['total_r']:.4f}"
        )
        print(
            f"Average R:      {metrics['average_r']:.4f}"
        )
        print(
            f"Profit factor:  {metrics['profit_factor']:.4f}"
        )
        print(
            f"Max drawdown:   {metrics['max_drawdown']:.4f}R"
        )   

        print()
        print("TRADE DETAILS")
        print("-" * 40)

        print(
            results_df[
                [
                    "trade_date",
                    "direction",
                    "entry_price",
                    "stop_price",
                    "target_price",
                    "exit_price",
                    "r_multiple",
                    "mae_r",
                    "mfe_r",
                    "outcome",
                ]
            ].to_string(index=False)
        )

if __name__ == "__main__":
    main()
