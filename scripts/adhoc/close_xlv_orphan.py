#!/usr/bin/env python3
"""
One-shot script: close the BROKER_SYNC XLV orphan position.

Context (2026-05-28): the Alpaca paper account holds 11 shares of XLV
that aren't owned by any canonical strategy. The position dates back to
an April reconciliation incident and has been carried under the
synthetic BROKER_SYNC strategy ever since. It currently shows ~+$36
unrealized profit and clutters every email's portfolio-value vs cash
breakdown.

This script:
  1. Loads .env for Alpaca paper creds.
  2. Confirms the broker actually holds the position and prints
     pre-trade state (qty, current price, market value).
  3. Submits a market SELL day order for the full position.
  4. Polls the order until it fills (or times out) and prints the result.

After the order fills, the next scheduled trading run will reconcile
the local DB and the BROKER_SYNC row will drop to zero.

Usage:
    python3 scripts/adhoc/close_xlv_orphan.py            # dry run
    python3 scripts/adhoc/close_xlv_orphan.py --confirm  # actually sell
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

SYMBOL = "XLV"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually submit the SELL order. Without this flag the script is dry-run.",
    )
    args = parser.parse_args()

    api_key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"

    if not api_key or not secret:
        print("ERROR: ALPACA_API_KEY / ALPACA_SECRET_KEY not set in .env", file=sys.stderr)
        return 2

    if not paper:
        print(
            "ERROR: ALPACA_PAPER is not 'true'. Refusing to run against a live account.",
            file=sys.stderr,
        )
        return 2

    client = TradingClient(api_key, secret, paper=True)

    # Verify the position exists at the broker before doing anything else.
    try:
        positions = client.get_all_positions()
    except Exception as e:
        print(f"ERROR: failed to fetch positions: {e}", file=sys.stderr)
        return 2

    xlv = next((p for p in positions if p.symbol == SYMBOL), None)
    if xlv is None:
        print(f"No {SYMBOL} position at broker — nothing to do. Exiting cleanly.")
        return 0

    qty = float(xlv.qty)
    avg_entry = float(xlv.avg_entry_price)
    current = float(xlv.current_price) if xlv.current_price else 0.0
    market_value = float(xlv.market_value) if xlv.market_value else qty * current
    unrealized = float(xlv.unrealized_pl) if xlv.unrealized_pl else 0.0

    print("=" * 60)
    print(f"Pre-trade position for {SYMBOL}:")
    print(f"  qty:          {qty:.4f}")
    print(f"  avg entry:    ${avg_entry:.2f}")
    print(f"  current:      ${current:.2f}")
    print(f"  market value: ${market_value:,.2f}")
    print(f"  unrealized:   ${unrealized:+,.2f}")
    print("=" * 60)

    if qty <= 0:
        print(
            f"Position qty is {qty} (not long). This script only handles long-side closes.",
            file=sys.stderr,
        )
        return 2

    if not args.confirm:
        print("Dry run. Re-run with --confirm to actually submit the SELL order.")
        return 0

    print(f"Submitting market SELL for {qty:.4f} shares of {SYMBOL} (day order)...")
    order = client.submit_order(
        MarketOrderRequest(
            symbol=SYMBOL,
            qty=qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
    )
    print(f"Order submitted: id={order.id}, status={order.status}")

    # Poll briefly for a terminal status. Market orders during RTH usually fill
    # in under a second; outside RTH the order will sit until the next session.
    for _ in range(20):
        time.sleep(0.5)
        latest = client.get_order_by_id(order.id)
        status = str(latest.status).lower()
        if status in ("filled", "canceled", "rejected", "expired"):
            print(f"Final order status: {latest.status}")
            if latest.filled_avg_price is not None:
                fill_price = float(latest.filled_avg_price)
                realized = (fill_price - avg_entry) * qty
                print(f"  filled qty:    {latest.filled_qty}")
                print(f"  fill price:    ${fill_price:.2f}")
                print(f"  realized P&L:  ${realized:+,.2f}")
            return 0

    print(
        "Order is still pending after 10s. It will most likely fill at the next market "
        "open if submitted outside RTH. Check the Alpaca dashboard or the next email."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
