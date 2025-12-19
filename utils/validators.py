"""
Data Validation Layer

Validates inputs, outputs, and data integrity across the system.
"""

from typing import Any, Optional, List, Dict
from decimal import Decimal
from datetime import datetime, date
import re


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class Validator:
    """Base validator class."""
    
    @staticmethod
    def validate_ticker(ticker: str) -> str:
        """Validate stock ticker symbol."""
        if not ticker or not isinstance(ticker, str):
            raise ValidationError("Ticker must be a non-empty string")
        
        ticker = ticker.upper().strip()
        
        if not re.match(r'^[A-Z]{1,5}$', ticker):
            raise ValidationError(f"Invalid ticker format: {ticker}")
        
        return ticker
    
    @staticmethod
    def validate_quantity(quantity: float) -> float:
        """Validate trade quantity."""
        if not isinstance(quantity, (int, float, Decimal)):
            raise ValidationError("Quantity must be a number")
        
        quantity = float(quantity)
        
        if quantity <= 0:
            raise ValidationError("Quantity must be positive")
        
        if quantity > 1000000:
            raise ValidationError("Quantity exceeds maximum limit")
        
        return quantity
    
    @staticmethod
    def validate_price(price: float) -> float:
        """Validate stock price."""
        if not isinstance(price, (int, float, Decimal)):
            raise ValidationError("Price must be a number")
        
        price = float(price)
        
        if price <= 0:
            raise ValidationError("Price must be positive")
        
        if price > 1000000:
            raise ValidationError("Price exceeds reasonable limit")
        
        return price
    
    @staticmethod
    def validate_date(date_value: Any) -> date:
        """Validate date value."""
        if isinstance(date_value, date):
            return date_value
        
        if isinstance(date_value, datetime):
            return date_value.date()
        
        if isinstance(date_value, str):
            try:
                return datetime.strptime(date_value, '%Y-%m-%d').date()
            except ValueError:
                raise ValidationError(f"Invalid date format: {date_value}")
        
        raise ValidationError("Date must be a date object or string in YYYY-MM-DD format")
    
    @staticmethod
    def validate_email(email: str) -> str:
        """Validate email address."""
        if not email or not isinstance(email, str):
            raise ValidationError("Email must be a non-empty string")
        
        email = email.strip().lower()
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValidationError(f"Invalid email format: {email}")
        
        return email
    
    @staticmethod
    def validate_percentage(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
        """Validate percentage value."""
        if not isinstance(value, (int, float, Decimal)):
            raise ValidationError("Percentage must be a number")
        
        value = float(value)
        
        if value < min_val or value > max_val:
            raise ValidationError(f"Percentage must be between {min_val} and {max_val}")
        
        return value
    
    @staticmethod
    def validate_score(score: float) -> float:
        """Validate factor score (0-1 range)."""
        if not isinstance(score, (int, float, Decimal)):
            raise ValidationError("Score must be a number")
        
        score = float(score)
        
        if score < 0 or score > 1:
            raise ValidationError("Score must be between 0 and 1")
        
        return score


class TradeValidator:
    """Validates trade-related data."""
    
    @staticmethod
    def validate_trade(
        ticker: str,
        action: str,
        quantity: float,
        price: float
    ) -> Dict[str, Any]:
        """Validate complete trade data."""
        validated = {
            'ticker': Validator.validate_ticker(ticker),
            'action': TradeValidator.validate_action(action),
            'quantity': Validator.validate_quantity(quantity),
            'price': Validator.validate_price(price)
        }
        
        # Calculate total value
        validated['total_value'] = validated['quantity'] * validated['price']
        
        return validated
    
    @staticmethod
    def validate_action(action: str) -> str:
        """Validate trade action."""
        if not action or not isinstance(action, str):
            raise ValidationError("Action must be a non-empty string")
        
        action = action.upper().strip()
        
        if action not in ['BUY', 'SELL']:
            raise ValidationError(f"Invalid action: {action}. Must be BUY or SELL")
        
        return action
    
    @staticmethod
    def validate_portfolio_allocation(positions: Dict[str, float]) -> Dict[str, float]:
        """Validate portfolio allocation percentages."""
        if not positions:
            raise ValidationError("Portfolio positions cannot be empty")
        
        total = sum(positions.values())
        
        if not (0.99 <= total <= 1.01):  # Allow small floating point errors
            raise ValidationError(f"Portfolio allocation must sum to 100%, got {total*100:.2f}%")
        
        for ticker, allocation in positions.items():
            Validator.validate_ticker(ticker)
            if allocation < 0 or allocation > 1:
                raise ValidationError(f"Invalid allocation for {ticker}: {allocation}")
        
        return positions


class FactorScoreValidator:
    """Validates factor scores."""
    
    @staticmethod
    def validate_factor_scores(scores: Dict[str, float]) -> Dict[str, float]:
        """Validate all factor scores."""
        required_factors = [
            'conviction', 'news', 'insider', 'technical',
            'moving_avg', 'volume', 'relative_strength', 'earnings'
        ]
        
        validated = {}
        
        for factor in required_factors:
            if factor not in scores:
                raise ValidationError(f"Missing required factor: {factor}")
            
            validated[factor] = Validator.validate_score(scores[factor])
        
        return validated
    
    @staticmethod
    def validate_composite_score(
        scores: Dict[str, float],
        weights: Dict[str, float]
    ) -> float:
        """Validate and calculate composite score."""
        validated_scores = FactorScoreValidator.validate_factor_scores(scores)
        
        # Validate weights sum to 1
        weight_sum = sum(weights.values())
        if not (0.99 <= weight_sum <= 1.01):
            raise ValidationError(f"Weights must sum to 1.0, got {weight_sum}")
        
        # Calculate composite
        composite = sum(
            validated_scores.get(factor, 0) * weight
            for factor, weight in weights.items()
        )
        
        return Validator.validate_score(composite)


class DatabaseValidator:
    """Validates database operations."""
    
    @staticmethod
    def validate_insert_data(table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data before database insert."""
        if not table:
            raise ValidationError("Table name cannot be empty")
        
        if not data:
            raise ValidationError("Insert data cannot be empty")
        
        # Remove None values
        cleaned_data = {k: v for k, v in data.items() if v is not None}
        
        return cleaned_data
    
    @staticmethod
    def validate_query_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate query parameters."""
        if not params:
            return {}
        
        # Sanitize string parameters to prevent SQL injection
        sanitized = {}
        for key, value in params.items():
            if isinstance(value, str):
                # Remove potentially dangerous characters
                sanitized[key] = re.sub(r'[;\'"\\]', '', value)
            else:
                sanitized[key] = value
        
        return sanitized


# Global validator instance
validator = Validator()
trade_validator = TradeValidator()
factor_validator = FactorScoreValidator()
db_validator = DatabaseValidator()
