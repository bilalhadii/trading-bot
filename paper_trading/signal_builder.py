from dataclasses import dataclass
from typing import Optional

import pandas as pd

from paper_trading.config import PaperTradingConfig
from paper_trading.order_plan import BracketOrderPlan, build_bracket_order_plan
from paper_trading.risk import RiskCheckResult, check_order_risk
from strategy.orb import calculate_opening_range
from strategy.signals import find_first_orb_retest_reclaim_body


@dataclass(frozen=True)
class PaperTradeDecision:
    approved: bool
    reason: str
    plan: Optional[BracketOrderPlan] = None
    signal: Optional[dict] = None
    risk_check: Optional[RiskCheckResult] = None


def build_retest_body_paper_trade_decision(
    session_df: pd.DataFrame,
    symbol: str,
    account_equity: float,
    config: PaperTradingConfig,
    realized_daily_pnl: float = 0.0,
    retest_max_bars: int = 5,
    tolerance_or_fraction: float = 0.10,
) -> PaperTradeDecision:
    if session_df.empty:
        return PaperTradeDecision(False, "NO_SESSION_DATA")
    if "timestamp_ny" not in session_df.columns:
        raise ValueError("session_df must include timestamp_ny.")

    session_df = session_df.sort_values("timestamp_ny").reset_index(drop=True)

    try:
        orb = calculate_opening_range(
            session_df,
            opening_minutes=5,
        )
    except ValueError:
        return PaperTradeDecision(False, "OPENING_RANGE_INCOMPLETE")

    signal = find_first_orb_retest_reclaim_body(
        session_df=session_df,
        or_high=orb["or_high"],
        or_low=orb["or_low"],
        max_bars=retest_max_bars,
        tolerance_or_fraction=tolerance_or_fraction,
    )

    if signal is None:
        return PaperTradeDecision(False, "NO_VALID_SIGNAL")

    entry_price = float(signal["entry_price"])
    direction = signal["direction"]

    if direction == "LONG":
        stop_price = float(orb["or_low"])
        target_price = entry_price + (entry_price - stop_price) * config.target_r
    else:
        stop_price = float(orb["or_high"])
        target_price = entry_price - (stop_price - entry_price) * config.target_r

    plan = build_bracket_order_plan(
        symbol=symbol,
        strategy_version=config.strategy_version,
        direction=direction,
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        account_equity=account_equity,
        risk_fraction=config.risk_fraction,
        max_notional_fraction=config.max_notional_fraction,
    )

    risk_check = check_order_risk(
        plan=plan,
        account_equity=account_equity,
        limits=config.risk_limits(),
        realized_daily_pnl=realized_daily_pnl,
    )

    return PaperTradeDecision(
        approved=risk_check.approved,
        reason=risk_check.reason,
        plan=plan,
        signal=signal,
        risk_check=risk_check,
    )
