import os

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient


load_dotenv()

api_key = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")

if not api_key or not secret_key:
    raise ValueError("Alpaca API credentials are missing from .env")


client = TradingClient(
    api_key=api_key,
    secret_key=secret_key,
    paper=True,
)

account = client.get_account()

print("Alpaca connection: OK")
print("Account status:", account.status)
print("Account number:", account.account_number)
print("Cash:", account.cash)
print("Buying power:", account.buying_power)
