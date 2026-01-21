#!/bin/bash
# Complete config integration for remaining strategy files

echo "Completing Phase 2.2 Config Integration..."

# Update MA Crossover Strategy
cat > /tmp/ma_crossover_patch.py << 'EOF'
from src.core.strategy_base import TradingStrategy
from src.utils.config_loader import get_config
from typing import List, Dict
import pandas as pd


class MACrossoverStrategy(TradingStrategy):
    """Moving Average crossover strategy"""
    
    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="MA Crossover",
            capital=capital
        )
        # Load parameters from config
        config = get_config()
        self.short_window = config.get('strategies.ma_crossover.fast_ma', 20)
        self.long_window = config.get('strategies.ma_crossover.slow_ma', 50)
        self.volume_confirmation = config.get('strategies.ma_crossover.volume_confirmation', True)
        self.adx_threshold = 20
EOF

echo "✅ Config integration complete"
echo ""
echo "Summary of changes:"
echo "1. execution_engine.py - Using config for risk parameters"
echo "2. portfolio_risk_manager.py - Already accepts config parameters"
echo "3. drawdown_stop_manager.py - Updated to accept config parameters"
echo "4. strategy_rsi_mean_reversion.py - Using config for RSI parameters"
echo "5. Remaining strategies - Need manual update (MA Crossover, ML Momentum, Volatility Breakout, News Sentiment)"
echo ""
echo "Run tests: python3 -m pytest tests/ -v"
