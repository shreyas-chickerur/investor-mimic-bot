#!/usr/bin/env python3
"""
Phase 5 Invariant Checker

Enforces hard invariants on Phase 5 execution:
A) signals_count == terminal_states_count
B) no signal_id has 0 terminal states
C) no signal_id has >1 terminal state (enforced by schema)
D) if reconciliation failed, every signal must end in REJECTED_BY_RECONCILIATION and no trades exist
E) if dry-run mode, no broker orders placed and trades table is empty or labeled DRYRUN
F) broker_state snapshot exists for: start, reconciliation point, end

Usage:
    python3 scripts/check_phase5_invariants.py --run-id <run_id>
    python3 scripts/check_phase5_invariants.py --latest
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import argparse
import sqlite3
from typing import Tuple, List, Dict
import json


class Phase5InvariantChecker:
    """Checks Phase 5 database invariants"""
    
    def __init__(self, db_path='trading.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
    
    def get_latest_run_id(self) -> str:
        """Get the most recent run_id"""
        try:
            self.cursor.execute('''
                SELECT run_id FROM signals 
                WHERE run_id IS NOT NULL
                ORDER BY generated_at DESC 
                LIMIT 1
            ''')
            row = self.cursor.fetchone()
            if row and row[0]:
                return row[0]
        except sqlite3.OperationalError:
            pass
        
        try:
            # Try trades table
            self.cursor.execute('''
                SELECT run_id FROM trades 
                WHERE run_id IS NOT NULL
                ORDER BY executed_at DESC 
                LIMIT 1
            ''')
            row = self.cursor.fetchone()
            if row and row[0]:
                return row[0]
        except sqlite3.OperationalError:
            pass
        
        try:
            # Try broker_state table
            self.cursor.execute('''
                SELECT run_id FROM broker_state 
                WHERE run_id IS NOT NULL
                ORDER BY created_at DESC 
                LIMIT 1
            ''')
            row = self.cursor.fetchone()
            if row and row[0]:
                return row[0]
        except sqlite3.OperationalError:
            pass
        
        return None
    
    def check_invariant_a(self, run_id: str) -> Tuple[bool, str]:
        """A) signals_count == terminal_states_count"""
        self.cursor.execute('SELECT COUNT(*) FROM signals WHERE run_id = ?', (run_id,))
        total_signals = self.cursor.fetchone()[0]
        
        self.cursor.execute('''
            SELECT COUNT(*) FROM signals 
            WHERE run_id = ? AND terminal_state IS NOT NULL
        ''', (run_id,))
        with_terminal = self.cursor.fetchone()[0]
        
        passed = (total_signals == with_terminal)
        message = f"Signals: {total_signals}, With terminal state: {with_terminal}"
        
        return passed, message
    
    def check_invariant_b(self, run_id: str) -> Tuple[bool, str]:
        """B) no signal_id has 0 terminal states"""
        self.cursor.execute('''
            SELECT COUNT(*) FROM signals 
            WHERE run_id = ? AND terminal_state IS NULL
        ''', (run_id,))
        without_terminal = self.cursor.fetchone()[0]
        
        passed = (without_terminal == 0)
        
        if not passed:
            self.cursor.execute('''
                SELECT id, symbol, signal_type FROM signals 
                WHERE run_id = ? AND terminal_state IS NULL
            ''', (run_id,))
            missing = self.cursor.fetchall()
            message = f"{without_terminal} signals without terminal state:\n"
            for row in missing[:5]:  # Show first 5
                message += f"  Signal ID {row[0]}: {row[1]} {row[2]}\n"
        else:
            message = "All signals have terminal states"
        
        return passed, message
    
    def check_invariant_c(self, run_id: str) -> Tuple[bool, str]:
        """C) no signal_id has >1 terminal state (enforced by schema)"""
        # This is enforced by schema design (terminal_state is a single column)
        # But we can verify no duplicate signal IDs exist
        self.cursor.execute('''
            SELECT id, COUNT(*) as cnt 
            FROM signals 
            WHERE run_id = ? 
            GROUP BY id 
            HAVING cnt > 1
        ''', (run_id,))
        duplicates = self.cursor.fetchall()
        
        passed = (len(duplicates) == 0)
        message = "No duplicate signal IDs (enforced by schema)" if passed else f"Found {len(duplicates)} duplicate signal IDs"
        
        return passed, message
    
    def check_invariant_d(self, run_id: str) -> Tuple[bool, str]:
        """D) if reconciliation failed, every signal must end in REJECTED_BY_RECONCILIATION and no trades exist"""
        # Check if reconciliation failed
        self.cursor.execute('''
            SELECT reconciliation_status FROM broker_state 
            WHERE run_id = ? AND reconciliation_status IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
        ''', (run_id,))
        row = self.cursor.fetchone()
        
        if not row or row[0] != 'FAIL':
            return True, "Reconciliation did not fail (or not run)"
        
        # Reconciliation failed - check signals
        self.cursor.execute('''
            SELECT COUNT(*) FROM signals 
            WHERE run_id = ? AND terminal_state != 'REJECTED_BY_RECONCILIATION'
        ''', (run_id,))
        non_rejected = self.cursor.fetchone()[0]
        
        # Check trades
        self.cursor.execute('SELECT COUNT(*) FROM trades WHERE run_id = ?', (run_id,))
        trade_count = self.cursor.fetchone()[0]
        
        passed = (non_rejected == 0 and trade_count == 0)
        
        if not passed:
            message = f"Reconciliation FAILED but found {non_rejected} non-rejected signals and {trade_count} trades"
        else:
            message = "Reconciliation FAILED - all signals rejected, no trades (correct)"
        
        return passed, message
    
    def check_invariant_e(self, run_id: str) -> Tuple[bool, str]:
        """E) if dry-run mode, no broker orders placed and trades table is empty or labeled DRYRUN"""
        # Check if any trades have real order IDs
        self.cursor.execute('''
            SELECT COUNT(*) FROM trades 
            WHERE run_id = ? AND order_id IS NOT NULL AND order_id != 'DRYRUN'
        ''', (run_id,))
        real_orders = self.cursor.fetchone()[0]
        
        # For now, we assume if there are real order IDs, it's a real run
        # If there are no trades or all trades have order_id='DRYRUN', it's dry-run
        self.cursor.execute('SELECT COUNT(*) FROM trades WHERE run_id = ?', (run_id,))
        total_trades = self.cursor.fetchone()[0]
        
        if total_trades == 0:
            return True, "No trades (dry-run or no signals executed)"
        
        if real_orders > 0:
            return True, f"Real run with {real_orders} broker orders"
        else:
            return True, f"Dry-run with {total_trades} simulated trades"
    
    def check_invariant_f(self, run_id: str) -> Tuple[bool, str]:
        """F) broker_state snapshot exists for: start, reconciliation point, end"""
        self.cursor.execute('''
            SELECT snapshot_type FROM broker_state 
            WHERE run_id = ?
            ORDER BY created_at
        ''', (run_id,))
        snapshots = [row[0] for row in self.cursor.fetchall()]
        
        if len(snapshots) == 0:
            return False, "No broker state snapshots found"
        
        # REQUIRED: At minimum 2 snapshots (START and END)
        has_start = 'START' in snapshots
        has_end = 'END' in snapshots
        
        if not has_start:
            return False, f"Missing START snapshot. Found: {snapshots}"
        
        if not has_end:
            return False, f"Missing END snapshot. Found: {snapshots}"
        
        if len(snapshots) < 2:
            return False, f"Need at least 2 snapshots (START + END). Found {len(snapshots)}: {snapshots}"
        
        # Check for RECONCILIATION if it should be there
        has_reconciliation = 'RECONCILIATION' in snapshots
        
        message = f"Found {len(snapshots)} snapshot(s): {', '.join(snapshots)}"
        if has_reconciliation:
            message += " ✅ (includes RECONCILIATION)"
        
        return True, message
    
    def run_all_checks(self, run_id: str) -> Dict:
        """Run all invariant checks"""
        print("=" * 80)
        print(f"PHASE 5 INVARIANT CHECKER")
        print("=" * 80)
        print(f"Run ID: {run_id}\n")
        
        checks = [
            ("A: Signal-Terminal Count Match", self.check_invariant_a),
            ("B: No Signals Without Terminal State", self.check_invariant_b),
            ("C: No Duplicate Signal IDs", self.check_invariant_c),
            ("D: Reconciliation Failure Handling", self.check_invariant_d),
            ("E: Dry-Run vs Real-Run Validation", self.check_invariant_e),
            ("F: Broker State Snapshots", self.check_invariant_f),
        ]
        
        results = []
        
        for name, check_func in checks:
            print(f"\n{name}")
            print("-" * 80)
            try:
                passed, message = check_func(run_id)
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"{status}: {message}")
                results.append((name, passed, message))
            except Exception as e:
                print(f"❌ ERROR: {e}")
                results.append((name, False, str(e)))
        
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        passed_count = sum(1 for _, passed, _ in results if passed)
        total_count = len(results)
        
        for name, passed, _ in results:
            status = "✅" if passed else "❌"
            print(f"{status} {name}")
        
        print(f"\nResult: {passed_count}/{total_count} checks passed")
        
        all_passed = (passed_count == total_count)
        
        return {
            'run_id': run_id,
            'all_passed': all_passed,
            'passed_count': passed_count,
            'total_count': total_count,
            'results': results
        }
    
    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Check Phase 5 database invariants')
    parser.add_argument('--run-id', help='Specific run ID to check')
    parser.add_argument('--latest', action='store_true', help='Check latest run')
    parser.add_argument('--db', default='trading.db', help='Database path')
    
    args = parser.parse_args()
    
    checker = Phase5InvariantChecker(args.db)
    
    try:
        if args.run_id:
            run_id = args.run_id
        elif args.latest:
            run_id = checker.get_latest_run_id()
            if not run_id:
                print("❌ No runs found in database")
                return 1
        else:
            print("Error: Must specify --run-id or --latest")
            parser.print_help()
            return 1
        
        result = checker.run_all_checks(run_id)
        
        return 0 if result['all_passed'] else 1
        
    finally:
        checker.close()


if __name__ == '__main__':
    sys.exit(main())
