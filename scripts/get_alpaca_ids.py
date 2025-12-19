#!/usr/bin/env python3
"""
Fetch Alpaca Account ID and Bank IDs via API.

This script retrieves your Alpaca account ID and linked bank account IDs
so you can add them to your .env file.

Usage:
    python3 scripts/get_alpaca_ids.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alpaca.broker.client import BrokerClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def main():
    print("=" * 80)
    print("Fetching Alpaca Account and Bank IDs")
    print("=" * 80)
    print()

    # Get credentials from environment
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    paper_trading = os.getenv("ALPACA_PAPER", "True").lower() == "true"

    if not api_key or not secret_key:
        print("✗ Error: Missing Alpaca credentials")
        print()
        print("Make sure you have set in your .env file:")
        print("  - ALPACA_API_KEY")
        print("  - ALPACA_SECRET_KEY")
        print("  - ALPACA_PAPER (optional, defaults to True)")
        print()
        sys.exit(1)

    try:
        # Initialize Alpaca client
        client = BrokerClient(api_key=api_key, secret_key=secret_key, sandbox=paper_trading)

        print("✓ Connected to Alpaca API")
        print()

        # List all accounts to get the account ID
        print("Fetching account information...")
        accounts = client.list_accounts()

        if not accounts:
            print("✗ No accounts found")
            sys.exit(1)

        # Use the first account (usually you only have one)
        account = accounts[0]
        account_id = account.id

        print(f"Account ID: {account_id}")
        print(f"Account Number: {account.account_number}")
        print(f"Status: {account.status}")
        print()

        # Get linked bank accounts for this account
        print("Fetching linked bank accounts...")
        try:
            banks = client.get_banks_for_account(account_id)

            if banks:
                print(f"Found {len(banks)} linked bank account(s):")
                print()
                for i, bank in enumerate(banks, 1):
                    print(f"Bank {i}:")
                    print(f"  Bank ID: {bank.id}")
                    print(f"  Bank Name: {bank.bank_name}")
                    print(
                        f"  Account Type: {bank.account_type if hasattr(bank, 'account_type') else 'N/A'}"
                    )
                    print(f"  Status: {bank.status}")
                    print()
            else:
                print("⚠ No bank accounts linked yet.")
                print("Please link a bank account in the Alpaca dashboard first.")
                print()
        except Exception as e:
            print(f"⚠ Could not fetch bank accounts: {e}")
            print("You may need to link a bank account in the Alpaca dashboard.")
            print()

        # Print .env configuration
        print("=" * 80)
        print("Add these to your .env file:")
        print("=" * 80)
        print()
        print(f"ALPACA_ACCOUNT_ID={account.id}")

        if banks:
            # Use the first bank account by default
            print(f"ALPACA_BANK_ID={banks[0].id}")

            if len(banks) > 1:
                print()
                print("Note: You have multiple bank accounts. Using the first one.")
                print("If you want to use a different bank, copy the appropriate Bank ID above.")
        else:
            print("# ALPACA_BANK_ID=  # Link a bank account first")

        print()
        print("=" * 80)

    except Exception as e:
        print(f"✗ Error: {e}")
        print()
        print("Make sure you have set:")
        print("  - ALPACA_API_KEY")
        print("  - ALPACA_SECRET_KEY")
        print("  - ALPACA_PAPER (True for paper trading)")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
