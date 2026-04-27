#!/usr/bin/env python3
"""
Regime Detection System
Detects market regimes to enable/disable strategies appropriately
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

try:
    from hmmlearn import hmm as _hmm_lib
    _HMM_AVAILABLE = True
except (ImportError, OSError):  # OSError covers missing shared libs on macOS
    _HMM_AVAILABLE = False

logger = logging.getLogger(__name__)

# Lazy-import to avoid circular deps and keep startup fast
def _get_vix_fetcher():
    try:
        from src.data.vix_data_fetcher import VIXDataFetcher
        return VIXDataFetcher(source='yahoo')
    except Exception:
        return None

class RegimeDetector:
    """Detects market regime (trend/chop, high/low volatility)"""
    
    def __init__(self, 
                 vix_low_threshold: float = 15.0,
                 vix_high_threshold: float = 25.0,
                 trend_lookback: int = 50,
                 vol_low_threshold: float = 0.15,
                 vol_high_threshold: float = 0.25):
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
        self.vol_low_threshold = vol_low_threshold
        self.vol_high_threshold = vol_high_threshold
        
        self._hmm_cache: Optional[Tuple[str, str]] = None  # (date_str, regime)
        logger.info(f"Regime Detector: VIX low={vix_low_threshold}, high={vix_high_threshold}, "
                    f"HMM={'enabled' if _HMM_AVAILABLE else 'unavailable (pip install hmmlearn)'}")
    
    def get_vix_level(self, market_data=None) -> float:
        """Get VIX level.

        Primary: live ^VIX from Yahoo Finance via VIXDataFetcher (free, no key).
        Fallback: 20-day annualized realized volatility of the market proxy.
        Final fallback: 18.0 (moderate regime default).
        """
        # 1. Try real VIX first
        try:
            fetcher = _get_vix_fetcher()
            if fetcher is not None:
                vix = fetcher.get_current_vix()
                if 5.0 <= vix <= 80.0:
                    logger.info(f"VIX (live ^VIX): {vix:.1f}")
                    return round(vix, 1)
        except Exception as exc:
            logger.warning(f"Live VIX fetch failed, using realized-vol proxy: {exc}")

        # 2. Realized-vol proxy from market data
        if market_data is not None and not market_data.empty:
            try:
                proxy = self._get_market_proxy(market_data)
                if len(proxy) >= 21:
                    returns = proxy.pct_change().dropna().tail(20)
                    realized_vol = returns.std() * (252 ** 0.5) * 100
                    if 5.0 <= realized_vol <= 80.0:
                        logger.info(f"VIX proxy (realized vol): {realized_vol:.1f}")
                        return round(realized_vol, 1)
            except Exception as exc:
                logger.warning(f"Could not calculate VIX proxy: {exc}")

        return 18.0

    def _get_market_proxy(self, market_data: pd.DataFrame) -> pd.Series:
        """Build a market proxy series from available symbols."""
        if market_data is None or market_data.empty:
            return pd.Series(dtype=float)

        if 'symbol' in market_data.columns:
            return market_data.groupby(market_data.index)['close'].mean()

        return market_data['close']
    
    def detect_volatility_regime(self, vix: float = None, market_data: pd.DataFrame = None) -> str:
        """
        Detect volatility regime based on VIX
        
        Returns:
            'low_volatility', 'normal', or 'high_volatility'
        """
        if vix is None:
            if market_data is not None:
                proxy = self._get_market_proxy(market_data)
                if len(proxy) > 20:
                    returns = proxy.pct_change().dropna()
                    if len(returns) > 0:
                        realized_vol = returns.std() * (252 ** 0.5)
                        if realized_vol < self.vol_low_threshold:
                            regime = 'low_volatility'
                        elif realized_vol > self.vol_high_threshold:
                            regime = 'high_volatility'
                        else:
                            regime = 'normal'
                        logger.info(f"Volatility regime: {regime} (realized vol: {realized_vol:.2f})")
                        return regime
            vix = self.get_vix_level()
        
        if vix < self.vix_low:
            regime = 'low_volatility'
        elif vix > self.vix_high:
            regime = 'high_volatility'
        else:
            regime = 'normal'
        
        logger.info(f"Volatility regime: {regime} (VIX: {vix:.2f})")
        return regime
    
    def detect_hmm_regime(self, market_data: pd.DataFrame) -> str:
        """Fit a 2-state Gaussian HMM on SPY returns + realized vol.

        Returns 'bull', 'bear', or 'unknown'.
        Bull state = higher mean return. Bear state = lower/negative mean return.
        Only refits when date changes (cached intraday).
        """
        today_str = str(pd.Timestamp.today().date())
        if self._hmm_cache and self._hmm_cache[0] == today_str:
            return self._hmm_cache[1]  # cache hit: skip refitting

        if not _HMM_AVAILABLE or market_data is None or market_data.empty:
            return 'unknown'

        try:
            spy = (
                market_data[market_data['symbol'] == 'SPY']['close']
                if 'symbol' in market_data.columns
                else market_data['close']
            )
            if len(spy) < 60:
                return 'unknown'

            rets = spy.pct_change().dropna()
            vol = rets.rolling(20).std().dropna()
            aligned_rets = rets.reindex(vol.index)
            X = np.column_stack([aligned_rets.values, vol.values])

            model = _hmm_lib.GaussianHMM(
                n_components=2, covariance_type='full',
                n_iter=100, random_state=42
            )
            model.fit(X)
            states = model.predict(X)

            # Bull state = whichever component has the higher mean return
            mean_returns = [X[states == s, 0].mean() for s in range(2)]
            bull_state = int(np.argmax(mean_returns))
            regime = 'bull' if states[-1] == bull_state else 'bear'

            self._hmm_cache = (today_str, regime)
            logger.info(f"HMM regime: {regime} (bull_state={bull_state}, "
                        f"mean_rets=[{mean_returns[0]:.4f}, {mean_returns[1]:.4f}])")
            return regime

        except Exception as exc:
            logger.warning(f"HMM regime detection failed: {exc}")
            return 'unknown'

    def detect_trend_regime(self, market_data: pd.DataFrame) -> str:
        """
        Detect trend regime (trending vs choppy)
        
        Uses SPY 200-day MA as proxy for market trend
        
        Returns:
            'strong_trend', 'weak_trend', or 'choppy'
        """
        proxy = self._get_market_proxy(market_data)
        if len(proxy) < 200:
            return 'weak_trend'

        short_ma = proxy.rolling(window=50).mean().iloc[-1]
        long_ma = proxy.rolling(window=200).mean().iloc[-1]
        if long_ma == 0 or pd.isna(short_ma) or pd.isna(long_ma):
            return 'weak_trend'

        trend_strength = (short_ma - long_ma) / long_ma
        if trend_strength > 0.02:
            return 'strong_trend'
        if abs(trend_strength) < 0.01:
            return 'choppy'
        return 'weak_trend'
    
    def get_regime_adjustments(self, vix: float = None, market_data: pd.DataFrame = None) -> Dict:
        """
        Get regime-based adjustments for system parameters
        
        Returns:
            Dict with adjusted parameters based on regime
        """
        if vix is None:
            vix = self.get_vix_level(market_data)
        vol_regime = self.detect_volatility_regime(vix, market_data)
        trend_regime = self.detect_trend_regime(market_data) if market_data is not None else 'weak_trend'
        hmm_regime = self.detect_hmm_regime(market_data) if market_data is not None else 'unknown'

        adjustments = {
            'vix': round(vix, 1),
            'volatility_regime': vol_regime,
            'trend_regime': trend_regime,
            'hmm_regime': hmm_regime,
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

        if trend_regime == 'choppy':
            adjustments['enable_trend_following'] = False
            logger.info("Choppy regime: Disabling trend-following strategies")

        # HMM bear regime: gate RSI mean-reversion BUY signals (mean reversion fails in
        # persistent downtrends; SELLs and other strategies are unaffected)
        if hmm_regime == 'bear':
            adjustments['enable_mean_reversion'] = False
            logger.warning("HMM bear regime detected: RSI Mean Reversion BUY signals suppressed")

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
        if 'ma crossover' in strategy_lower or 'crossover' in strategy_lower or 'trend' in strategy_lower:
            enabled = regime_adjustments['enable_trend_following']
            if not enabled:
                logger.info(f"Disabling {strategy_name} due to regime")
            return enabled
        
        # Other strategies always enabled
        return True
    
    def get_status(self, market_data=None) -> Dict:
        """Get current regime status, optionally using market_data for VIX proxy."""
        vix = self.get_vix_level(market_data)
        vol_regime = self.detect_volatility_regime(vix, market_data)
        adjustments = self.get_regime_adjustments(vix, market_data)

        return {
            'vix': vix,
            'volatility_regime': vol_regime,
            'adjustments': adjustments
        }
