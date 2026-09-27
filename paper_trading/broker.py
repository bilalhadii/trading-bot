import os
from dataclasses import dataclass
from typing import Iterable

from dotenv import load_dotenv


@dataclass(frozen=True)
class AccountSnapshot:
    equity: float
    buying_power: float
    trading_blocked: bool


def create_alpaca_paper_trading_client():
    load_dotenv()

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        raise RuntimeError(
            "ALPACA_API_KEY or ALPACA_SECRET_KEY is missing from .env"
        )

    from alpaca.trading.client import TradingClient

    return TradingClient(
        api_key,
        secret_key,
        paper=True,
    )


def get_account_snapshot(trading_client) -> AccountSnapshot:
    account = trading_client.get_account()

    return AccountSnapshot(
        equity=float(account.equity),
        buying_power=float(account.buying_power),
        trading_blocked=bool(account.trading_blocked),
    )


def symbol_has_open_position(
    positions: Iterable[object],
    symbol: str,
) -> bool:
    symbol = symbol.upper()
    return any(
        getattr(position, "symbol", "").upper() == symbol
        and float(getattr(position, "qty", 0)) != 0
        for position in positions
    )


def symbol_has_open_order(
    orders: Iterable[object],
    symbol: str,
) -> bool:
    symbol = symbol.upper()
    return any(
        getattr(order, "symbol", "").upper() == symbol
        for order in orders
    )


def symbol_is_clear_to_trade(
    trading_client,
    symbol: str,
) -> bool:
    return not symbol_has_open_position(
        trading_client.get_all_positions(),
        symbol,
    ) and not symbol_has_open_order(
        trading_client.get_orders(),
        symbol,
    )
