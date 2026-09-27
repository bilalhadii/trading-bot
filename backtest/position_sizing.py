from dataclasses import dataclass
from math import floor
from typing import Optional


@dataclass(frozen=True)
class PositionSize:
    shares: int
    risk_per_share: float
    planned_risk_dollars: float
    notional_dollars: float
    risk_fraction: float


@dataclass(frozen=True)
class ExecutionCostResult:
    shares: int
    gross_pnl_dollars: float
    commission_dollars: float
    slippage_dollars: float
    net_pnl_dollars: float
    gross_r_multiple: float
    net_r_multiple: float


def calculate_risk_per_share(
    direction: str,
    entry_price: float,
    stop_price: float,
) -> float:
    direction = direction.upper()

    if direction == "LONG":
        risk_per_share = entry_price - stop_price
    elif direction == "SHORT":
        risk_per_share = stop_price - entry_price
    else:
        raise ValueError(f"Invalid direction: {direction}")

    if risk_per_share <= 0:
        raise ValueError("Risk per share must be positive.")

    return float(risk_per_share)


def calculate_share_quantity(
    account_equity: float,
    risk_fraction: float,
    direction: str,
    entry_price: float,
    stop_price: float,
    max_notional_fraction: Optional[float] = None,
) -> PositionSize:
    if account_equity <= 0:
        raise ValueError("Account equity must be positive.")
    if risk_fraction <= 0:
        raise ValueError("Risk fraction must be positive.")
    if entry_price <= 0:
        raise ValueError("Entry price must be positive.")
    if max_notional_fraction is not None and max_notional_fraction <= 0:
        raise ValueError("Max notional fraction must be positive.")

    risk_per_share = calculate_risk_per_share(
        direction,
        entry_price,
        stop_price,
    )

    target_risk_dollars = account_equity * risk_fraction
    risk_limited_shares = floor(target_risk_dollars / risk_per_share)

    if max_notional_fraction is not None:
        max_notional_dollars = account_equity * max_notional_fraction
        notional_limited_shares = floor(max_notional_dollars / entry_price)
        shares = min(risk_limited_shares, notional_limited_shares)
    else:
        shares = risk_limited_shares

    shares = max(0, shares)

    return PositionSize(
        shares=shares,
        risk_per_share=risk_per_share,
        planned_risk_dollars=shares * risk_per_share,
        notional_dollars=shares * entry_price,
        risk_fraction=(shares * risk_per_share) / account_equity,
    )


def calculate_trade_pnl_per_share(
    direction: str,
    entry_price: float,
    exit_price: float,
) -> float:
    direction = direction.upper()

    if direction == "LONG":
        return float(exit_price - entry_price)
    if direction == "SHORT":
        return float(entry_price - exit_price)

    raise ValueError(f"Invalid direction: {direction}")


def calculate_round_trip_execution_costs(
    entry_price: float,
    exit_price: float,
    shares: int,
    commission_per_share: float = 0.0,
    slippage_bps: float = 0.0,
) -> tuple[float, float]:
    if shares < 0:
        raise ValueError("Shares cannot be negative.")
    if commission_per_share < 0:
        raise ValueError("Commission per share cannot be negative.")
    if slippage_bps < 0:
        raise ValueError("Slippage bps cannot be negative.")
    if entry_price <= 0 or exit_price <= 0:
        raise ValueError("Entry and exit prices must be positive.")

    traded_notional = shares * (entry_price + exit_price)
    commission = shares * commission_per_share * 2
    slippage = traded_notional * (slippage_bps / 10_000)

    return float(commission), float(slippage)


def calculate_execution_result(
    direction: str,
    entry_price: float,
    stop_price: float,
    exit_price: float,
    shares: int,
    commission_per_share: float = 0.0,
    slippage_bps: float = 0.0,
) -> ExecutionCostResult:
    if shares < 0:
        raise ValueError("Shares cannot be negative.")

    risk_per_share = calculate_risk_per_share(
        direction,
        entry_price,
        stop_price,
    )
    planned_risk_dollars = shares * risk_per_share

    pnl_per_share = calculate_trade_pnl_per_share(
        direction,
        entry_price,
        exit_price,
    )
    gross_pnl = shares * pnl_per_share

    commission, slippage = calculate_round_trip_execution_costs(
        entry_price=entry_price,
        exit_price=exit_price,
        shares=shares,
        commission_per_share=commission_per_share,
        slippage_bps=slippage_bps,
    )

    net_pnl = gross_pnl - commission - slippage

    if planned_risk_dollars == 0:
        gross_r = 0.0
        net_r = 0.0
    else:
        gross_r = gross_pnl / planned_risk_dollars
        net_r = net_pnl / planned_risk_dollars

    return ExecutionCostResult(
        shares=shares,
        gross_pnl_dollars=float(gross_pnl),
        commission_dollars=commission,
        slippage_dollars=slippage,
        net_pnl_dollars=float(net_pnl),
        gross_r_multiple=float(gross_r),
        net_r_multiple=float(net_r),
    )
