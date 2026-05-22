#!/usr/bin/env python3
"""
Regime Detection System
Detects market regimes to enable/disable strategies appropriately
"""
from __future__ import annotations

import logging

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

        return VIXDataFetcher(source="yahoo")
    except Exception:
        return None


class RegimeDetector:
    """Detects market regime (trend/chop, high/low volatility)"""

    def __init__(
        self,
        vix_low_threshold: float = 15.0,
        vix_high_threshold: float = 25.0,
        trend_lookback: int = 50,
        vol_low_threshold: float = 0.15,
        vol_high_threshold: float = 0.25,
    ):
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

        self._hmm_cache: tuple[str, str] | None = None  # (date_str, regime)
        logger.info(
            f"Regime Detector: VIX low={vix_low_threshold}, high={vix_high_threshold}, "
            f"HMM={'enabled' if _HMM_AVAILABLE else 'unavailable (pip install hmmlearn)'}"
        )

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
                    realized_vol = returns.std() * (252**0.5) * 100
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

        if "symbol" in market_data.columns:
            return market_data.groupby(market_data.index)["close"].mean()

        return market_data["close"]

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
                        realized_vol = returns.std() * (252**0.5)
                        if realized_vol < self.vol_low_threshold:
                            regime = "low_volatility"
                        elif realized_vol > self.vol_high_threshold:
                            regime = "high_volatility"
                        else:
                            regime = "normal"
                        logger.info(
                            f"Volatility regime: {regime} (realized vol: {realized_vol:.2f})"
                        )
                        return regime
            vix = self.get_vix_level()

        if vix < self.vix_low:
            regime = "low_volatility"
        elif vix > self.vix_high:
            regime = "high_volatility"
        else:
            regime = "normal"

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
            return "unknown"

        try:
            spy = (
                market_data[market_data["symbol"] == "SPY"]["close"]
                if "symbol" in market_data.columns
                else market_data["close"]
            )
            if len(spy) < 60:
                return "unknown"

            rets = spy.pct_change().dropna()
            vol = rets.rolling(20).std().dropna()
            aligned_rets = rets.reindex(vol.index)
            X = np.column_stack([aligned_rets.values, vol.values])

            model = _hmm_lib.GaussianHMM(
                n_components=2, covariance_type="full", n_iter=100, random_state=42
            )
            model.fit(X)
            states = model.predict(X)

            # Bull state = whichever component has the higher mean return
            mean_returns = [X[states == s, 0].mean() for s in range(2)]
            bull_state = int(np.argmax(mean_returns))
            regime = "bull" if states[-1] == bull_state else "bear"

            self._hmm_cache = (today_str, regime)
            logger.info(
                f"HMM regime: {regime} (bull_state={bull_state}, "
                f"mean_rets=[{mean_returns[0]:.4f}, {mean_returns[1]:.4f}])"
            )
            return regime

        except Exception as exc:
            logger.warning(f"HMM regime detection failed: {exc}")
            return "unknown"

    def detect_trend_regime(self, market_data: pd.DataFrame) -> str:
        """
        Detect trend regime (trending vs choppy)

        Uses SPY 200-day MA as proxy for market trend

        Returns:
            'strong_trend', 'weak_trend', or 'choppy'
        """
        proxy = self._get_market_proxy(market_data)
        if len(proxy) < 200:
            return "weak_trend"

        short_ma = proxy.rolling(window=50).mean().iloc[-1]
        long_ma = proxy.rolling(window=200).mean().iloc[-1]
        if long_ma == 0 or pd.isna(short_ma) or pd.isna(long_ma):
            return "weak_trend"

        trend_strength = (short_ma - long_ma) / long_ma
        if trend_strength > 0.02:
            return "strong_trend"
        if abs(trend_strength) < 0.01:
            return "choppy"
        return "weak_trend"

    def get_regime_adjustments(
        self,
        vix: float = None,
        market_data: pd.DataFrame = None,
        base_max_heat: float = 0.30,
    ) -> dict:
        """
        Get regime-based adjustments for system parameters

        Returns:
            Dict with adjusted parameters based on regime
        """
        if vix is None:
            vix = self.get_vix_level(market_data)
        vol_regime = self.detect_volatility_regime(vix, market_data)
        trend_regime = (
            self.detect_trend_regime(market_data) if market_data is not None else "weak_trend"
        )
        hmm_regime = self.detect_hmm_regime(market_data) if market_data is not None else "unknown"

        adjustments = {
            "vix": round(vix, 1),
            "volatility_regime": vol_regime,
            "trend_regime": trend_regime,
            "hmm_regime": hmm_regime,
            "max_portfolio_heat": base_max_heat,
            "enable_mean_reversion": True,
            "enable_breakout": True,
            "enable_trend_following": True,
            "position_size_multiplier": 1.0,
        }

        # Adjust based on volatility regime
        if vol_regime == "low_volatility":
            adjustments["max_portfolio_heat"] = base_max_heat * 1.2
            adjustments["position_size_multiplier"] = 1.2  # Larger positions
            logger.info(
                "Low volatility: Increasing heat to %.0f%%, position size +20%%",
                adjustments["max_portfolio_heat"] * 100,
            )

        elif vol_regime == "high_volatility":
            adjustments["max_portfolio_heat"] = base_max_heat * 0.7
            adjustments["position_size_multiplier"] = 0.8  # Smaller positions
            adjustments["enable_breakout"] = False  # Disable breakout strategies
            logger.info(
                "High volatility: Reducing heat to %.0f%%, position size -20%%, disabling breakouts",
                adjustments["max_portfolio_heat"] * 100,
            )

        if trend_regime == "choppy":
            adjustments["enable_trend_following"] = False
            logger.info("Choppy regime: Disabling trend-following strategies")

        # HMM bear regime: gate RSI mean-reversion BUY signals (mean reversion fails in
        # persistent downtrends; SELLs and other strategies are unaffected)
        if hmm_regime == "bear":
            adjustments["enable_mean_reversion"] = False
            logger.warning("HMM bear regime detected: RSI Mean Reversion BUY signals suppressed")

        return adjustments

    def should_enable_strategy(self, strategy_name: str, regime_adjustments: dict) -> bool:
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
        if "rsi" in strategy_lower or "mean reversion" in strategy_lower:
            enabled = regime_adjustments["enable_mean_reversion"]
            if not enabled:
                logger.info(f"Disabling {strategy_name} due to regime")
            return enabled

        # Breakout strategies
        if "breakout" in strategy_lower or "volatility breakout" in strategy_lower:
            enabled = regime_adjustments["enable_breakout"]
            if not enabled:
                logger.info(f"Disabling {strategy_name} due to regime")
            return enabled

        # Trend following strategies
        if (
            "ma crossover" in strategy_lower
            or "crossover" in strategy_lower
            or "trend" in strategy_lower
        ):
            enabled = regime_adjustments["enable_trend_following"]
            if not enabled:
                logger.info(f"Disabling {strategy_name} due to regime")
            return enabled

        # Other strategies always enabled
        return True

    def _compute_adx(self, proxy: pd.Series, period: int = 14) -> float:
        """Average Directional Index from a price series (Wilder smoothing)."""
        try:
            if len(proxy) < period + 2:
                return 0.0
            highs = proxy  # single-series proxy; use price as both high and low approximation
            lows = proxy
            closes = proxy

            tr_list = []
            pdm_list = []
            ndm_list = []
            for i in range(1, len(closes)):
                tr = max(
                    highs.iloc[i] - lows.iloc[i],
                    abs(highs.iloc[i] - closes.iloc[i - 1]),
                    abs(lows.iloc[i] - closes.iloc[i - 1]),
                )
                pdm = max(highs.iloc[i] - highs.iloc[i - 1], 0)
                ndm = max(lows.iloc[i - 1] - lows.iloc[i], 0)
                if pdm > ndm:
                    ndm = 0.0
                elif ndm > pdm:
                    pdm = 0.0
                else:
                    pdm = ndm = 0.0
                tr_list.append(tr)
                pdm_list.append(pdm)
                ndm_list.append(ndm)

            tr_s = pd.Series(tr_list)
            pdm_s = pd.Series(pdm_list)
            ndm_s = pd.Series(ndm_list)

            atr = tr_s.rolling(period).mean()
            pdi = 100 * (pdm_s.rolling(period).mean() / atr.replace(0, float("nan")))
            ndi = 100 * (ndm_s.rolling(period).mean() / atr.replace(0, float("nan")))
            dx = (100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, float("nan"))).dropna()
            if len(dx) < period:
                return 0.0
            adx = dx.rolling(period).mean().iloc[-1]
            return float(adx) if not pd.isna(adx) else 0.0
        except Exception:
            return 0.0

    def _compute_breadth(self, market_data: pd.DataFrame, lookback: int = 20) -> float:
        """Return fraction of symbols above their 20-day SMA (market breadth)."""
        try:
            if market_data is None or market_data.empty or "symbol" not in market_data.columns:
                return 0.5
            above = 0
            total = 0
            for _sym, grp in market_data.groupby("symbol"):
                prices = grp["close"].sort_index()
                if len(prices) < lookback + 1:
                    continue
                sma = prices.iloc[-lookback:].mean()
                above += int(prices.iloc[-1] > sma)
                total += 1
            return above / total if total > 0 else 0.5
        except Exception:
            return 0.5

    def detect_composite_regime(
        self,
        vix: float | None = None,
        market_data: pd.DataFrame | None = None,
    ) -> str:
        """5-regime composite label used by the strategy weight table.

        Priority order (first match wins):
          HIGH_VOL     — VIX > 25
          LOW_VOL      — VIX < 15
          TRENDING_BULL — ADX > 25 AND breadth > 55%
          RANGING      — ADX < 20
          NORMAL       — everything else
        """
        if vix is None:
            vix = self.get_vix_level(market_data)

        if vix > 25:
            regime = "HIGH_VOL"
        elif vix < 15:
            regime = "LOW_VOL"
        else:
            if market_data is None or market_data.empty:
                # No price data — cannot compute ADX or breadth; fall back to NORMAL
                regime = "NORMAL"
            else:
                proxy = self._get_market_proxy(market_data)
                adx = self._compute_adx(proxy)
                breadth = self._compute_breadth(market_data)
                logger.info(
                    "Composite regime inputs: vix=%.1f adx=%.1f breadth=%.2f", vix, adx, breadth
                )
                if adx > 25 and breadth > 0.55:
                    regime = "TRENDING_BULL"
                elif adx < 20:
                    regime = "RANGING"
                else:
                    regime = "NORMAL"

        logger.info("Composite regime: %s (VIX=%.1f)", regime, vix)
        return regime

    def get_status(self, market_data=None) -> dict:
        """Get current regime status, optionally using market_data for VIX proxy."""
        vix = self.get_vix_level(market_data)
        vol_regime = self.detect_volatility_regime(vix, market_data)
        adjustments = self.get_regime_adjustments(vix, market_data)
        composite = self.detect_composite_regime(vix, market_data)

        return {
            "vix": vix,
            "volatility_regime": vol_regime,
            "composite_regime": composite,
            "adjustments": adjustments,
        }
