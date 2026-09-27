from dataclasses import dataclass

from paper_trading.order_plan import BracketOrderPlan


@dataclass(frozen=True)
class RiskLimits:
    max_trade_risk_fraction: float
    max_notional_fraction: float
    max_daily_loss_fraction: float
    allow_short_selling: bool = True


@dataclass(frozen=True)
class RiskCheckResult:
    approved: bool
    reason: str


def check_order_risk(
    plan: BracketOrderPlan,
    account_equity: float,
    limits: RiskLimits,
    realized_daily_pnl: float = 0.0,
) -> RiskCheckResult:
    if account_equity <= 0:
        raise ValueError("Account equity must be positive.")
    if limits.max_trade_risk_fraction <= 0:
        raise ValueError("Max trade risk fraction must be positive.")
    if limits.max_notional_fraction <= 0:
        raise ValueError("Max notional fraction must be positive.")
    if limits.max_daily_loss_fraction <= 0:
        raise ValueError("Max daily loss fraction must be positive.")

    if not plan.is_tradeable:
        return RiskCheckResult(False, "ZERO_QUANTITY")

    if plan.position_side == "short" and not limits.allow_short_selling:
        return RiskCheckResult(False, "SHORT_SELLING_DISABLED")

    trade_risk_fraction = plan.planned_risk_dollars / account_equity
    if trade_risk_fraction > limits.max_trade_risk_fraction:
        return RiskCheckResult(False, "TRADE_RISK_LIMIT")

    notional_fraction = plan.notional_dollars / account_equity
    if notional_fraction > limits.max_notional_fraction:
        return RiskCheckResult(False, "NOTIONAL_LIMIT")

    daily_loss_fraction = max(0.0, -realized_daily_pnl) / account_equity
    if daily_loss_fraction >= limits.max_daily_loss_fraction:
        return RiskCheckResult(False, "DAILY_LOSS_LIMIT")

    return RiskCheckResult(True, "APPROVED")
