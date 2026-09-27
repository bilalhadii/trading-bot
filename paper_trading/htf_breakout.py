from dataclasses import dataclass
from typing import Optional

import pandas as pd

from paper_trading.config import PaperTradingConfig
from paper_trading.order_plan import BracketOrderPlan, build_bracket_order_plan
from paper_trading.risk import RiskCheckResult, check_order_risk


STRATEGY_VERSION = "HTF_BREAKOUT_RETEST_2R"


@dataclass(frozen=True)
class HTFBreakoutConfig:
    resistance_lookback_sessions: int = 40
    minimum_touches: int = 2
    level_tolerance_percent: float = 0.005
    breakout_buffer_percent: float = 0.001
    retest_tolerance_percent: float = 0.003
    stop_buffer_percent: float = 0.003
    max_bars_after_breakout_for_retest: int = 30
    target_r: float = 2.0


@dataclass(frozen=True)
class HTFTradeDecision:
    approved: bool
    reason: str
    plan: Optional[BracketOrderPlan] = None
    signal: Optional[dict] = None
    risk_check: Optional[RiskCheckResult] = None


def _prepare_daily(daily_df: pd.DataFrame) -> pd.DataFrame:
    if daily_df.empty:
        return daily_df.copy()
    df = daily_df.copy().sort_values("timestamp").reset_index(drop=True)
    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
    return df


def classify_trend(daily_df: pd.DataFrame) -> tuple[str, Optional[dict]]:
    df = _prepare_daily(daily_df)
    if len(df) < 21:
        return "INSUFFICIENT_DAILY_DATA", None

    latest = df.iloc[-1]
    close = float(latest["close"])
    ema9 = float(latest["ema9"])
    ema21 = float(latest["ema21"])

    if close > ema9 and close > ema21:
        state = "STRONG_BULLISH"
    elif close < ema9 and close > ema21:
        state = "BULLISH_PULLBACK"
    else:
        state = "NEUTRAL_BEARISH"

    return state, {
        "daily_close": close,
        "ema9": ema9,
        "ema21": ema21,
    }


def detect_resistance_level(
    daily_df: pd.DataFrame,
    config: HTFBreakoutConfig,
) -> tuple[Optional[float], int]:
    df = _prepare_daily(daily_df)
    if len(df) < config.resistance_lookback_sessions:
        return None, 0

    window = df.tail(config.resistance_lookback_sessions)
    candidate = float(window["high"].max())
    lower = candidate * (1 - config.level_tolerance_percent)
    upper = candidate * (1 + config.level_tolerance_percent)
    touches = int(
        (
            (window["high"] >= lower)
            & (window["high"] <= upper)
        ).sum()
    )

    if touches < config.minimum_touches:
        return None, touches

    return candidate, touches


def find_intraday_breakout_retest_signal(
    session_df: pd.DataFrame,
    resistance: float,
    config: HTFBreakoutConfig,
) -> tuple[Optional[dict], str]:
    if session_df.empty:
        return None, "NO_SESSION_DATA"
    if "timestamp_ny" not in session_df.columns:
        raise ValueError("session_df must include timestamp_ny.")

    df = session_df.sort_values("timestamp_ny").reset_index(drop=True)
    breakout_level = resistance * (1 + config.breakout_buffer_percent)
    retest_lower = resistance * (1 - config.retest_tolerance_percent)
    retest_upper = resistance * (1 + config.retest_tolerance_percent)
    invalidation = resistance * (1 - config.stop_buffer_percent)

    breakout_index = None
    breakout_candle = None
    for index, candle in df.iterrows():
        if float(candle["close"]) > breakout_level:
            breakout_index = index
            breakout_candle = candle
            break

    if breakout_index is None:
        return None, "NO_BREAKOUT"

    window_end = min(
        breakout_index + config.max_bars_after_breakout_for_retest + 1,
        len(df),
    )
    retest_candle = None

    for index in range(breakout_index + 1, window_end):
        candle = df.iloc[index]
        close = float(candle["close"])

        if close < invalidation:
            return None, "INVALIDATED"

        if retest_candle is None:
            overlaps_level = (
                float(candle["low"]) <= retest_upper
                and float(candle["high"]) >= retest_lower
            )
            if overlaps_level:
                retest_candle = candle
            continue

        confirmed = (
            close > float(retest_candle["high"])
            and close > float(candle["open"])
        )
        if confirmed:
            if index + 1 >= len(df):
                return None, "NO_ENTRY_CANDLE"
            entry = df.iloc[index + 1]
            return {
                "strategy_version": STRATEGY_VERSION,
                "direction": "LONG",
                "resistance": float(resistance),
                "breakout_timestamp": breakout_candle["timestamp_ny"],
                "breakout_close": float(breakout_candle["close"]),
                "retest_timestamp": retest_candle["timestamp_ny"],
                "retest_low": float(retest_candle["low"]),
                "confirmation_timestamp": candle["timestamp_ny"],
                "entry_timestamp": entry["timestamp_ny"],
                "entry_price": float(entry["open"]),
            }, "APPROVED"

    if retest_candle is None:
        return None, "NO_RETEST"
    return None, "NO_REVERSAL_CONFIRMATION"


def build_htf_breakout_paper_trade_decision(
    daily_df: pd.DataFrame,
    session_df: pd.DataFrame,
    symbol: str,
    account_equity: float,
    paper_config: PaperTradingConfig,
    htf_config: HTFBreakoutConfig = HTFBreakoutConfig(),
    realized_daily_pnl: float = 0.0,
) -> HTFTradeDecision:
    trend_state, trend_details = classify_trend(daily_df)
    if trend_state not in {"STRONG_BULLISH", "BULLISH_PULLBACK"}:
        return HTFTradeDecision(
            False,
            trend_state,
            signal={"trend_state": trend_state, "trend": trend_details},
        )

    resistance, touches = detect_resistance_level(daily_df, htf_config)
    if resistance is None:
        return HTFTradeDecision(
            False,
            "NO_VALID_RESISTANCE",
            signal={
                "trend_state": trend_state,
                "trend": trend_details,
                "resistance_touches": touches,
            },
        )

    signal, reason = find_intraday_breakout_retest_signal(
        session_df=session_df,
        resistance=resistance,
        config=htf_config,
    )
    if signal is None:
        return HTFTradeDecision(
            False,
            reason,
            signal={
                "trend_state": trend_state,
                "trend": trend_details,
                "resistance": resistance,
                "resistance_touches": touches,
            },
        )

    entry_price = float(signal["entry_price"])
    stop_price = min(
        float(signal["retest_low"]),
        resistance * (1 - htf_config.stop_buffer_percent),
    )
    risk = entry_price - stop_price
    if risk <= 0:
        return HTFTradeDecision(False, "INVALID_RISK", signal=signal)

    target_price = entry_price + risk * htf_config.target_r
    strategy_config = PaperTradingConfig(
        strategy_version=STRATEGY_VERSION,
        target_r=htf_config.target_r,
        risk_fraction=paper_config.risk_fraction,
        max_trade_risk_fraction=paper_config.max_trade_risk_fraction,
        max_notional_fraction=paper_config.max_notional_fraction,
        max_daily_loss_fraction=paper_config.max_daily_loss_fraction,
        allow_short_selling=paper_config.allow_short_selling,
    )
    plan = build_bracket_order_plan(
        symbol=symbol,
        strategy_version=STRATEGY_VERSION,
        direction="LONG",
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        account_equity=account_equity,
        risk_fraction=strategy_config.risk_fraction,
        max_notional_fraction=strategy_config.max_notional_fraction,
    )
    risk_check = check_order_risk(
        plan=plan,
        account_equity=account_equity,
        limits=strategy_config.risk_limits(),
        realized_daily_pnl=realized_daily_pnl,
    )
    signal = {
        **signal,
        "trend_state": trend_state,
        "trend": trend_details,
        "resistance_touches": touches,
    }

    return HTFTradeDecision(
        approved=risk_check.approved,
        reason=risk_check.reason,
        plan=plan,
        signal=signal,
        risk_check=risk_check,
    )
