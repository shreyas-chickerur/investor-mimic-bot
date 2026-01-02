#!/usr/bin/env python3
"""
Typed Configuration with Validation
Uses pydantic for strong typing and validation
"""
import os
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import logging

logger = logging.getLogger(__name__)


class TradingSystemConfig(BaseModel):
    """Typed configuration for trading system"""
    
    ENVIRONMENT: str = Field(default='dev', description="dev|paper|live")
    
    ALPACA_API_KEY: str = Field(default='', description="Alpaca API key")
    ALPACA_SECRET_KEY: str = Field(default='', description="Alpaca secret key")
    ALPACA_PAPER: bool = Field(default=True, description="Use paper trading")
    ALPACA_LIVE_ENABLED: bool = Field(default=False, description="Allow live trading")
    
    TRADING_DISABLED: bool = Field(default=False, description="Global kill switch")
    STRATEGY_DISABLED_LIST: str = Field(default='', description="Comma-separated strategy names")
    
    UNIVERSE_MODE: str = Field(default='static', description="static|csv|dynamic")
    UNIVERSE_CSV_PATH: str = Field(default='config/universe.csv')
    
    MAX_PORTFOLIO_HEAT: float = Field(default=0.30, ge=0.0, le=1.0)
    MAX_DAILY_LOSS_PCT: float = Field(default=0.02, ge=0.0, le=0.10)
    MAX_CORRELATION: float = Field(default=0.7, ge=0.0, le=1.0)
    
    DATA_MAX_AGE_HOURS: int = Field(default=24, ge=1, le=168)
    AUTO_UPDATE_DATA: bool = Field(default=False)
    
    ENABLE_BROKER_RECONCILIATION: bool = Field(default=True)
    RECONCILIATION_TOLERANCE_PCT: float = Field(default=0.01, ge=0.0, le=0.10)
    
    SENDER_EMAIL: Optional[str] = None
    SENDER_PASSWORD: Optional[str] = None
    RECIPIENT_EMAIL: Optional[str] = None
    SMTP_SERVER: str = Field(default='smtp.gmail.com')
    SMTP_PORT: int = Field(default=587)
    
    LOG_LEVEL: str = Field(default='INFO')
    STRUCTURED_LOGGING: bool = Field(default=False)
    
    SIGNAL_INJECTION: bool = Field(default=False, description="Validation mode")
    
    class Config:
        validate_assignment = True
    
    @field_validator('ENVIRONMENT')
    @classmethod
    def validate_environment(cls, v):
        if v not in ['dev', 'paper', 'live']:
            raise ValueError("ENVIRONMENT must be dev|paper|live")
        return v
    
    @field_validator('ALPACA_LIVE_ENABLED')
    @classmethod
    def validate_live_trading(cls, v, info):
        values = info.data
        if v and values.get('ALPACA_PAPER', True):
            raise ValueError("Cannot enable live trading with ALPACA_PAPER=true")
        return v
    
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.ENVIRONMENT == 'live' and not self.ALPACA_PAPER
    
    def validate_required_for_production(self):
        """Validate all required fields for production"""
        if self.is_production():
            if not self.ALPACA_LIVE_ENABLED:
                raise ValueError("ALPACA_LIVE_ENABLED must be true for production")
            if not self.ENABLE_BROKER_RECONCILIATION:
                raise ValueError("Reconciliation must be enabled for production")
            if not all([self.SENDER_EMAIL, self.SENDER_PASSWORD, self.RECIPIENT_EMAIL]):
                raise ValueError("Email configuration required for production")
        
        logger.info(f"Config validated: environment={self.ENVIRONMENT}, paper={self.ALPACA_PAPER}")
    
    @classmethod
    def from_env(cls):
        """Load config from environment variables"""
        return cls(
            ENVIRONMENT=os.getenv('ENVIRONMENT', 'dev'),
            ALPACA_API_KEY=os.getenv('ALPACA_API_KEY', ''),
            ALPACA_SECRET_KEY=os.getenv('ALPACA_SECRET_KEY', ''),
            ALPACA_PAPER=os.getenv('ALPACA_PAPER', 'true').lower() == 'true',
            ALPACA_LIVE_ENABLED=os.getenv('ALPACA_LIVE_ENABLED', 'false').lower() == 'true',
            TRADING_DISABLED=os.getenv('TRADING_DISABLED', 'false').lower() == 'true',
            STRATEGY_DISABLED_LIST=os.getenv('STRATEGY_DISABLED_LIST', ''),
            UNIVERSE_MODE=os.getenv('UNIVERSE_MODE', 'static'),
            UNIVERSE_CSV_PATH=os.getenv('UNIVERSE_CSV_PATH', 'config/universe.csv'),
            MAX_PORTFOLIO_HEAT=float(os.getenv('MAX_PORTFOLIO_HEAT', '0.30')),
            MAX_DAILY_LOSS_PCT=float(os.getenv('MAX_DAILY_LOSS_PCT', '0.02')),
            MAX_CORRELATION=float(os.getenv('MAX_CORRELATION', '0.7')),
            DATA_MAX_AGE_HOURS=int(os.getenv('DATA_MAX_AGE_HOURS', '24')),
            AUTO_UPDATE_DATA=os.getenv('AUTO_UPDATE_DATA', 'false').lower() == 'true',
            ENABLE_BROKER_RECONCILIATION=os.getenv('ENABLE_BROKER_RECONCILIATION', 'true').lower() == 'true',
            RECONCILIATION_TOLERANCE_PCT=float(os.getenv('RECONCILIATION_TOLERANCE_PCT', '0.01')),
            SENDER_EMAIL=os.getenv('SENDER_EMAIL'),
            SENDER_PASSWORD=os.getenv('SENDER_PASSWORD'),
            RECIPIENT_EMAIL=os.getenv('RECIPIENT_EMAIL'),
            SMTP_SERVER=os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            SMTP_PORT=int(os.getenv('SMTP_PORT', '587')),
            LOG_LEVEL=os.getenv('LOG_LEVEL', 'INFO'),
            STRUCTURED_LOGGING=os.getenv('STRUCTURED_LOGGING', 'false').lower() == 'true',
            SIGNAL_INJECTION=os.getenv('SIGNAL_INJECTION', 'false').lower() == 'true'
        )
