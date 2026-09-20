import os

from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


load_dotenv()

api_key = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")

client = StockHistoricalDataClient(
    api_key,
    secret_key,
)

request = StockBarsRequest(
    symbol_or_symbols=["AAPL"],
    timeframe=TimeFrame.Minute,
    start="2026-08-20T14:30:00Z",
    end="2026-08-20T15:30:00Z",
    feed="iex",
    limit=100,
)

bars = client.get_stock_bars(request)

print("Raw response:")
print(bars)

print("\nDataFrame:")
print(bars.df)
