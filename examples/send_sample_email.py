#!/usr/bin/env python3
"""
Send Sample Email with Mock Data

Generates and sends a sample email digest with realistic mock data
to demonstrate the email format and features.
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import json

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

# Create mock artifact data
mock_artifact = {
    "trades": {
        "placed": [
            {"action": "BUY", "symbol": "AAPL", "shares": 25, "price": 195.50, "strategy": "RSI Mean Reversion", "order_id": "abc123"},
            {"action": "BUY", "symbol": "MSFT", "shares": 18, "price": 378.25, "strategy": "ML Momentum", "order_id": "def456"},
            {"action": "SELL", "symbol": "GOOGL", "shares": 12, "price": 142.80, "strategy": "Volatility Breakout", "order_id": "ghi789"},
            {"action": "BUY", "symbol": "NVDA", "shares": 8, "price": 495.30, "strategy": "MA Crossover", "order_id": "jkl012"},
        ]
    },
    "positions": {
        "open": [
            {"symbol": "AAPL", "shares": 25, "entry_price": 195.50, "current_price": 197.20},
            {"symbol": "MSFT", "shares": 18, "entry_price": 378.25, "current_price": 380.50},
            {"symbol": "TSLA", "shares": 15, "entry_price": 245.80, "current_price": 248.30},
            {"symbol": "NVDA", "shares": 8, "entry_price": 495.30, "current_price": 498.75},
        ]
    },
    "risk": {
        "portfolio_value": 102450.75,
        "cash": 35280.50,
        "daily_pnl": 287.45,
        "portfolio_heat": 24.5
    },
    "regime": {
        "classification": "normal",
        "vix": 16.8
    },
    "system_health": {
        "reconciliation_status": "PASS",
        "reconciliation_discrepancies": [],
        "runtime_seconds": 12.3,
        "data_freshness": "2 hours",
        "error_count": 0,
        "warning_count": 0
    }
}

# Create mock strategy performance data (for database query simulation)
mock_strategy_perf = [
    {"strategy": "RSI Mean Reversion", "trades": 3, "wins": 2, "losses": 1, "total_pnl": 145.30, "avg_pnl": 48.43},
    {"strategy": "ML Momentum", "trades": 2, "wins": 2, "losses": 0, "total_pnl": 98.50, "avg_pnl": 49.25},
    {"strategy": "Volatility Breakout", "trades": 2, "wins": 1, "losses": 1, "total_pnl": 43.65, "avg_pnl": 21.83},
    {"strategy": "MA Crossover", "trades": 1, "wins": 0, "losses": 1, "total_pnl": -25.00, "avg_pnl": -25.00},
]

def create_mock_artifact():
    """Create mock artifact file"""
    artifact_dir = project_root / 'artifacts' / 'json'
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    date = datetime.now().strftime('%Y-%m-%d')
    artifact_path = artifact_dir / f'{date}.json'
    
    with open(artifact_path, 'w') as f:
        json.dump(mock_artifact, f, indent=2)
    
    return artifact_path

def mock_get_strategy_performance_today(db_path='trading.db'):
    """Mock function to return sample strategy performance"""
    return mock_strategy_perf

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Send sample email with mock data')
    parser.add_argument('--include-visuals', action='store_true', 
                       help='Include strategy performance charts (Mon/Wed/Fri style)')
    args = parser.parse_args()
    
    print("📧 Generating sample email with mock data...")
    
    # Create mock artifact
    artifact_path = create_mock_artifact()
    print(f"✓ Created mock artifact: {artifact_path}")
    
    # Import the email generation module
    sys.path.insert(0, str(project_root / 'scripts'))
    from generate_daily_email import generate_email_body, get_strategy_performance_today
    
    # Temporarily patch the strategy performance function
    import generate_daily_email as email_module
    original_func = email_module.get_strategy_performance_today
    email_module.get_strategy_performance_today = mock_get_strategy_performance_today
    
    try:
        # Generate email HTML
        html = generate_email_body(
            str(artifact_path), 
            db_path='trading.db',
            include_visuals=args.include_visuals
        )
        
        # Save to file
        output_path = '/tmp/sample_email.html'
        with open(output_path, 'w') as f:
            f.write(html)
        
        visual_status = "with visuals" if args.include_visuals else "standard"
        print(f"✓ Generated email HTML ({visual_status}): {output_path}")
        print(f"\n📊 Sample Email Summary:")
        print(f"   Portfolio Value: ${mock_artifact['risk']['portfolio_value']:,.2f}")
        print(f"   Daily P&L: ${mock_artifact['risk']['daily_pnl']:+.2f}")
        print(f"   Trades: {len(mock_artifact['trades']['placed'])}")
        print(f"   Positions: {len(mock_artifact['positions']['open'])}")
        print(f"   Top Strategy: RSI Mean Reversion (+$145.30)")
        print(f"\n✅ Sample email generated successfully!")
        print(f"   Open {output_path} in a browser to view")
        
    finally:
        # Restore original function
        email_module.get_strategy_performance_today = original_func
    
    sys.exit(0)
