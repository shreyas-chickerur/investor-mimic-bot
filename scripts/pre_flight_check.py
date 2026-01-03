#!/usr/bin/env python3
"""
Pre-flight check for automated morning runs.

Checks:
1. Market is open today (not weekend/holiday)
2. Data is reasonably fresh OR can be updated
3. All safety systems operational
4. Database accessible

Returns exit code 0 if safe to proceed, 1 if should skip.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from data_validator import DataValidator
from database import TradingDatabase


def check_market_open():
    """Check if market is open today."""
    # Use US Eastern Time (market time) instead of UTC
    import pytz
    eastern = pytz.timezone('America/New_York')
    now = datetime.now(eastern)
    weekday = now.weekday()
    
    # Weekend check
    if weekday >= 5:  # Saturday=5, Sunday=6
        print(f"⏸️  Market closed: Weekend ({now.strftime('%A')})")
        return False
    
    # Basic holiday check (major US holidays)
    holidays_2026 = [
        '2026-01-01',  # New Year's Day
        '2026-01-19',  # MLK Day
        '2026-02-16',  # Presidents Day
        '2026-04-03',  # Good Friday
        '2026-05-25',  # Memorial Day
        '2026-07-03',  # Independence Day (observed)
        '2026-09-07',  # Labor Day
        '2026-11-26',  # Thanksgiving
        '2026-12-25',  # Christmas
    ]
    
    today = now.strftime('%Y-%m-%d')
    if today in holidays_2026:
        print(f"⏸️  Market closed: Holiday ({today})")
        return False
    
    print(f"✅ Market open: {now.strftime('%A, %B %d, %Y')}")
    return True


def check_data_freshness():
    """Check if market data is fresh enough."""
    try:
        data_path = project_root / 'data' / 'training_data.csv'
        if not data_path.exists():
            print("❌ Data file not found")
            return False
        
        df = pd.read_csv(data_path)
        df['date'] = pd.to_datetime(df['date'])
        latest_date = df['date'].max()
        
        now = datetime.now()
        age_hours = (now - latest_date).total_seconds() / 3600
        age_days = age_hours / 24
        
        # Get threshold from environment (default 240 hours = 10 days to handle holiday periods)
        max_age_hours = int(os.getenv('DATA_VALIDATOR_MAX_AGE_HOURS', '240'))
        
        if age_hours <= max_age_hours:
            print(f"✅ Data fresh: {age_days:.1f} days old (latest: {latest_date.strftime('%Y-%m-%d')})")
            return True
        else:
            print(f"⚠️  Data stale: {age_days:.1f} days old (latest: {latest_date.strftime('%Y-%m-%d')})")
            print("   Attempting to update...")
            
            # Try to update data
            try:
                import subprocess
                result = subprocess.run(['python3', 'scripts/update_data.py'], 
                                      capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    raise Exception(f"Update failed: {result.stderr}")
                
                # Check if update succeeded
                df_new = pd.read_csv(data_path)
                df_new['date'] = pd.to_datetime(df_new['date'])
                new_latest = df_new['date'].max()
                
                if new_latest > latest_date:
                    print(f"✅ Data updated successfully (now: {new_latest.strftime('%Y-%m-%d')})")
                    return True
                else:
                    print("⚠️  Data update did not fetch newer data")
                    # Still allow if within 7 days (full week)
                    if age_hours <= 168:  # 7 days
                        print(f"   Proceeding with {age_days:.1f} day old data")
                        return True
                    else:
                        print("❌ Data too stale to proceed safely")
                        return False
                        
            except Exception as e:
                print(f"❌ Data update failed: {e}")
                # Allow if within 7 days even if update fails
                if age_hours <= 168:
                    print(f"   Proceeding with {age_days:.1f} day old data (update failed)")
                    return True
                else:
                    return False
                    
    except Exception as e:
        print(f"❌ Error checking data: {e}")
        return False


def check_database():
    """Check database is accessible."""
    try:
        db = TradingDatabase()
        # Try a simple query
        strategies = db.get_all_strategies()
        print(f"✅ Database accessible ({len(strategies)} strategies)")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False


def check_safety_systems():
    """Check safety systems are configured."""
    checks = []
    
    # Check DRY_RUN mode
    dry_run = os.getenv('DRY_RUN', 'false').lower()
    if dry_run == 'true':
        print("ℹ️  DRY_RUN mode: ENABLED (no broker writes)")
        checks.append(True)
    else:
        print("⚠️  DRY_RUN mode: DISABLED (live trading)")
        checks.append(True)
    
    # Check paper trading
    paper = os.getenv('ALPACA_PAPER', 'true').lower()
    if paper == 'true':
        print("✅ Paper trading: ENABLED")
        checks.append(True)
    else:
        print("⚠️  Paper trading: DISABLED (LIVE CAPITAL)")
        checks.append(True)
    
    # Check kill switches
    trading_disabled = os.getenv('TRADING_DISABLED', 'false').lower()
    if trading_disabled == 'true':
        print("⏸️  Global kill switch: ACTIVE (trading disabled)")
        checks.append(False)
    else:
        print("✅ Global kill switch: INACTIVE")
        checks.append(True)
    
    return all(checks)


def main():
    """Run all pre-flight checks."""
    print("=" * 80)
    print("PRE-FLIGHT CHECK - Automated Trading Run")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print()
    
    checks = {
        'Market Open': check_market_open(),
        'Data Fresh': check_data_freshness(),
        'Database': check_database(),
        'Safety Systems': check_safety_systems(),
    }
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    for name, passed in checks.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:20s} {status}")
    
    all_passed = all(checks.values())
    
    print()
    if all_passed:
        print("✅ ALL CHECKS PASSED - Safe to proceed with trading run")
        print("=" * 80)
        return 0
    else:
        print("❌ CHECKS FAILED - Skipping trading run")
        print("=" * 80)
        return 1


if __name__ == '__main__':
    sys.exit(main())
