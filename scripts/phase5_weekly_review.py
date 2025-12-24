#!/usr/bin/env python3
"""
Phase 5 Weekly Review Script

Analyzes the last 7 days of Phase 5 execution and generates a summary report.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import json
from datetime import datetime, timedelta


def main():
    print('='*80)
    print('PHASE 5 WEEKLY REVIEW')
    print('='*80)
    
    # Analyze last 7 days
    days_data = []
    
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        json_path = Path(f'artifacts/json/{date}.json')
        
        if json_path.exists():
            with open(json_path) as f:
                data = json.load(f)
            
            recon_status = data.get('reconciliation_status', 'UNKNOWN')
            recon_discrep = len(data.get('reconciliation_discrepancies', []))
            signals_gen = len(data.get('generated_signals', []))
            signals_exec = len(data.get('executed_signals', []))
            signals_rej = len(data.get('rejected_signals', []))
            trades = len(data.get('filled_orders', []))
            
            passed = 'PASS' in recon_status and recon_discrep == 0
            
            days_data.append({
                'date': date,
                'passed': passed,
                'recon_status': recon_status,
                'discrepancies': recon_discrep,
                'signals_generated': signals_gen,
                'signals_executed': signals_exec,
                'signals_rejected': signals_rej,
                'trades': trades
            })
            
            status = '✅' if passed else '❌'
            print(f'{date}: {status} Recon, {signals_gen} signals, {trades} trades')
    
    if not days_data:
        print('\n⚠️  No artifacts found for the last 7 days')
        return False
    
    # Calculate summary statistics
    days_checked = len(days_data)
    days_passed = sum(1 for d in days_data if d['passed'])
    success_rate = days_passed / days_checked * 100
    total_trades = sum(d['trades'] for d in days_data)
    total_signals = sum(d['signals_generated'] for d in days_data)
    
    print(f'\n{'='*80}')
    print('WEEK SUMMARY')
    print(f'{'='*80}')
    print(f'Days checked: {days_checked}')
    print(f'Days passed: {days_passed}')
    print(f'Success rate: {success_rate:.1f}%')
    print(f'Total signals: {total_signals}')
    print(f'Total trades: {total_trades}')
    
    # Check for issues
    failed_days = [d for d in days_data if not d['passed']]
    if failed_days:
        print(f'\n⚠️  FAILED DAYS:')
        for day in failed_days:
            print(f"  {day['date']}: {day['recon_status']}, {day['discrepancies']} discrepancies")
    
    # Phase 5 requirement
    print(f'\n{'='*80}')
    if success_rate == 100.0:
        print('✅ Week meets Phase 5 requirements (100% success)')
    else:
        print(f'❌ Week does NOT meet Phase 5 requirements')
        print(f'   Required: 100% success rate')
        print(f'   Actual: {success_rate:.1f}%')
    
    print(f'{'='*80}')
    
    return success_rate == 100.0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
