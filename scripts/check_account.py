#!/usr/bin/env python3
"""
Alpaca Account Checker

This script connects to Alpaca's API using environment variables and displays:
- Account information
- Buying power
- Current positions
"""
import os

from dotenv import load_dotenv


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def main():
    # Load environment variables from .env file
    load_dotenv()

    # Get API keys from environment variables
    api_key = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_SECRET_KEY")

    if not api_key or not api_secret:
        print("Error: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env file")
        return

    paper = _bool_env("PAPER_TRADING", True)

    from alpaca.trading.client import TradingClient

    api = TradingClient(api_key, api_secret, paper=paper)

    try:
        # Get account information
        account = api.get_account()

        print("\n=== Account Information ===")
        print(f"Account Status: {account.status}")
        print(f"Buying Power: {getattr(account, 'buying_power', None)}")
        print(f"Cash: {getattr(account, 'cash', None)}")
        print(f"Portfolio Value: {getattr(account, 'portfolio_value', None)}")

        # Get current positions
        print("\n=== Current Positions ===")
        positions = api.get_all_positions()

        if not positions:
            print("No open positions.")
        else:
            for position in positions:
                print(f"\nSymbol: {position.symbol}")
                print(f"Quantity: {getattr(position, 'qty', None)} shares")
                print(f"Market Value: {getattr(position, 'market_value', None)}")
                print(f"Avg Entry Price: {getattr(position, 'avg_entry_price', None)}")
                print(f"Current Price: {getattr(position, 'current_price', None)}")
                print(f"Unrealized P/L: {getattr(position, 'unrealized_pl', None)}")

    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
