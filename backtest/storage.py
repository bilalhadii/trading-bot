import pandas as pd
from sqlalchemy import text

from database.connection import engine


def save_trades(trades: list[dict]) -> None:

    if not trades:
        return

    sql = text("""
    INSERT INTO backtest_trades (
        strategy_version,
        ticker,
        trade_date,
        direction,
        signal_time,
        entry_time,
        exit_time,
        entry_price,
        stop_price,
        target_price,
        exit_price,
        risk_amount,
        pnl,
        r_multiple,
        outcome,
        mae_price,
        mfe_price,
        mae_r,
        mfe_r
    )
    VALUES (
        :strategy_version,
        :ticker,
        :trade_date,
        :direction,
        :signal_time,
        :entry_time,
        :exit_time,
        :entry_price,
        :stop_price,
        :target_price,
        :exit_price,
        :risk_amount,
        :pnl,
        :r_multiple,
        :outcome,
        :mae_price,
        :mfe_price,
        :mae_r,
        :mfe_r
    )
    ON CONFLICT (
        strategy_version,
        ticker,
        trade_date
    )
    DO UPDATE SET
        signal_time = EXCLUDED.signal_time,
        entry_time = EXCLUDED.entry_time,
        exit_time = EXCLUDED.exit_time,
        entry_price = EXCLUDED.entry_price,
        stop_price = EXCLUDED.stop_price,
        target_price = EXCLUDED.target_price,
        exit_price = EXCLUDED.exit_price,
        risk_amount = EXCLUDED.risk_amount,
        pnl = EXCLUDED.pnl,
        r_multiple = EXCLUDED.r_multiple,
        outcome = EXCLUDED.outcome,
        mae_price = EXCLUDED.mae_price,
        mfe_price = EXCLUDED.mfe_price,
        mae_r = EXCLUDED.mae_r,
        mfe_r = EXCLUDED.mfe_r
""")

    with engine.begin() as conn:
        conn.execute(sql, trades)