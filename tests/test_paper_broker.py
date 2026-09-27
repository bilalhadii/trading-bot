from dataclasses import dataclass

from paper_trading.broker import (
    get_account_snapshot,
    symbol_has_open_order,
    symbol_has_open_position,
    symbol_is_clear_to_trade,
)


@dataclass
class FakeAccount:
    equity: str = "10000.50"
    buying_power: str = "20000.25"
    trading_blocked: bool = False


@dataclass
class FakePosition:
    symbol: str
    qty: str


@dataclass
class FakeOrder:
    symbol: str


class FakeTradingClient:
    def __init__(self, positions=None, orders=None):
        self.positions = positions or []
        self.orders = orders or []

    def get_account(self):
        return FakeAccount()

    def get_all_positions(self):
        return self.positions

    def get_orders(self):
        return self.orders


def test_get_account_snapshot():
    snapshot = get_account_snapshot(FakeTradingClient())

    assert snapshot.equity == 10000.50
    assert snapshot.buying_power == 20000.25
    assert not snapshot.trading_blocked


def test_symbol_has_open_position():
    assert symbol_has_open_position(
        [FakePosition("AAPL", "1")],
        "aapl",
    )
    assert not symbol_has_open_position(
        [FakePosition("AAPL", "0")],
        "AAPL",
    )


def test_symbol_has_open_order():
    assert symbol_has_open_order([FakeOrder("AAPL")], "aapl")
    assert not symbol_has_open_order([FakeOrder("MSFT")], "AAPL")


def test_symbol_is_clear_to_trade():
    assert symbol_is_clear_to_trade(FakeTradingClient(), "AAPL")
    assert not symbol_is_clear_to_trade(
        FakeTradingClient(positions=[FakePosition("AAPL", "1")]),
        "AAPL",
    )
    assert not symbol_is_clear_to_trade(
        FakeTradingClient(orders=[FakeOrder("AAPL")]),
        "AAPL",
    )
