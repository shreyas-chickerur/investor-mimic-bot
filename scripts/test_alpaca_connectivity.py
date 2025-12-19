#!/usr/bin/env python3

# Standard library imports
import os
import sys
from pathlib import Path

# Add project root to path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Third-party imports
from dotenv import load_dotenv


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def main() -> int:
    # Load .env if present (non-destructive if already exported)
    load_dotenv()

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        print("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in environment")
        return 2

    paper_trading = _bool_env("PAPER_TRADING", True)

    # Only override base URL if explicitly provided; otherwise rely on alpaca-py's defaults.
    base_url_env = os.getenv("ALPACA_BASE_URL")
    base_url: str
    if base_url_env:
        base_url = base_url_env.strip()
    else:
        base_url = (
            "https://paper-api.alpaca.markets" if paper_trading else "https://api.alpaca.markets"
        )

    # alpaca-py internally appends /v2; if the user provides a URL that already ends with /v2,
    # requests can become .../v2/v2/.... Sanitize a trailing /v2.
    if base_url.rstrip("/").endswith("/v2"):
        base_url = base_url.rstrip("/")[:-3]

    # alpaca-py (already in requirements.txt)
    from alpaca.trading.client import TradingClient

    if base_url_env:
        trading = TradingClient(api_key, secret_key, paper=paper_trading, url_override=base_url)
    else:
        trading = TradingClient(api_key, secret_key, paper=paper_trading)

    # Account
    account = trading.get_account()

    print("Alpaca connectivity: OK")
    print(f"Paper trading: {paper_trading}")
    print(f"Base URL: {base_url}")

    # These fields exist on the account model; we avoid printing secrets
    print("--- Account ---")
    print(f"Account ID: {getattr(account, 'id', None)}")
    print(f"Status: {getattr(account, 'status', None)}")
    print(f"Currency: {getattr(account, 'currency', None)}")
    print(f"Equity: {getattr(account, 'equity', None)}")
    print(f"Cash: {getattr(account, 'cash', None)}")
    print(f"Buying power: {getattr(account, 'buying_power', None)}")

    # Positions
    positions = trading.get_all_positions()

    print("--- Positions ---")
    if not positions:
        print("No open positions")
        return 0

    for p in positions:
        print(
            " ".join(
                [
                    f"symbol={getattr(p, 'symbol', None)}",
                    f"qty={getattr(p, 'qty', None)}",
                    f"market_value={getattr(p, 'market_value', None)}",
                    f"avg_entry_price={getattr(p, 'avg_entry_price', None)}",
                    f"unrealized_pl={getattr(p, 'unrealized_pl', None)}",
                ]
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
