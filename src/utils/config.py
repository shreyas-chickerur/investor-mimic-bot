#!/usr/bin/env python3
"""
Trading System Configuration
Manages auto vs manual trading modes
"""
import os
from dotenv import load_dotenv

load_dotenv()

class TradingConfig:
    """Configuration for trading system"""
    
    # Alpaca Configuration
    ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
    ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
    ALPACA_BASE_URL = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    
    # Trading Mode
    AUTO_TRADE = os.getenv('AUTO_TRADE', 'false').lower() == 'true'
    
    # Approval Configuration
    APPROVAL_BASE_URL = os.getenv('APPROVAL_BASE_URL', 'http://localhost:8000')
    
    # Email Configuration
    EMAIL_USERNAME = os.getenv('EMAIL_USERNAME')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
    EMAIL_TO = os.getenv('EMAIL_TO')
    
    @classmethod
    def is_auto_trade_enabled(cls) -> bool:
        """Check if automatic trading is enabled"""
        return cls.AUTO_TRADE
    
    @classmethod
    def is_manual_approval_required(cls) -> bool:
        """Check if manual approval is required"""
        return not cls.AUTO_TRADE
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        if not cls.ALPACA_API_KEY or not cls.ALPACA_SECRET_KEY:
            return False
        
        # If manual approval, need email config
        if cls.is_manual_approval_required():
            if not cls.EMAIL_USERNAME or not cls.EMAIL_PASSWORD or not cls.EMAIL_TO:
                return False
        
        return True
    
    @classmethod
    def get_mode_description(cls) -> str:
        """Get human-readable mode description"""
        if cls.AUTO_TRADE:
            return "🤖 AUTOMATIC TRADING - Trades execute immediately"
        else:
            return "✋ MANUAL APPROVAL - Email sent for review before trading"
