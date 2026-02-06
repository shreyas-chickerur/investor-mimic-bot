#!/usr/bin/env python3
"""Update all imports to use absolute imports after reorganization"""
import os
import re
from pathlib import Path

# Mapping of old imports to new imports
IMPORT_MAPPINGS = {
    # Core
    'from database import': 'from src.core.database import',
    'import database': 'import src.core.database as database',
    'from execution_engine import': 'from src.core.execution_engine import',
    'from strategy_base import': 'from src.core.strategy_base import',
    'from trading_system import': 'from src.core.trading_system import',
    
    # Risk
    'from portfolio_risk_manager import': 'from src.risk.portfolio_risk_manager import',
    'from drawdown_stop_manager import': 'from src.risk.drawdown_stop_manager import',
    'from stop_loss_manager import': 'from src.risk.stop_loss_manager import',
    'from correlation_filter import': 'from src.risk.correlation_filter import',
    'from broker_reconciler import': 'from src.risk.broker_reconciler import',
    
    # Regime
    'from regime_detector import': 'from src.regime.regime_detector import',
    'from dynamic_allocator import': 'from src.regime.dynamic_allocator import',
    
    # Data
    'from alpaca_data_fetcher import': 'from src.data.alpaca_data_fetcher import',
    'from alpha_vantage_fetcher import': 'from src.data.alpha_vantage_fetcher import',
    'from vix_data_fetcher import': 'from src.data.vix_data_fetcher import',
    'from data_validator import': 'from src.data.data_validator import',
    'from data_quality_checker import': 'from src.data.data_quality_checker import',
    'from universe_provider import': 'from src.data.universe_provider import',
    
    # Monitoring
    'from performance_metrics import': 'from src.monitoring.performance_metrics import',
    'from pnl_calculator import': 'from src.monitoring.pnl_calculator import',
    'from signal_funnel_tracker import': 'from src.monitoring.signal_funnel_tracker import',
    'from strategy_health_scorer import': 'from src.monitoring.strategy_health_scorer import',
    'from artifact_writer import': 'from src.monitoring.artifact_writer import',
    'from dashboard_server import': 'from src.monitoring.dashboard_server import',
    'from strategy_dashboard import': 'from src.monitoring.strategy_dashboard import',
    
    # Integration
    'from trade_executor import': 'from src.integration.trade_executor import',
    'from dry_run_executor import': 'from src.integration.dry_run_executor import',
    'from dry_run_wrapper import': 'from src.integration.dry_run_wrapper import',
    'from backtesting_framework import': 'from src.integration.backtesting_framework import',
    'from portfolio_backtester import': 'from src.integration.portfolio_backtester import',
    'from strategy_runner import': 'from src.integration.strategy_runner import',
    'from strategy_database import': 'from src.integration.strategy_database import',
    'from pending_signals_manager import': 'from src.integration.pending_signals_manager import',
    'from cash_manager import': 'from src.integration.cash_manager import',
    
    # Utils
    'from config import': 'from src.utils.config import',
    'from config_typed import': 'from src.utils.config_typed import',
    'from logger import': 'from src.utils.logger import',
    'from structured_logger import': 'from src.utils.structured_logger import',
    'from email_notifier import': 'from src.utils.email_notifier import',
    'from security import': 'from src.utils.security import',
    'from execution_costs import': 'from src.utils.execution_costs import',
    'from kill_switch_service import': 'from src.utils.kill_switch_service import',
    'from alerting import': 'from src.utils.alerting import',
    'from signal_flow_tracer import': 'from src.utils.signal_flow_tracer import',
    'from signal_tracer import': 'from src.utils.signal_tracer import',
    'from signal_injection_engine import': 'from src.utils.signal_injection_engine import',
    'from window_boundary_guardrail import': 'from src.utils.window_boundary_guardrail import',
    'from news_sentiment import': 'from src.utils.news_sentiment import',
}

def update_file_imports(filepath):
    """Update imports in a single file"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Apply all mappings
        for old_import, new_import in IMPORT_MAPPINGS.items():
            content = content.replace(old_import, new_import)
        
        # Only write if changed
        if content != original_content:
            with open(filepath, 'w') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error updating {filepath}: {e}")
        return False

def main():
    """Update all Python files"""
    root = Path(__file__).parent.parent
    updated_count = 0
    
    # Update all Python files in src/
    for filepath in root.glob('src/**/*.py'):
        if update_file_imports(filepath):
            print(f"Updated: {filepath.relative_to(root)}")
            updated_count += 1
    
    # Update all Python files in tests/
    for filepath in root.glob('tests/**/*.py'):
        if update_file_imports(filepath):
            print(f"Updated: {filepath.relative_to(root)}")
            updated_count += 1
    
    # Update all Python files in scripts/
    for filepath in root.glob('scripts/**/*.py'):
        if filepath.name != 'update_imports.py':  # Skip self
            if update_file_imports(filepath):
                print(f"Updated: {filepath.relative_to(root)}")
                updated_count += 1
    
    print(f"\nTotal files updated: {updated_count}")

if __name__ == '__main__':
    main()
