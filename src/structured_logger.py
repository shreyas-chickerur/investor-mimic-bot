#!/usr/bin/env python3
"""
Structured JSON Event Logger
Logs events as JSON for observability and analysis
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class StructuredLogger:
    """Logs structured JSON events"""
    
    EVENT_TYPES = [
        'SIGNAL_GENERATED',
        'SIGNAL_REJECTED',
        'ORDER_INTENT_CREATED',
        'ORDER_SUBMITTED',
        'ORDER_FILLED',
        'ORDER_REJECTED',
        'RECONCILIATION_CHECK',
        'KILL_SWITCH_TRIGGERED',
        'STRATEGY_DISABLED',
        'RISK_LIMIT_HIT',
        'ERROR'
    ]
    
    def __init__(self, run_id: str, log_dir: str = 'logs/events'):
        self.run_id = run_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.log_dir / f"events_{run_id}.jsonl"
        
        logger.info(f"Structured logger initialized: {self.log_file}")
    
    def log_event(self, event_type: str, data: Dict[str, Any], 
                  strategy_id: Optional[int] = None,
                  symbol: Optional[str] = None,
                  stage: Optional[str] = None):
        """
        Log a structured event
        
        Args:
            event_type: One of EVENT_TYPES
            data: Event-specific data
            strategy_id: Optional strategy ID
            symbol: Optional symbol
            stage: Optional pipeline stage
        """
        if event_type not in self.EVENT_TYPES:
            logger.warning(f"Unknown event type: {event_type}")
        
        event = {
            'timestamp': datetime.now().isoformat(),
            'run_id': self.run_id,
            'event_type': event_type,
            'strategy_id': strategy_id,
            'symbol': symbol,
            'stage': stage,
            'data': data
        }
        
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(event) + '\n')
    
    def log_signal_generated(self, strategy_id: int, symbol: str, 
                            action: str, confidence: float, reasoning: str):
        """Log signal generation event"""
        self.log_event(
            'SIGNAL_GENERATED',
            {
                'action': action,
                'confidence': confidence,
                'reasoning': reasoning
            },
            strategy_id=strategy_id,
            symbol=symbol,
            stage='GENERATION'
        )
    
    def log_signal_rejected(self, strategy_id: int, symbol: str, 
                           stage: str, reason_code: str, details: Dict = None):
        """Log signal rejection event"""
        self.log_event(
            'SIGNAL_REJECTED',
            {
                'reason_code': reason_code,
                'details': details or {}
            },
            strategy_id=strategy_id,
            symbol=symbol,
            stage=stage
        )
    
    def log_order_intent(self, intent_id: str, strategy_id: int, 
                        symbol: str, side: str, qty: float):
        """Log order intent creation"""
        self.log_event(
            'ORDER_INTENT_CREATED',
            {
                'intent_id': intent_id,
                'side': side,
                'qty': qty
            },
            strategy_id=strategy_id,
            symbol=symbol,
            stage='ORDER_INTENT'
        )
    
    def log_order_submitted(self, intent_id: str, broker_order_id: str, 
                           strategy_id: int, symbol: str):
        """Log order submission"""
        self.log_event(
            'ORDER_SUBMITTED',
            {
                'intent_id': intent_id,
                'broker_order_id': broker_order_id
            },
            strategy_id=strategy_id,
            symbol=symbol,
            stage='EXECUTION'
        )
    
    def log_order_filled(self, broker_order_id: str, strategy_id: int, 
                        symbol: str, qty: float, price: float):
        """Log order fill"""
        self.log_event(
            'ORDER_FILLED',
            {
                'broker_order_id': broker_order_id,
                'qty': qty,
                'price': price
            },
            strategy_id=strategy_id,
            symbol=symbol,
            stage='EXECUTION'
        )
    
    def log_kill_switch(self, reason: str, details: Dict = None):
        """Log kill switch activation"""
        self.log_event(
            'KILL_SWITCH_TRIGGERED',
            {
                'reason': reason,
                'details': details or {}
            },
            stage='KILL_SWITCH'
        )
