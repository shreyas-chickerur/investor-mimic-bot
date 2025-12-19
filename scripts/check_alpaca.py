#!/usr/bin/env python3
"""
Simple script to test Alpaca API connection and display account information.
"""
import os
import sys
from decimal import Decimal

from alpaca.trading.client import TradingClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def main():
    try:
        # Initialize Alpaca client
        alpaca = TradingClient(
            os.getenv("ALPACA_API_KEY"),
            os.getenv("ALPACA_SECRET_KEY"),
            paper=True,  # Use paper trading by default
        )

        # Get account information
        account = alpaca.get_account()

        # Print account details
        print("\n=== Alpaca Account Information ===")
        print(f"Account ID: {account.id}")
        print(f"Status: {account.status}")
        print(f"Buying Power: ${account.buying_power}")
        print(f"Cash: ${account.cash}")
        print(f"Portfolio Value: ${account.portfolio_value}")
        print(f"Equity: ${account.equity}")
        print("\n=== Current Positions ===")

        # Get current positions
        try:
            positions = alpaca.get_all_positions()
            if positions:
                for position in positions:
                    print(f"{position.symbol}: {position.qty} shares (Market Value: ${position.market_value})")
            else:
                print("No positions found.")
        except Exception as e:
            print(f"Error fetching positions: {e}")

        print("\n=== Connection Test Successful! ===")

    except Exception as e:
        print("\n=== Error ===")
        print(f"Failed to connect to Alpaca: {e}")
        print("\nMake sure you have set up your .env file with the following variables:")
        print("ALPACA_API_KEY=your_api_key_here")
        print("ALPACA_SECRET_KEY=your_secret_key_here")
        sys.exit(1)


if __name__ == "__main__":
    main()
