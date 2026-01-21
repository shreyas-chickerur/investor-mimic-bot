#!/usr/bin/env python3
"""Verify that all imports work after reorganization"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test all critical imports"""
    errors = []
    success = []
    
    # Test core imports
    try:
        from src.core.database import TradingDatabase
        from src.core.execution_engine import ExecutionEngine
        from src.core.strategy_base import StrategyBase
        success.append("✅ Core imports")
    except Exception as e:
        errors.append(f"❌ Core imports: {e}")
    
    # Test risk imports
    try:
        from src.risk.portfolio_risk_manager import PortfolioRiskManager
        from src.risk.drawdown_stop_manager import DrawdownStopManager
        from src.risk.stop_loss_manager import StopLossManager
        from src.risk.correlation_filter import CorrelationFilter
        from src.risk.broker_reconciler import BrokerReconciler
        success.append("✅ Risk imports")
    except Exception as e:
        errors.append(f"❌ Risk imports: {e}")
    
    # Test regime imports
    try:
        from src.regime.regime_detector import RegimeDetector
        from src.regime.dynamic_allocator import DynamicAllocator
        success.append("✅ Regime imports")
    except Exception as e:
        errors.append(f"❌ Regime imports: {e}")
    
    # Test data imports
    try:
        from src.data.alpaca_data_fetcher import AlpacaDataFetcher
        from src.data.alpha_vantage_fetcher import AlphaVantageFetcher
        from src.data.vix_data_fetcher import VIXDataFetcher
        from src.data.data_validator import DataValidator
        from src.data.universe_provider import UniverseProvider
        success.append("✅ Data imports")
    except Exception as e:
        errors.append(f"❌ Data imports: {e}")
    
    # Test monitoring imports
    try:
        from src.monitoring.pnl_calculator import PnLCalculator
        from src.monitoring.signal_funnel_tracker import SignalFunnelTracker
        from src.monitoring.strategy_health_scorer import StrategyHealthScorer
        success.append("✅ Monitoring imports")
    except Exception as e:
        errors.append(f"❌ Monitoring imports: {e}")
    
    # Test integration imports
    try:
        from src.integration.dry_run_executor import DryRunExecutor
        from src.integration.portfolio_backtester import PortfolioBacktester
        from src.integration.strategy_runner import StrategyRunner
        from src.integration.cash_manager import CashManager
        success.append("✅ Integration imports")
    except Exception as e:
        errors.append(f"❌ Integration imports: {e}")
    
    # Test utils imports
    try:
        from src.utils.config import TradingConfig
        from src.utils.logger import setup_logger
        from src.utils.email_notifier import EmailNotifier
        from src.utils.execution_costs import ExecutionCostModel
        success.append("✅ Utils imports")
    except Exception as e:
        errors.append(f"❌ Utils imports: {e}")
    
    # Test strategy imports
    try:
        from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
        from src.strategies.strategy_ma_crossover import MACrossoverStrategy
        from src.strategies.strategy_ml_momentum import MLMomentumStrategy
        success.append("✅ Strategy imports")
    except Exception as e:
        errors.append(f"❌ Strategy imports: {e}")
    
    # Print results
    print("\n" + "="*60)
    print("REORGANIZATION VERIFICATION RESULTS")
    print("="*60 + "\n")
    
    for msg in success:
        print(msg)
    
    if errors:
        print()
        for msg in errors:
            print(msg)
        print(f"\n❌ FAILED: {len(errors)} import groups failed")
        return False
    else:
        print(f"\n✅ SUCCESS: All {len(success)} import groups working")
        return True

if __name__ == '__main__':
    success = test_imports()
    sys.exit(0 if success else 1)
