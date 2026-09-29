from dataclasses import dataclass
from math import floor
from typing import Literal, Optional

from backtest.position_sizing import (
    PositionSize,
    calculate_risk_per_share,
    calculate_share_quantity,
)


OrderSide = Literal["buy", "sell"]
PositionSide = Literal["long", "short"]


@dataclass(frozen=True)
class BracketOrderPlan:
    symbol: str
    strategy_version: str
    position_side: PositionSide
    entry_side: OrderSide
    exit_side: OrderSide
    quantity: int
    entry_price_reference: float
    stop_price: float
    target_price: float
    risk_per_share: float
    planned_risk_dollars: float
    notional_dollars: float
    risk_fraction: float
    time_in_force: str = "day"
    order_class: str = "bracket"

    @property
    def is_tradeable(self) -> bool:
        return self.quantity > 0


def normalize_direction(direction: str) -> PositionSide:
    direction = direction.upper()

    if direction == "LONG":
        return "long"
    if direction == "SHORT":
        return "short"

    raise ValueError(f"Invalid direction: {direction}")


def build_bracket_order_plan(
    symbol: str,
    strategy_version: str,
    direction: str,
    entry_price: float,
    stop_price: float,
    target_price: float,
    account_equity: float,
    risk_fraction: float,
    max_notional_fraction: Optional[float] = None,
) -> BracketOrderPlan:
    if not symbol:
        raise ValueError("Symbol is required.")
    if not strategy_version:
        raise ValueError("Strategy version is required.")
    if target_price <= 0:
        raise ValueError("Target price must be positive.")

    position_side = normalize_direction(direction)
    risk_per_share = calculate_risk_per_share(
        direction,
        entry_price,
        stop_price,
    )

    if position_side == "long":
        if target_price <= entry_price:
            raise ValueError("Long target must be above entry.")
        entry_side: OrderSide = "buy"
        exit_side: OrderSide = "sell"
    else:
        if target_price >= entry_price:
            raise ValueError("Short target must be below entry.")
        entry_side = "sell"
        exit_side = "buy"

    size: PositionSize = calculate_share_quantity(
        account_equity=account_equity,
        risk_fraction=risk_fraction,
        direction=direction,
        entry_price=entry_price,
        stop_price=stop_price,
        max_notional_fraction=max_notional_fraction,
    )

    return BracketOrderPlan(
        symbol=symbol.upper(),
        strategy_version=strategy_version,
        position_side=position_side,
        entry_side=entry_side,
        exit_side=exit_side,
        quantity=size.shares,
        entry_price_reference=float(entry_price),
        stop_price=float(stop_price),
        target_price=float(target_price),
        risk_per_share=risk_per_share,
        planned_risk_dollars=size.planned_risk_dollars,
        notional_dollars=size.notional_dollars,
        risk_fraction=size.risk_fraction,
    )


def build_fixed_risk_bracket_order_plan(
    symbol: str,
    strategy_version: str,
    direction: str,
    entry_price: float,
    stop_price: float,
    target_price: float,
    risk_dollars: float,
) -> BracketOrderPlan:
    if risk_dollars <= 0:
        raise ValueError("Risk dollars must be positive.")
    if not symbol:
        raise ValueError("Symbol is required.")
    if not strategy_version:
        raise ValueError("Strategy version is required.")
    if target_price <= 0:
        raise ValueError("Target price must be positive.")

    position_side = normalize_direction(direction)
    risk_per_share = calculate_risk_per_share(
        direction,
        entry_price,
        stop_price,
    )

    if position_side == "long":
        if target_price <= entry_price:
            raise ValueError("Long target must be above entry.")
        entry_side: OrderSide = "buy"
        exit_side: OrderSide = "sell"
    else:
        if target_price >= entry_price:
            raise ValueError("Short target must be below entry.")
        entry_side = "sell"
        exit_side = "buy"

    quantity = max(0, floor(risk_dollars / risk_per_share))

    return BracketOrderPlan(
        symbol=symbol.upper(),
        strategy_version=strategy_version,
        position_side=position_side,
        entry_side=entry_side,
        exit_side=exit_side,
        quantity=quantity,
        entry_price_reference=float(entry_price),
        stop_price=float(stop_price),
        target_price=float(target_price),
        risk_per_share=risk_per_share,
        planned_risk_dollars=quantity * risk_per_share,
        notional_dollars=quantity * entry_price,
        risk_fraction=0.0,
    )
