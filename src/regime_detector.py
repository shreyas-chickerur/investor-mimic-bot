#!/usr/bin/env python3
"""
Regime Detection System
Detects market regimes to enable/disable strategies appropriately
"""
import logging
from typing import Dict, Tuple
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)

class RegimeDetector:
    """Detects market regime (trend/chop, high/low volatility)"""
    
    def __init__(self, 
                 vix_low_threshold: float = 15.0,
                 vix_high_threshold: float = 25.0,
                 trend_lookback: int = 50):
        """
        Initialize regime detector
        
        Args:
            vix_low_threshold: VIX below this = low volatility regime
            vix_high_threshold: VIX above this = high volatility regime
            trend_lookback: Days to look back for trend detection
        """
        self.vix_low = vix_low_threshold
        self.vix_high = vix_high_threshold
        self.trend_lookback = trend_lookback
        
        logger.info(f"Regime Detector: VIX low={vix_low_threshold}, high={vix_high_threshold}")
    
    def get_vix_level(self) -> float:
        """
        Get current VIX level
        
        Fetches from VIX data source if available, otherwise returns default
        """
        try:
            from vix_data_fetcher import VIXDataFetcher
            fetcher = VIXDataFetcher(source='yahoo')
            vix = fetcher.get_current_vix()
            return vix
        except Exception as e:
            logger.warning(f"Could not fetch VIX, using default: {e}")
            # Return moderate volatility as fallback
            return 18.0
    
    def detect_volatility_regime(self, vix: float = None) -> str:
        """
        Detect volatility regime based on VIX
        
        Returns:
            'low_volatility', 'normal', or 'high_volatility'
        """
        if vix is None:
            vix = self.get_vix_level()
        
        if vix < self.vix_low:
            regime = 'low_volatility'
        elif vix > self.vix_high:
            regime = 'high_volatility'
        else:
            regime = 'normal'
        
        logger.info(f"Volatility regime: {regime} (VIX: {vix:.2f})")
        return regime
    
    def detect_trend_regime(self, market_data: pd.DataFrame) -> str:
        """
        Detect trend regime (trending vs choppy)
        
        Uses SPY 200-day MA as proxy for market trend
        
        Returns:
            'strong_trend', 'weak_trend', or 'choppy'
        """
        # In production, would use SPY data
        # For now, return neutral
        return 'weak_trend'
    
    def get_regime_adjustments(self, vix: float = None) -> Dict:
        """
        Get regime-based adjustments for system parameters
        
        Returns:
            Dict with adjusted parameters based on regime
        """
        vol_regime = self.detect_volatility_regime(vix)
        
        adjustments = {
            'volatility_regime': vol_regime,
            'max_portfolio_heat': 0.30,  # Default
            'enable_mean_reversion': True,
            'enable_breakout': True,
            'enable_trend_following': True,
            'position_size_multiplier': 1.0
        }
        
        # Adjust based on volatility regime
        if vol_regime == 'low_volatility':
            adjustments['max_portfolio_heat'] = 0.40  # Allow more exposure
            adjustments['position_size_multiplier'] = 1.2  # Larger positions
            logger.info("Low volatility: Increasing heat to 40%, position size +20%")
            
        elif vol_regime == 'high_volatility':
            adjustments['max_portfolio_heat'] = 0.20  # Reduce exposure
            adjustments['position_size_multiplier'] = 0.8  # Smaller positions
            adjustments['enable_breakout'] = False  # Disable breakout strategies
            logger.info("High volatility: Reducing heat to 20%, position size -20%, disabling breakouts")
        
        return adjustments
    
    def should_enable_strategy(self, strategy_name: str, regime_adjustments: Dict) -> bool:
        """
        Determine if a strategy should be enabled based on regime
        
        Args:
            strategy_name: Name of the strategy
            regime_adjustments: Current regime adjustments
            
        Returns:
            True if strategy should run, False otherwise
        """
        strategy_lower = strategy_name.lower()
        
        # Mean reversion strategies
        if 'rsi' in strategy_lower or 'mean reversion' in strategy_lower:
            enabled = regime_adjustments['enable_mean_reversion']
            if not enabled:
                logger.info(f"Disabling {strategy_name} due to regime")
            return enabled
        
        # Breakout strategies
        if 'breakout' in strategy_lower or 'volatility breakout' in strategy_lower:
            enabled = regime_adjustments['enable_breakout']
            if not enabled:
                logger.info(f"Disabling {strategy_name} due to regime")
            return enabled
        
        # Trend following strategies
        if 'ma' in strategy_lower or 'crossover' in strategy_lower:
            enabled = regime_adjustments['enable_trend_following']
            if not enabled:
                logger.info(f"Disabling {strategy_name} due to regime")
            return enabled
        
        # Other strategies always enabled
        return True
    
    def get_status(self) -> Dict:
        """Get current regime status"""
        vix = self.get_vix_level()
        vol_regime = self.detect_volatility_regime(vix)
        adjustments = self.get_regime_adjustments(vix)
        
        return {
            'vix': vix,
            'volatility_regime': vol_regime,
            'adjustments': adjustments
        }
