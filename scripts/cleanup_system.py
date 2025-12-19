#!/usr/bin/env python3
"""
System Cleanup Script

Removes unused files and consolidates the codebase.
"""

import os
import shutil
from pathlib import Path

def cleanup():
    """Remove unused files and directories."""
    
    base_dir = Path(__file__).parent.parent
    
    # Files to remove
    files_to_remove = [
        'SYSTEM_COMPLETE.md',
        'FINAL_REAL_DATA_RESULTS.md',
        'DEPLOYMENT_READY.md',
        'COMPREHENSIVE_TEST_REPORT.md',
        'RESILIENT_SYSTEM_SUMMARY.md',
        'TEST_RESULTS.md',
    ]
    
    # Directories to remove
    dirs_to_remove = [
        'historical_data',
        'historical_data_real',
        'backtest_results',
        'optimization_results',
    ]
    
    # Remove files
    for file in files_to_remove:
        filepath = base_dir / file
        if filepath.exists():
            filepath.unlink()
            print(f"Removed: {file}")
    
    # Remove directories
    for dir_name in dirs_to_remove:
        dirpath = base_dir / dir_name
        if dirpath.exists():
            shutil.rmtree(dirpath)
            print(f"Removed directory: {dir_name}")
    
    # Remove redundant backtest scripts
    backtest_scripts = [
        'backtesting/run_simple_backtest.py',
        'backtesting/run_ultra_optimized_backtest.py',
        'backtesting/run_real_data_backtest.py',
        'backtesting/run_improved_real_backtest.py',
        'backtesting/run_balanced_real_backtest.py',
    ]
    
    for script in backtest_scripts:
        filepath = base_dir / script
        if filepath.exists():
            filepath.unlink()
            print(f"Removed: {script}")
    
    # Remove redundant data collection scripts
    data_scripts = [
        'scripts/generate_synthetic_backtest_data.py',
        'scripts/collect_real_historical_data.py',
        'scripts/fetch_real_data_simple.py',
        'scripts/fetch_alpaca_historical_data.py',
    ]
    
    for script in data_scripts:
        filepath = base_dir / script
        if filepath.exists():
            filepath.unlink()
            print(f"Removed: {script}")
    
    print("\n✓ Cleanup complete!")

if __name__ == "__main__":
    cleanup()
