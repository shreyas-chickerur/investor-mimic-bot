"""
Pydantic schemas for data validation and type safety.

Ensures data integrity across the trading system with formal validation.
"""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, validator, ConfigDict
import pandas as pd


class MarketDataSchema(BaseModel):
    """Schema for validating market data."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    symbol: str = Field(..., min_length=1, max_length=10, description="Stock ticker symbol")
    date: datetime = Field(..., description="Trading date")
    open: float = Field(..., gt=0, description="Opening price")
    high: float = Field(..., gt=0, description="High price")
    low: float = Field(..., gt=0, description="Low price")
    close: float = Field(..., gt=0, description="Closing price")
    volume: int = Field(..., ge=0, description="Trading volume")
    
    # Technical indicators (optional)
    rsi: Optional[float] = Field(None, ge=0, le=100, description="RSI indicator")
    sma_20: Optional[float] = Field(None, gt=0, description="20-day SMA")
    sma_50: Optional[float] = Field(None, gt=0, description="50-day SMA")
    sma_200: Optional[float] = Field(None, gt=0, description="200-day SMA")
    atr_20: Optional[float] = Field(None, ge=0, description="20-day ATR")
    volatility_20d: Optional[float] = Field(None, ge=0, description="20-day volatility")
    
    @validator('high')
    def high_must_be_highest(cls, v, values):
        """Validate that high is the highest price."""
        if 'low' in values and v < values['low']:
            raise ValueError('High must be >= Low')
        if 'open' in values and v < values['open']:
            raise ValueError('High must be >= Open')
        if 'close' in values and v < values['close']:
            raise ValueError('High must be >= Close')
        return v
    
    @validator('low')
    def low_must_be_lowest(cls, v, values):
        """Validate that low is the lowest price."""
        if 'high' in values and v > values['high']:
            raise ValueError('Low must be <= High')
        if 'open' in values and v > values['open']:
            raise ValueError('Low must be <= Open')
        if 'close' in values and v > values['close']:
            raise ValueError('Low must be <= Close')
        return v


class SignalSchema(BaseModel):
    """Schema for validating trading signals."""
    
    symbol: str = Field(..., min_length=1, max_length=10)
    action: Literal['BUY', 'SELL'] = Field(..., description="Trade action")
    shares: int = Field(..., gt=0, description="Number of shares")
    price: float = Field(..., gt=0, description="Expected execution price")
    value: float = Field(..., gt=0, description="Total trade value")
    confidence: float = Field(..., ge=0, le=1, description="Signal confidence")
    reasoning: str = Field(..., min_length=1, description="Signal reasoning")
    strategy_id: Optional[int] = Field(None, ge=1, description="Strategy ID")
    asof_date: Optional[datetime] = Field(None, description="Signal generation date")
    
    @validator('value')
    def value_must_match_shares_price(cls, v, values):
        """Validate that value = shares * price."""
        if 'shares' in values and 'price' in values:
            expected_value = values['shares'] * values['price']
            if abs(v - expected_value) > 0.01:  # Allow small floating point errors
                raise ValueError(f'Value {v} does not match shares * price {expected_value}')
        return v


class TradeSchema(BaseModel):
    """Schema for validating executed trades."""
    
    symbol: str = Field(..., min_length=1, max_length=10)
    action: Literal['BUY', 'SELL']
    shares: int = Field(..., gt=0)
    price: float = Field(..., gt=0)
    value: float = Field(..., gt=0)
    strategy_id: int = Field(..., ge=1)
    executed_at: datetime = Field(...)
    order_id: Optional[str] = Field(None, description="Broker order ID")
    commission: Optional[float] = Field(None, ge=0, description="Trade commission")
    slippage: Optional[float] = Field(None, description="Price slippage")
    
    @validator('value')
    def value_must_match_shares_price(cls, v, values):
        """Validate that value = shares * price."""
        if 'shares' in values and 'price' in values:
            expected_value = values['shares'] * values['price']
            if abs(v - expected_value) > 0.01:
                raise ValueError(f'Value {v} does not match shares * price {expected_value}')
        return v


class PortfolioStateSchema(BaseModel):
    """Schema for validating portfolio state."""
    
    total_value: float = Field(..., gt=0, description="Total portfolio value")
    cash: float = Field(..., ge=0, description="Available cash")
    positions_value: float = Field(..., ge=0, description="Total positions value")
    open_positions: int = Field(..., ge=0, description="Number of open positions")
    daily_pnl: Optional[float] = Field(None, description="Daily P&L")
    total_pnl: Optional[float] = Field(None, description="Total P&L")
    heat: float = Field(..., ge=0, le=1, description="Portfolio heat (exposure)")
    
    @validator('total_value')
    def total_must_equal_cash_plus_positions(cls, v, values):
        """Validate that total = cash + positions."""
        if 'cash' in values and 'positions_value' in values:
            expected_total = values['cash'] + values['positions_value']
            if abs(v - expected_total) > 0.01:
                raise ValueError(
                    f'Total value {v} does not match cash + positions {expected_total}'
                )
        return v


# Validation helper functions

def validate_market_data(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """
    Validate market data DataFrame against schema.
    
    Args:
        df: Market data DataFrame
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Check required columns
    required_cols = ['symbol', 'open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")
        return False, errors
    
    # Validate each row
    for idx, row in df.iterrows():
        try:
            MarketDataSchema(
                symbol=row['symbol'],
                date=row.name if isinstance(row.name, datetime) else datetime.now(),
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume'],
                rsi=row.get('rsi'),
                sma_20=row.get('sma_20'),
                sma_50=row.get('sma_50'),
                sma_200=row.get('sma_200'),
                atr_20=row.get('atr_20'),
                volatility_20d=row.get('volatility_20d'),
            )
        except Exception as e:
            errors.append(f"Row {idx} ({row.get('symbol', 'unknown')}): {str(e)}")
            if len(errors) > 10:  # Limit error messages
                errors.append("... (more errors truncated)")
                break
    
    return len(errors) == 0, errors


def validate_signal(signal: dict) -> tuple[bool, Optional[str]]:
    """
    Validate a trading signal.
    
    Args:
        signal: Signal dictionary
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        SignalSchema(**signal)
        return True, None
    except Exception as e:
        return False, str(e)


def validate_trade(trade: dict) -> tuple[bool, Optional[str]]:
    """
    Validate an executed trade.
    
    Args:
        trade: Trade dictionary
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        TradeSchema(**trade)
        return True, None
    except Exception as e:
        return False, str(e)


def validate_portfolio_state(state: dict) -> tuple[bool, Optional[str]]:
    """
    Validate portfolio state.
    
    Args:
        state: Portfolio state dictionary
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        PortfolioStateSchema(**state)
        return True, None
    except Exception as e:
        return False, str(e)
