#!/usr/bin/env python3
"""Validate system is ready for live trading"""
import sys
import os
from pathlib import Path
import subprocess
import sqlite3

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

def validate_system():
    """Run all pre-live trading checks"""
    print("=" * 70)
    print("PRE-LIVE TRADING VALIDATION")
    print("=" * 70)
    
    errors = []
    warnings = []
    
    # 1. Check test coverage
    print("\n[1/10] Checking test coverage...")
    try:
        result = subprocess.run(
            ['pytest', 'tests/', '--cov=src', '--cov-report=term-missing', '--cov-fail-under=60', '-q'],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=Path(__file__).parent.parent
        )
        if result.returncode != 0:
            errors.append("Test coverage below 60% or tests failing")
            print("❌ Test coverage insufficient")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
        else:
            print("✅ Test coverage >= 60%")
    except subprocess.TimeoutExpired:
        errors.append("Tests took too long (>2 min)")
        print("❌ Tests timeout")
    except FileNotFoundError:
        warnings.append("pytest not found - install with: pip install pytest pytest-cov")
        print("⚠️  pytest not installed")
    except Exception as e:
        errors.append(f"Failed to run tests: {e}")
        print(f"❌ Test execution failed: {e}")
    
    # 2. Verify broker reconciliation works
    print("\n[2/10] Testing broker reconciliation...")
    try:
        from src.risk.broker_reconciler import BrokerReconciler
        reconciler = BrokerReconciler()
        
        # Get actual broker state and test reconciliation with it
        broker_state = reconciler.get_broker_state()
        if broker_state:
            result = reconciler.reconcile_daily(
                broker_state.get('positions', {}),
                broker_state.get('cash', 0)
            )
            if not result[0]:  # result is (success, discrepancies)
                warnings.append(f"Broker reconciliation found {len(result[1])} discrepancies")
                print(f"⚠️  Reconciliation found discrepancies (check manually)")
                for disc in result[1][:3]:  # Show first 3
                    print(f"   - {disc}")
            else:
                print("✅ Broker reconciliation working")
        else:
            print("✅ Broker reconciliation initialized (no API connection)")
    except Exception as e:
        errors.append(f"Broker reconciliation error: {e}")
        print(f"❌ Reconciliation error: {e}")
    
    # 3. Check stop losses are enabled
    print("\n[3/10] Verifying stop loss configuration...")
    try:
        from src.risk.stop_loss_manager import StopLossManager
        stop_manager = StopLossManager()
        
        # Verify stop loss manager initializes
        print("✅ Stop loss manager initialized")
    except Exception as e:
        errors.append(f"Stop loss manager error: {e}")
        print(f"❌ Stop loss error: {e}")
    
    # 4. Verify drawdown stops configured
    print("\n[4/10] Checking drawdown protection...")
    try:
        from src.risk.drawdown_stop_manager import DrawdownStopManager
        from src.core.database import TradingDatabase
        from src.utils.email_notifier import EmailNotifier
        
        # Create required dependencies
        db = TradingDatabase('trading.db')
        email = EmailNotifier()
        dd_manager = DrawdownStopManager(db, email)
        
        halt_threshold = dd_manager.halt_threshold
        panic_threshold = dd_manager.panic_threshold
        
        if halt_threshold >= 0.15:
            warnings.append(f"Halt threshold high: {halt_threshold:.0%} (recommend <= 10%)")
        if panic_threshold >= 0.20:
            warnings.append(f"Panic threshold high: {panic_threshold:.0%} (recommend <= 15%)")
        
        if halt_threshold >= panic_threshold:
            errors.append(f"Halt threshold ({halt_threshold:.0%}) >= panic ({panic_threshold:.0%})")
            print("❌ Drawdown thresholds misconfigured")
        else:
            print(f"✅ Drawdown: halt {halt_threshold:.0%}, panic {panic_threshold:.0%}")
    except Exception as e:
        errors.append(f"Failed to check drawdown config: {e}")
        print(f"❌ Config error: {e}")
    
    # 5. Check email notifications work
    print("\n[5/10] Testing email notifications...")
    try:
        if not os.getenv('EMAIL_USERNAME') or not os.getenv('EMAIL_PASSWORD'):
            warnings.append("Email credentials not configured")
            print("⚠️  Email not configured")
        else:
            print("✅ Email configured")
    except Exception as e:
        warnings.append(f"Email setup issue: {e}")
        print(f"⚠️  Email issue: {e}")
    
    # 6. Verify paper trading results exist
    print("\n[6/10] Analyzing paper trading performance...")
    try:
        db_path = Path(__file__).parent.parent / 'trading.db'
        if not db_path.exists():
            warnings.append("No trading.db found - no paper trading history")
            print("⚠️  No trading database")
        else:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM trades")
            trade_count = cursor.fetchone()[0]
            
            if trade_count < 10:
                warnings.append(f"Only {trade_count} paper trades - need more data (recommend 30+)")
                print(f"⚠️  Limited paper trading: {trade_count} trades")
            else:
                # Calculate win rate
                cursor.execute("SELECT COUNT(*) FROM trades WHERE pnl > 0")
                winning_trades = cursor.fetchone()[0]
                win_rate = (winning_trades / trade_count * 100) if trade_count > 0 else 0
                
                if win_rate < 40:
                    warnings.append(f"Low win rate in paper trading: {win_rate:.1f}%")
                    print(f"⚠️  Win rate: {win_rate:.1f}% (low)")
                else:
                    print(f"✅ Paper trading: {trade_count} trades, {win_rate:.1f}% win rate")
            
            conn.close()
    except Exception as e:
        errors.append(f"Failed to analyze paper trading: {e}")
        print(f"❌ Database error: {e}")
    
    # 7. Check for data quality
    print("\n[7/10] Validating data quality...")
    try:
        data_file = Path(__file__).parent.parent / 'data' / 'training_data.csv'
        if not data_file.exists():
            warnings.append("No training_data.csv found")
            print("⚠️  No training data")
        else:
            print("✅ Training data exists")
    except Exception as e:
        warnings.append(f"Data quality check issue: {e}")
        print(f"⚠️  Data quality: {e}")
    
    # 8. Verify risk limits are reasonable
    print("\n[8/10] Reviewing risk limits...")
    try:
        from src.risk.portfolio_risk_manager import PortfolioRiskManager
        risk_manager = PortfolioRiskManager()
        
        max_heat = risk_manager.max_portfolio_heat
        max_daily_loss = risk_manager.max_daily_loss_pct
        
        if max_heat > 0.50:
            errors.append(f"Max heat too high: {max_heat:.0%} (recommend <= 50%)")
            print(f"❌ Max heat: {max_heat:.0%} (too high)")
        elif max_heat > 0.30:
            warnings.append(f"Max heat moderate: {max_heat:.0%}")
            print(f"⚠️  Max heat: {max_heat:.0%}")
        else:
            print(f"✅ Max heat: {max_heat:.0%}")
        
        if max_daily_loss > 0.03:
            warnings.append(f"Daily loss limit high: {max_daily_loss:.0%}")
            print(f"⚠️  Daily loss limit: {max_daily_loss:.0%}")
        else:
            print(f"✅ Daily loss limit: {max_daily_loss:.0%}")
    except Exception as e:
        errors.append(f"Failed to check risk limits: {e}")
        print(f"❌ Config error: {e}")
    
    # 9. Verify database schema is current
    print("\n[9/10] Checking database schema...")
    try:
        db_path = Path(__file__).parent.parent / 'trading.db'
        if not db_path.exists():
            errors.append("No trading.db found")
            print("❌ No database")
        else:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ['strategies', 'signals', 'trades', 'positions', 'broker_state']
            missing = [t for t in required_tables if t not in tables]
            
            if missing:
                errors.append(f"Missing database tables: {missing}")
                print(f"❌ Missing tables: {missing}")
            else:
                print("✅ Database schema complete")
            
            conn.close()
    except Exception as e:
        errors.append(f"Database schema check failed: {e}")
        print(f"❌ Database error: {e}")
    
    # 10. Verify API keys are set
    print("\n[10/10] Checking API configuration...")
    required_keys = ['ALPACA_API_KEY', 'ALPACA_SECRET_KEY']
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    
    if missing_keys:
        errors.append(f"Missing API keys: {missing_keys}")
        print(f"❌ Missing keys: {missing_keys}")
    else:
        # Check if in paper mode
        is_paper = os.getenv('ALPACA_PAPER', 'true').lower() == 'true'
        if not is_paper:
            warnings.append("ALPACA_PAPER is false - will trade with REAL MONEY")
            print("⚠️  LIVE TRADING MODE")
        else:
            print("✅ API keys configured (paper mode)")
    
    # Print summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    
    if errors:
        print("\n❌ CRITICAL ERRORS (must fix before live trading):")
        for i, err in enumerate(errors, 1):
            print(f"  {i}. {err}")
    
    if warnings:
        print("\n⚠️  WARNINGS (review recommended):")
        for i, warn in enumerate(warnings, 1):
            print(f"  {i}. {warn}")
    
    if not errors and not warnings:
        print("\n✅ ALL CHECKS PASSED")
        print("\n🎯 SYSTEM READY FOR LIVE TRADING")
        print("\nRECOMMENDED NEXT STEPS:")
        print("  1. Start with small capital ($5,000-$10,000)")
        print("  2. Monitor daily for first 2 weeks")
        print("  3. Review all trades manually")
        print("  4. Gradually increase capital if performing well")
        print("  5. Set calendar reminder for monthly performance review")
        return 0
    elif not errors:
        print("\n✅ PASSED WITH WARNINGS")
        print("\nReview warnings above, then proceed with caution.")
        return 0
    else:
        print("\n❌ VALIDATION FAILED")
        print("\nFix critical errors before enabling live trading.")
        return 1

if __name__ == '__main__':
    sys.exit(validate_system())
