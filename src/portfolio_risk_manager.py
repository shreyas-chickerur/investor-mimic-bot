#!/usr/bin/env python3
"""
Portfolio-Level Risk Manager
Enforces portfolio-wide risk limits across all strategies
"""
import logging
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class PortfolioRiskManager:
    """Manages portfolio-level risk controls"""
    
    def __init__(self, 
                 max_portfolio_heat: float = 0.30,  # Max 30% capital exposed
                 max_daily_loss_pct: float = 0.02,  # Max 2% daily loss
                 max_correlated_exposure: float = 0.40):  # Max 40% in correlated positions
        """
        Initialize risk manager
        
        Args:
            max_portfolio_heat: Maximum portfolio exposure (default 30%)
            max_daily_loss_pct: Maximum daily loss percentage (default 2%)
            max_correlated_exposure: Maximum exposure to correlated positions
        """
        self.base_max_heat = max_portfolio_heat
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_correlated_exposure = max_correlated_exposure
        
        self.daily_start_value = None
        self.trading_halted = False
        
        # Regime-dependent heat limits
        self.regime_heat_limits = {
            'NORMAL': max_portfolio_heat,
            'HIGH_VOL': max_portfolio_heat * 0.83,  # 25% if base is 30%
            'CRISIS': max_portfolio_heat * 0.67     # 20% if base is 30%
        }
        
        self.current_regime = 'NORMAL'
        self.max_portfolio_heat = self.regime_heat_limits['NORMAL']
        
        logger.info(f"Portfolio Risk Manager: base_heat={max_portfolio_heat*100:.0f}%, "
                   f"daily_loss={max_daily_loss_pct*100:.0f}%, regime-adaptive enabled")
    
    def set_regime(self, regime: str):
        """
        Update risk limits based on market regime
        
        Args:
            regime: Market regime (NORMAL, HIGH_VOL, CRISIS)
        """
        if regime in self.regime_heat_limits:
            old_limit = self.max_portfolio_heat
            self.current_regime = regime
            self.max_portfolio_heat = self.regime_heat_limits[regime]
            
            if old_limit != self.max_portfolio_heat:
                logger.info(f"Regime changed to {regime}: heat limit adjusted "
                          f"{old_limit*100:.0f}% → {self.max_portfolio_heat*100:.0f}%")
    
    def set_daily_start_value(self, portfolio_value: float):
        """Set the portfolio value at start of day for daily loss tracking"""
        self.daily_start_value = portfolio_value
        self.trading_halted = False
        logger.info(f"Daily start value set: ${portfolio_value:,.2f}")
    
    def check_daily_loss_limit(self, current_value: float) -> bool:
        """
        Check if daily loss limit has been breached
        
        Returns:
            True if trading should continue, False if halted
        """
        if self.daily_start_value is None:
            return True
        
        daily_loss = (current_value - self.daily_start_value) / self.daily_start_value
        
        if daily_loss < -self.max_daily_loss_pct:
            self.trading_halted = True
            logger.error(f"CIRCUIT BREAKER: Daily loss {daily_loss*100:.2f}% exceeds limit "
                        f"{self.max_daily_loss_pct*100}%. Trading halted.")
            return False
        
        return True
    
    def check_portfolio_heat(self, total_exposure: float, portfolio_value: float) -> bool:
        """
        Check if portfolio heat (exposure) is within limits
        
        Args:
            total_exposure: Total value of all positions
            portfolio_value: Total portfolio value
            
        Returns:
            True if within limits, False if exceeded
        """
        heat = total_exposure / portfolio_value if portfolio_value > 0 else 0
        
        if heat > self.max_portfolio_heat:
            logger.warning(f"Portfolio heat {heat*100:.1f}% exceeds limit "
                          f"{self.max_portfolio_heat*100}%. Rejecting new positions.")
            return False
        
        return True
    
    def can_add_position(self, 
                        position_value: float,
                        current_exposure: float,
                        portfolio_value: float) -> bool:
        """
        Check if a new position can be added
        
        Args:
            position_value: Value of proposed position
            current_exposure: Current total exposure
            portfolio_value: Total portfolio value
            
        Returns:
            True if position can be added, False otherwise
        """
        # Check if trading is halted
        if self.trading_halted:
            logger.warning("Trading halted due to daily loss limit")
            return False
        
        # Check portfolio heat
        new_exposure = current_exposure + position_value
        if not self.check_portfolio_heat(new_exposure, portfolio_value):
            return False
        
        return True
    
    def get_status(self) -> Dict:
        """Get current risk manager status"""
        return {
            'trading_halted': self.trading_halted,
            'max_portfolio_heat': self.max_portfolio_heat,
            'max_daily_loss_pct': self.max_daily_loss_pct,
            'daily_start_value': self.daily_start_value
        }
