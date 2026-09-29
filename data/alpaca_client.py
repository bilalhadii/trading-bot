import os
from datetime import datetime

from dotenv import load_dotenv

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
DATA_FEED = os.getenv("ALPACA_DATA_FEED", "iex")


if not API_KEY or not SECRET_KEY:
    raise RuntimeError(
        "ALPACA_API_KEY or ALPACA_SECRET_KEY is missing from .env"
    )


client = StockHistoricalDataClient(
    API_KEY,
    SECRET_KEY,
)


def get_minute_bars(
    ticker: str,
    start: datetime,
    end: datetime,
):
    """
    Retrieve 1-minute historical stock bars from Alpaca.
    """

    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Minute,
        start=start,
        end=end,
        feed=DATA_FEED,
    )

    return client.get_stock_bars(request)


def get_daily_bars(
    ticker: str,
    start: datetime,
    end: datetime,
):
    """
    Retrieve daily historical stock bars from Alpaca.
    """

    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DATA_FEED,
    )

    return client.get_stock_bars(request)
