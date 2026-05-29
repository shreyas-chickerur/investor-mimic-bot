"""Reconcile local DB state against Alpaca paper account.

Verifies:
  1. Current open positions (broker vs local) - is XLV still held?
  2. The 7 ACKED order_intents - what's their real broker status?
  3. The 19 SELL trades - did they actually fill at the broker?
  4. Account cash to corroborate the cash-impact divergence finding.

Usage: python3 scripts/adhoc/verify_against_alpaca.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from alpaca.trading.client import TradingClient  # noqa: E402
from alpaca.trading.enums import QueryOrderStatus  # noqa: E402
from alpaca.trading.requests import GetOrdersRequest  # noqa: E402


def fmt(x: float, w: int = 12) -> str:
    return f"{x:>{w},.2f}"


def main() -> None:
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        print("ERROR: ALPACA credentials missing from .env")
        sys.exit(1)
    client = TradingClient(api_key, secret_key, paper=True)

    print("=" * 80)
    print("1. ACCOUNT STATE")
    print("=" * 80)
    acct = client.get_account()
    print(f"  cash             ${float(acct.cash):>14,.2f}")
    print(f"  portfolio_value  ${float(acct.portfolio_value):>14,.2f}")
    print(f"  buying_power     ${float(acct.buying_power):>14,.2f}")
    print(f"  equity           ${float(acct.equity):>14,.2f}")
    print(f"  status           {acct.status}")

    print()
    print("=" * 80)
    print("2. BROKER POSITIONS vs LOCAL DB")
    print("=" * 80)
    broker_positions = client.get_all_positions()
    broker_by_symbol = {p.symbol: p for p in broker_positions}

    conn = sqlite3.connect(str(ROOT / "trading.db"))
    local_rows = conn.execute(
        """
        SELECT p.symbol, s.name AS strategy, p.shares, p.avg_price, p.current_price
        FROM positions p JOIN strategies s ON p.strategy_id=s.id
        WHERE p.shares != 0
        ORDER BY p.symbol, s.name
        """
    ).fetchall()
    local_total_by_symbol: dict[str, float] = {}
    print(
        f"  {'symbol':<8}{'strategy':<22}{'local sh':>10}{'broker sh':>12}{'avg_px':>12}{'broker_px':>12}"
    )
    for sym, strat, shares, avg_px, _cur in local_rows:
        local_total_by_symbol[sym] = local_total_by_symbol.get(sym, 0.0) + shares
        bsh = float(broker_by_symbol[sym].qty) if sym in broker_by_symbol else 0.0
        bpx = float(broker_by_symbol[sym].avg_entry_price) if sym in broker_by_symbol else 0.0
        flag = "" if abs(shares - bsh) < 1e-6 or len(local_rows) > 1 else "  <-- MISMATCH"
        print(f"  {sym:<8}{strat:<22}{shares:>10.2f}{bsh:>12.2f}{avg_px:>12.2f}{bpx:>12.2f}{flag}")

    # Symbol-level reconciliation
    print()
    print("  Symbol-level reconciliation (local total across strategies vs broker):")
    all_syms = sorted(set(local_total_by_symbol) | set(broker_by_symbol))
    for sym in all_syms:
        local_sh = local_total_by_symbol.get(sym, 0.0)
        broker_sh = float(broker_by_symbol[sym].qty) if sym in broker_by_symbol else 0.0
        delta = local_sh - broker_sh
        flag = "" if abs(delta) < 1e-6 else f"  <-- DELTA {delta:+.2f}"
        print(f"    {sym:<8}  local={local_sh:>8.2f}  broker={broker_sh:>8.2f}{flag}")

    print()
    print("=" * 80)
    print("3. THE 7 STALE ACKED ORDER INTENTS - real broker status")
    print("=" * 80)
    acked = conn.execute(
        """
        SELECT created_at, symbol, side, target_qty, broker_order_id
        FROM order_intents WHERE status='ACKED'
        ORDER BY created_at DESC
        """
    ).fetchall()
    for created, sym, side, qty, broker_id in acked:
        try:
            o = client.get_order_by_id(broker_id)
            print(
                f"  {created} {sym:<6} {side} {qty:>4}  broker_status={o.status}  filled={o.filled_qty}@{o.filled_avg_price}"
            )
        except Exception as exc:
            print(f"  {created} {sym:<6} {side} {qty:>4}  ERROR: {exc}")

    print()
    print("=" * 80)
    print("4. LAST 30 BROKER ORDERS (any side, any status)")
    print("=" * 80)
    req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=30, nested=False)
    orders = client.get_orders(filter=req)
    for o in orders:
        ts = str(o.submitted_at)[:19] if o.submitted_at else "-"
        fp = f"@{o.filled_avg_price}" if o.filled_avg_price else ""
        print(
            f"  {ts}  {o.symbol:<6} {o.side} {o.qty:>4}  {o.status.value:<12} filled={o.filled_qty}{fp}"
        )

    print()
    print("=" * 80)
    print("5. LOCAL SELL TRADES vs BROKER ORDER HISTORY")
    print("=" * 80)
    sells = conn.execute(
        """
        SELECT t.executed_at, t.symbol, t.shares, t.exec_price, t.order_id
        FROM trades t WHERE t.action='SELL'
        ORDER BY t.executed_at DESC
        """
    ).fetchall()
    print(f"  Total local SELL trades: {len(sells)}")
    matched, unmatched = 0, 0
    for executed_at, sym, shares, exec_px, order_id in sells:
        try:
            o = client.get_order_by_id(order_id)
            is_sell = str(o.side).upper().endswith("SELL")
            is_filled = str(o.status).lower().endswith("filled")
            if is_sell and is_filled:
                matched += 1
                bpx = float(o.filled_avg_price) if o.filled_avg_price else 0.0
                drift_bps = ((bpx - exec_px) / exec_px * 1e4) if exec_px else 0
                print(
                    f"  ✓ {executed_at[:19]} {sym:<6} SELL {shares:>4} local=${exec_px:.2f} broker=${bpx:.2f} ({drift_bps:+.0f}bps)"
                )
            else:
                unmatched += 1
                print(
                    f"  ✗ {executed_at[:19]} {sym:<6} SELL {shares:>4} broker_side={o.side} status={o.status}"
                )
        except Exception as exc:
            unmatched += 1
            print(f"  ? {executed_at[:19]} {sym:<6} SELL {shares:>4} {order_id[:8]} ERROR: {exc}")
    print(f"\n  Matched: {matched}/{len(sells)}, Unmatched: {unmatched}")


if __name__ == "__main__":
    main()
