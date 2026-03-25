#!/usr/bin/env python3
"""
Sync Local Database with Broker State

Corrective sync: adjusts existing strategy positions to match broker totals.
Does NOT wipe positions — preserves strategy-level tracking and entry dates.
Only creates BROKER_SYNC entries for truly untracked positions.
"""
import sys
import os
import sqlite3
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from src.risk.broker_reconciler import BrokerReconciler
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def _get_local_positions(cursor):
    """Get all local positions grouped by symbol, with strategy breakdown."""
    cursor.execute("""
        SELECT p.strategy_id, s.name as strategy_name, p.symbol, p.shares, p.avg_price
        FROM positions p
        JOIN strategies s ON p.strategy_id = s.id
        WHERE p.shares > 0
        ORDER BY p.symbol, s.name
    """)
    rows = cursor.fetchall()

    # Build per-symbol aggregation and per-strategy detail
    by_symbol = {}  # {symbol: {'total': float, 'strategies': [(strategy_id, name, shares, avg_price)]}}
    for strategy_id, strategy_name, symbol, shares, avg_price in rows:
        if symbol not in by_symbol:
            by_symbol[symbol] = {'total': 0.0, 'strategies': []}
        by_symbol[symbol]['total'] += shares
        by_symbol[symbol]['strategies'].append((strategy_id, strategy_name, shares, avg_price))

    return by_symbol


def _get_or_create_broker_sync_strategy(cursor, portfolio_value):
    """Get or create the BROKER_SYNC strategy for untracked positions."""
    cursor.execute("SELECT id FROM strategies WHERE name = 'BROKER_SYNC' LIMIT 1")
    result = cursor.fetchone()
    if result:
        return result[0]

    cursor.execute("""
        INSERT INTO strategies (name, description, capital_allocation, initial_capital, status)
        VALUES ('BROKER_SYNC', 'Positions synced from broker', 0.0, ?, 'active')
    """, (portfolio_value,))
    strategy_id = cursor.lastrowid
    logger.info(f"  Created BROKER_SYNC strategy (id={strategy_id})")
    return strategy_id


def sync_broker_to_database(db_path='trading.db'):
    """
    Corrective sync: compare local positions against broker and fix discrepancies.

    Strategy:
    1. For each broker position, check if local total matches.
    2. If local total is LESS than broker: add the difference to the strategy
       that already holds the most shares of that symbol (or BROKER_SYNC if none).
    3. If local total is MORE than broker: reduce from the strategy with the
       most shares (proportionally if needed).
    4. If a symbol exists in broker but not locally at all: add under BROKER_SYNC.
    5. If a symbol exists locally but not in broker: remove it.
    """
    logger.info("=" * 80)
    logger.info("CORRECTIVE SYNC: LOCAL DATABASE → BROKER STATE")
    logger.info("=" * 80)

    # Get broker state
    reconciler = BrokerReconciler()
    broker_state = reconciler.get_broker_state()

    if not broker_state:
        logger.error("❌ Failed to fetch broker state")
        return False

    broker_positions = broker_state['positions']
    logger.info(f"\nBroker: {len(broker_positions)} positions, "
                f"Cash: ${broker_state['cash']:,.2f}, "
                f"Portfolio: ${broker_state['portfolio_value']:,.2f}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        local = _get_local_positions(cursor)
        sync_id = _get_or_create_broker_sync_strategy(cursor, broker_state['portfolio_value'])
        changes = 0

        logger.info(f"\nLocal: {len(local)} symbols tracked")
        logger.info("")

        # --- Reconcile each broker position ---
        for symbol, pos_data in broker_positions.items():
            broker_qty = float(pos_data['qty'])
            broker_avg = float(pos_data['avg_price'])
            local_info = local.get(symbol)
            local_total = local_info['total'] if local_info else 0.0

            diff = broker_qty - local_total

            if abs(diff) < 0.001:
                logger.info(f"  ✅ {symbol}: {broker_qty} shares — in sync")
                continue

            if local_total == 0:
                # Entirely new position — add under BROKER_SYNC.
                # Use today as entry_date fallback so time-based exits can fire.
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute("""
                    INSERT INTO positions
                        (strategy_id, symbol, shares, avg_price, current_price,
                         market_value, unrealized_pnl, entry_date, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(strategy_id, symbol) DO UPDATE SET
                        shares = excluded.shares,
                        avg_price = excluded.avg_price,
                        current_price = excluded.current_price,
                        market_value = excluded.market_value,
                        unrealized_pnl = excluded.unrealized_pnl,
                        entry_date = COALESCE(positions.entry_date, excluded.entry_date),
                        last_updated = excluded.last_updated
                """, (
                    sync_id, symbol, broker_qty, broker_avg, broker_avg,
                    broker_qty * broker_avg, 0.0, today, datetime.now().isoformat()
                ))
                logger.info(f"  🆕 {symbol}: added {broker_qty} shares under BROKER_SYNC")
                changes += 1

            elif diff > 0:
                # Local has fewer shares than broker — add the difference
                # Add to the strategy that already holds the most shares
                strats = sorted(local_info['strategies'], key=lambda x: x[2], reverse=True)
                target_sid, target_name, target_shares, target_avg = strats[0]
                new_shares = target_shares + diff
                # Weighted average price
                new_avg = (target_avg * target_shares + broker_avg * diff) / new_shares

                cursor.execute("""
                    UPDATE positions SET shares = ?, avg_price = ?, last_updated = ?
                    WHERE strategy_id = ? AND symbol = ?
                """, (new_shares, new_avg, datetime.now().isoformat(), target_sid, symbol))
                logger.info(f"  📈 {symbol}: added {diff:.0f} shares to {target_name} "
                            f"({target_shares:.0f} → {new_shares:.0f})")
                changes += 1

            else:
                # Local has more shares than broker — reduce
                excess = abs(diff)
                strats = sorted(local_info['strategies'], key=lambda x: x[2], reverse=True)

                for sid, sname, sshares, savg in strats:
                    if excess <= 0:
                        break
                    reduce = min(sshares, excess)
                    new_shares = sshares - reduce
                    excess -= reduce

                    if new_shares <= 0:
                        cursor.execute("DELETE FROM positions WHERE strategy_id = ? AND symbol = ?",
                                       (sid, symbol))
                        logger.info(f"  📉 {symbol}: removed from {sname} (was {sshares:.0f})")
                    else:
                        cursor.execute("""
                            UPDATE positions SET shares = ?, last_updated = ?
                            WHERE strategy_id = ? AND symbol = ?
                        """, (new_shares, datetime.now().isoformat(), sid, symbol))
                        logger.info(f"  📉 {symbol}: reduced in {sname} "
                                    f"({sshares:.0f} → {new_shares:.0f})")
                    changes += 1

        # --- Remove local positions not in broker ---
        for symbol, local_info in local.items():
            if symbol not in broker_positions:
                for sid, sname, sshares, _ in local_info['strategies']:
                    cursor.execute("DELETE FROM positions WHERE strategy_id = ? AND symbol = ?",
                                   (sid, symbol))
                    logger.info(f"  🗑️  {symbol}: removed from {sname} (not in broker)")
                    changes += 1

        # --- Record sync event ---
        cursor.execute("""
            INSERT INTO broker_state (
                run_id, snapshot_date, snapshot_type, cash, portfolio_value,
                buying_power, positions_json, reconciliation_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'AUTO_SYNC',
            datetime.now().strftime('%Y-%m-%d'),
            'SYNC',
            broker_state['cash'],
            broker_state['portfolio_value'],
            broker_state['buying_power'],
            str(broker_positions),
            'SYNCED',
            datetime.now().isoformat()
        ))

        conn.commit()

        # --- Verify ---
        updated_local = _get_local_positions(cursor)
        all_match = True
        for symbol, pos_data in broker_positions.items():
            broker_qty = float(pos_data['qty'])
            local_total = updated_local.get(symbol, {}).get('total', 0.0)
            if abs(local_total - broker_qty) > 0.001:
                logger.error(f"  ❌ {symbol}: local={local_total}, broker={broker_qty}")
                all_match = False

        logger.info(f"\n{'✅' if all_match else '❌'} Sync complete: {changes} changes made")
        logger.info(f"  Positions: {len(broker_positions)}")
        logger.info(f"  Cash: ${broker_state['cash']:,.2f}")
        logger.info(f"  Portfolio: ${broker_state['portfolio_value']:,.2f}")

        if all_match:
            logger.info(f"\n✅ VERIFICATION PASSED — all positions in sync")
        else:
            logger.error(f"\n❌ VERIFICATION FAILED — discrepancies remain")

        return all_match

    except Exception as e:
        logger.error(f"\n❌ Sync failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = sync_broker_to_database()
    sys.exit(0 if success else 1)
