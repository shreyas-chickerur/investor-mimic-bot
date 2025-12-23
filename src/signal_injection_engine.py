#!/usr/bin/env python3
"""
Signal Injection Engine - VALIDATION ONLY

Purpose: Inject synthetic but structurally valid signals to validate
execution pipeline independent of market conditions.

CRITICAL: This bypasses ONLY signal generation. All downstream logic
(risk management, correlation filtering, position sizing, execution)
remains fully active and must be validated.

This is NEVER used in production trading.
"""
import logging
from typing import List, Dict
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

class SignalInjectionEngine:
    """
    Injects synthetic signals for validation testing
    
    VALIDATION ONLY - Never used in production
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize signal injection engine
        
        Args:
            config_path: Path to validation_config.yaml
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / 'config' / 'validation_config.yaml'
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.enabled = self.config['validation_mode']['signal_injection']['enabled']
        self.templates = self.config.get('signal_injection_templates', [])
        
        if self.enabled:
            logger.warning("="*80)
            logger.warning("SIGNAL INJECTION MODE ENABLED - VALIDATION ONLY")
            logger.warning("This mode bypasses strategy signal generation")
            logger.warning("DO NOT USE IN PRODUCTION")
            logger.warning("="*80)
    
    def is_enabled(self) -> bool:
        """Check if signal injection is enabled"""
        return self.enabled
    
    def inject_signals(self, date, existing_signals: List[Dict] = None) -> List[Dict]:
        """
        Inject synthetic signals for validation
        
        Args:
            date: Current date in backtest
            existing_signals: Signals from strategies (will be replaced)
        
        Returns:
            List of injected signals
        """
        if not self.enabled:
            return existing_signals or []
        
        # Inject signals on EVERY day to ensure we get trades
        # Use templates to create signals
        injected = []
        for template in self.templates[:self.config['validation_mode']['signal_injection']['inject_count']]:
            signal = template.copy()
            signal['injected'] = True
            signal['injection_date'] = str(date)
            injected.append(signal)
        
        if len(injected) > 0:
            logger.info(f"[INJECTION] {date}: Injected {len(injected)} synthetic signals")
            for sig in injected:
                logger.info(f"  [INJECTION] {sig['action']} {sig['symbol']} @ ${sig['price']:.2f}, {sig['shares']} shares")
        
        return injected
    
    def mark_as_injected(self, signal: Dict) -> Dict:
        """Mark a signal as injected for tracking"""
        signal['injected'] = True
        return signal
