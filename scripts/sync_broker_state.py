#!/usr/bin/env python3
"""
Sync Local Database with Broker State

Corrective sync: adjusts existing strategy positions to match broker totals.
Does NOT wipe positions — preserves strategy-level tracking and entry dates.
Only creates BROKER_SYNC entries for truly untracked positions.
"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import logging

from src.risk.broker_reconciler import BrokerReconciler

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _get_local_positions(cursor):
    """Get all local positions grouped by symbol, with strategy breakdown.

    Includes shorts (shares < 0). Filtering with `shares > 0` silently
    dropped shorts from the verification view, so this script's own
    post-sync verify step would always report local=0 vs broker=-N even
    after the negative-share row had just been inserted (see run
    25943767585: NFLX short of -24 shares).
    """
    cursor.execute(
        """
        SELECT p.strategy_id, s.name as strategy_name, p.symbol, p.shares, p.avg_price
        FROM positions p
        JOIN strategies s ON p.strategy_id = s.id
        WHERE p.shares != 0
        ORDER BY p.symbol, s.name
    """
    )
    rows = cursor.fetchall()

    # Build per-symbol aggregation and per-strategy detail
    by_symbol = (
        {}
    )  # {symbol: {'total': float, 'strategies': [(strategy_id, name, shares, avg_price)]}}
    for strategy_id, strategy_name, symbol, shares, avg_price in rows:
        if symbol not in by_symbol:
            by_symbol[symbol] = {"total": 0.0, "strategies": []}
        by_symbol[symbol]["total"] += shares
        by_symbol[symbol]["strategies"].append((strategy_id, strategy_name, shares, avg_price))

    return by_symbol


#: How far back to look for an order intent that explains an untracked broker
#: position. DAY marketable limits placed pre-market fill intraday the SAME
#: day, so the originating intent is normally 1 trading day old at sync time;
#: 5 calendar days covers long weekends + a missed run without matching
#: ancient intents to a genuinely manual/unknown position.
INTENT_ATTRIBUTION_LOOKBACK_DAYS = 5


def _find_entry_intent(cursor, symbol, broker_qty, lookback_days=INTENT_ATTRIBUTION_LOOKBACK_DAYS):
    """Find the order intent that explains an untracked broker position.

    Since PR #60 entries are DAY marketable limits that fill intraday AFTER
    the pre-market run ends. If the optimistic local position is lost before
    the next sync (e.g. a same-day duplicate run's "not in broker" sweep ran
    while the order was still resting), the fill shows up here as an
    untracked broker position. Without this lookup it would be adopted under
    BROKER_SYNC (orphaned from its strategy: no exit logic, and it eats a
    max_positions slot forever). Matching against recent order_intents —
    which carry strategy_id/symbol/side/target_qty — books it back under the
    strategy that actually bought it.

    Only long positions are attributed (side='BUY'); shorts don't record an
    opening intent, so they keep the BROKER_SYNC fallback. Returns
    (strategy_id, strategy_name, entry_date) or None.
    """
    if broker_qty <= 0:
        return None
    try:
        cursor.execute(
            """
            SELECT oi.strategy_id, s.name,
                   DATE(COALESCE(oi.filled_at, oi.submitted_at, oi.created_at)) AS entry_date
            FROM order_intents oi
            JOIN strategies s ON s.id = oi.strategy_id
            WHERE oi.symbol = ?
              AND oi.side = 'BUY'
              AND oi.status IN ('SUBMITTED', 'ACKED', 'FILLED')
              AND s.name != 'BROKER_SYNC'
              AND oi.created_at >= datetime('now', ?)
            ORDER BY (ABS(oi.target_qty - ?) < 0.001) DESC, oi.created_at DESC
            LIMIT 1
            """,
            (symbol, f"-{int(lookback_days)} days", broker_qty),
        )
        row = cursor.fetchone()
    except sqlite3.Error as exc:
        # order_intents may not exist in older/partial DBs — fall back to
        # BROKER_SYNC adoption rather than failing the whole sync.
        logger.warning(f"  ⚠️  {symbol}: intent lookup failed ({exc}); using BROKER_SYNC")
        return None
    if not row:
        return None
    return row[0], row[1], row[2]


def _get_or_create_broker_sync_strategy(cursor, portfolio_value):
    """Get or create the BROKER_SYNC strategy for untracked positions."""
    cursor.execute("SELECT id FROM strategies WHERE name = 'BROKER_SYNC' LIMIT 1")
    result = cursor.fetchone()
    if result:
        return result[0]

    cursor.execute(
        """
        INSERT INTO strategies (name, description, capital_allocation, initial_capital, status)
        VALUES ('BROKER_SYNC', 'Positions synced from broker', 0.0, ?, 'active')
    """,
        (portfolio_value,),
    )
    strategy_id = cursor.lastrowid
    logger.info(f"  Created BROKER_SYNC strategy (id={strategy_id})")
    return strategy_id


def sync_broker_to_database(db_path="trading.db"):
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

    broker_positions = broker_state["positions"]
    logger.info(
        f"\nBroker: {len(broker_positions)} positions, "
        f"Cash: ${broker_state['cash']:,.2f}, "
        f"Portfolio: ${broker_state['portfolio_value']:,.2f}"
    )

    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()

    try:
        local = _get_local_positions(cursor)
        sync_id = _get_or_create_broker_sync_strategy(cursor, broker_state["portfolio_value"])
        changes = 0

        logger.info(f"\nLocal: {len(local)} symbols tracked")
        logger.info("")

        # --- Reconcile each broker position ---
        for symbol, pos_data in broker_positions.items():
            broker_qty = float(pos_data["qty"])
            broker_avg = float(pos_data["avg_price"])
            # Alpaca occasionally reports avg_entry_price=0 (e.g. just after an
            # OPG fill before it settles). Writing 0 corrupts the position:
            # P&L computes off a zero basis and the stop-loss audit refuses to
            # synthesise a stop (avg_price<=0 → no protection). Fall back to the
            # implied price from market_value/qty so avg_price is never 0.
            if broker_avg <= 0 and broker_qty != 0:
                mkt_val = float(pos_data.get("market_value", 0.0) or 0.0)
                implied = abs(mkt_val / broker_qty) if mkt_val else 0.0
                if implied > 0:
                    logger.warning(
                        f"  ⚠️  {symbol}: broker avg_price=0; using implied "
                        f"${implied:.2f} from market_value/qty"
                    )
                    broker_avg = implied
            local_info = local.get(symbol)
            local_total = local_info["total"] if local_info else 0.0

            # Repair a corrupted local cost basis. A local avg_price of 0 (or
            # negative) is not cosmetic drift: P&L is then computed off a zero
            # basis (unrealized = full market value, e.g. VZ showed a phantom
            # +$1,146 "gain"), and the stop-loss audit refuses to synthesise a
            # stop when avg_price<=0. The qty-reconciliation branches below only
            # touch `shares`, so without this a zero basis survives forever even
            # when the quantity already matches the broker. Whenever the broker
            # reports a valid average, write it back to any local row whose
            # basis is non-positive — independent of the quantity diff.
            if broker_avg > 0 and local_info:
                repaired = []
                for sid, sname, sshares, savg in local_info["strategies"]:
                    if savg is None or savg <= 0:
                        cursor.execute(
                            "UPDATE positions SET avg_price = ?, "
                            "unrealized_pnl = (COALESCE(current_price, ?) - ?) * shares, "
                            "last_updated = ? WHERE strategy_id = ? AND symbol = ?",
                            (
                                broker_avg,
                                broker_avg,
                                broker_avg,
                                datetime.now().isoformat(),
                                sid,
                                symbol,
                            ),
                        )
                        logger.info(
                            f"  🩹 {symbol}: repaired cost basis in {sname} "
                            f"(avg_price 0 → ${broker_avg:.2f})"
                        )
                        changes += 1
                        repaired.append((sid, sname, sshares, broker_avg))
                    else:
                        repaired.append((sid, sname, sshares, savg))
                local_info["strategies"] = repaired

            diff = broker_qty - local_total

            if abs(diff) < 0.001:
                logger.info(f"  ✅ {symbol}: {broker_qty} shares — in sync")
                continue

            # Sign-flip: local is LONG but broker is SHORT (or vice versa).
            # The simple diff-based logic can't bridge opposite-direction positions
            # cleanly — it would delete the local long but not insert the broker short,
            # leaving local=0 vs broker=-N after the loop.  Clear the local side first
            # and then fall through to the local_total==0 insertion below.
            sign_flip = (
                local_info is not None
                and local_total != 0
                and broker_qty != 0
                and (local_total > 0) != (broker_qty > 0)
            )
            if sign_flip:
                for sid, sname, sshares, _ in local_info["strategies"]:
                    cursor.execute(
                        "DELETE FROM positions WHERE strategy_id = ? AND symbol = ?",
                        (sid, symbol),
                    )
                    logger.info(
                        f"  ♻️  {symbol}: cleared {sshares:.0f} shares from {sname} "
                        f"(sign-flip: local={local_total:+.0f} → broker={broker_qty:+.0f})"
                    )
                    changes += 1
                local_total = 0.0
                local_info = None

            if local_total == 0:
                # Entirely new position. Before orphaning it under BROKER_SYNC,
                # check whether a recent order intent explains it: DAY entries
                # fill intraday after the run ends, and if the optimistic local
                # row was lost the fill must go back to the strategy that
                # bought it — not strategy BROKER_SYNC where no exit logic
                # will ever manage it.
                intent_match = _find_entry_intent(cursor, symbol, broker_qty)
                if intent_match:
                    target_sid, target_name, entry_date = intent_match
                else:
                    # Truly untracked — adopt under BROKER_SYNC.
                    # Use today as entry_date fallback so time-based exits can fire.
                    target_sid, target_name = sync_id, "BROKER_SYNC"
                    entry_date = datetime.now().strftime("%Y-%m-%d")
                cursor.execute(
                    """
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
                """,
                    (
                        target_sid,
                        symbol,
                        broker_qty,
                        broker_avg,
                        broker_avg,
                        broker_qty * broker_avg,
                        0.0,
                        entry_date,
                        datetime.now().isoformat(),
                    ),
                )
                if intent_match:
                    logger.info(
                        f"  🎯 {symbol}: added {broker_qty} shares under {target_name} "
                        f"(matched order intent, entry_date={entry_date})"
                    )
                else:
                    logger.info(f"  🆕 {symbol}: added {broker_qty} shares under BROKER_SYNC")
                changes += 1

            elif diff > 0:
                # Local has fewer shares than broker — add the difference
                # Add to the strategy that already holds the most shares
                strats = sorted(local_info["strategies"], key=lambda x: x[2], reverse=True)
                target_sid, target_name, target_shares, target_avg = strats[0]
                new_shares = target_shares + diff
                # Weighted average price
                new_avg = (target_avg * target_shares + broker_avg * diff) / new_shares

                cursor.execute(
                    """
                    UPDATE positions SET shares = ?, avg_price = ?, last_updated = ?
                    WHERE strategy_id = ? AND symbol = ?
                """,
                    (new_shares, new_avg, datetime.now().isoformat(), target_sid, symbol),
                )
                logger.info(
                    f"  📈 {symbol}: added {diff:.0f} shares to {target_name} "
                    f"({target_shares:.0f} → {new_shares:.0f})"
                )
                changes += 1

            else:
                # Local has more shares than broker — reduce
                # Sort by abs(shares) so the largest positions absorb the excess first.
                # Using abs() is critical for short positions (negative shares) where
                # sorting by raw value would put the biggest shorts last.
                excess = abs(diff)
                strats = sorted(local_info["strategies"], key=lambda x: abs(x[2]), reverse=True)

                for sid, sname, sshares, _ in strats:
                    if excess <= 0:
                        break
                    reduce = min(abs(sshares), excess)
                    new_shares = sshares - reduce
                    excess -= reduce

                    if new_shares == 0:
                        cursor.execute(
                            "DELETE FROM positions WHERE strategy_id = ? AND symbol = ?",
                            (sid, symbol),
                        )
                        logger.info(f"  📉 {symbol}: removed from {sname} (was {sshares:.0f})")
                    else:
                        cursor.execute(
                            """
                            UPDATE positions SET shares = ?, last_updated = ?
                            WHERE strategy_id = ? AND symbol = ?
                        """,
                            (new_shares, datetime.now().isoformat(), sid, symbol),
                        )
                        logger.info(
                            f"  📉 {symbol}: reduced in {sname} "
                            f"({sshares:.0f} → {new_shares:.0f})"
                        )
                    changes += 1

        # --- Remove local positions not in broker ---
        # In the pre-run sync these are overwhelmingly yesterday's OPG orders
        # that were optimistically marked FILLED but never actually filled
        # (gap through the limit at the open). The count is persisted so
        # post_run_expect can surface a high fill-miss rate — previously
        # unfilled entries vanished without a trace.
        phantom_symbols: list[str] = []
        for symbol, local_info in local.items():
            if symbol not in broker_positions:
                phantom_symbols.append(symbol)
                for sid, sname, _, _ in local_info["strategies"]:
                    cursor.execute(
                        "DELETE FROM positions WHERE strategy_id = ? AND symbol = ?", (sid, symbol)
                    )
                    logger.info(f"  🗑️  {symbol}: removed from {sname} (not in broker)")
                    changes += 1
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS system_state ("
            "key TEXT PRIMARY KEY, value TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
        cursor.execute(
            "INSERT OR REPLACE INTO system_state (key, value) VALUES ('unfilled_opg_swept', ?)",
            (
                json.dumps(
                    {
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "count": len(phantom_symbols),
                        "symbols": phantom_symbols,
                    }
                ),
            ),
        )

        # --- Record sync event ---
        # created_at deliberately uses the column DEFAULT CURRENT_TIMESTAMP:
        # an explicit datetime.now().isoformat() here wrote local-time
        # 'YYYY-MM-DDTHH:MM:SS' while the engine's rows use the UTC space
        # format, and 'T' > ' ' made SYNC rows beat same-day engine rows in
        # every ORDER BY created_at DESC.
        cursor.execute(
            """
            INSERT INTO broker_state (
                run_id, snapshot_date, snapshot_type, cash, portfolio_value,
                buying_power, positions_json, reconciliation_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "AUTO_SYNC",
                datetime.now().strftime("%Y-%m-%d"),
                "SYNC",
                broker_state["cash"],
                broker_state["portfolio_value"],
                broker_state["buying_power"],
                json.dumps(broker_positions),
                "SYNCED",
            ),
        )

        conn.commit()

        # --- Verify ---
        updated_local = _get_local_positions(cursor)
        all_match = True
        for symbol, pos_data in broker_positions.items():
            broker_qty = float(pos_data["qty"])
            local_total = updated_local.get(symbol, {}).get("total", 0.0)
            if abs(local_total - broker_qty) > 0.001:
                logger.error(f"  ❌ {symbol}: local={local_total}, broker={broker_qty}")
                all_match = False

        logger.info(f"\n{'✅' if all_match else '❌'} Sync complete: {changes} changes made")
        logger.info(f"  Positions: {len(broker_positions)}")
        logger.info(f"  Cash: ${broker_state['cash']:,.2f}")
        logger.info(f"  Portfolio: ${broker_state['portfolio_value']:,.2f}")

        if all_match:
            logger.info("\n✅ VERIFICATION PASSED — all positions in sync")
        else:
            logger.error("\n❌ VERIFICATION FAILED — discrepancies remain")

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
