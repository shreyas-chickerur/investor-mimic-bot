"""
DRY_RUN Mode Wrapper

Runs full system without broker writes when DRY_RUN=true.
All logic, sizing, intent creation, and reporting executes normally.
"""

import os
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class DryRunWrapper:
    """
    Wrapper for broker operations that can be disabled in DRY_RUN mode.
    
    When DRY_RUN=true:
    - All logic executes normally
    - No actual broker writes occur
    - All reporting and artifacts are generated
    - Logs show what WOULD have been executed
    """
    
    def __init__(self):
        """Initialize DRY_RUN wrapper."""
        self.dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'
        
        if self.dry_run:
            logger.warning("=" * 80)
            logger.warning("DRY_RUN MODE ENABLED - No broker writes will occur")
            logger.warning("=" * 80)
        else:
            logger.info("DRY_RUN mode disabled - Live broker writes enabled")
    
    def is_dry_run(self) -> bool:
        """Check if in DRY_RUN mode."""
        return self.dry_run
    
    def execute_broker_operation(self, operation_name: str, 
                                 operation_func: Callable, 
                                 *args, **kwargs) -> Any:
        """
        Execute broker operation with DRY_RUN protection.
        
        Args:
            operation_name: Name of operation for logging
            operation_func: Function to execute
            *args, **kwargs: Arguments to pass to function
        
        Returns:
            Result of operation (or mock result in DRY_RUN mode)
        """
        if self.dry_run:
            logger.info(f"[DRY_RUN] Would execute: {operation_name}")
            logger.debug(f"[DRY_RUN] Args: {args}, Kwargs: {kwargs}")
            
            # Return mock result based on operation type
            return self._get_mock_result(operation_name, *args, **kwargs)
        else:
            # Execute actual operation
            return operation_func(*args, **kwargs)
    
    def _get_mock_result(self, operation_name: str, *args, **kwargs) -> Any:
        """
        Get mock result for DRY_RUN mode.
        
        Args:
            operation_name: Name of operation
            *args, **kwargs: Operation arguments
        
        Returns:
            Mock result appropriate for operation type
        """
        # Mock order submission
        if 'submit_order' in operation_name.lower():
            return self._mock_order_result(*args, **kwargs)
        
        # Mock position close
        if 'close_position' in operation_name.lower():
            return self._mock_close_result(*args, **kwargs)
        
        # Mock account query
        if 'get_account' in operation_name.lower():
            return self._mock_account_result()
        
        # Mock positions query
        if 'get_positions' in operation_name.lower():
            return self._mock_positions_result()
        
        # Default: return None
        return None
    
    def _mock_order_result(self, *args, **kwargs):
        """Mock order submission result."""
        import uuid
        from datetime import datetime
        
        class MockOrder:
            def __init__(self):
                self.id = f"DRY_RUN_{uuid.uuid4().hex[:8]}"
                self.status = "filled"
                self.filled_qty = kwargs.get('qty', 0) if kwargs else (args[0].qty if args else 0)
                self.filled_avg_price = kwargs.get('price', 100.0) if kwargs else 100.0
                self.created_at = datetime.now()
                self.filled_at = datetime.now()
        
        return MockOrder()
    
    def _mock_close_result(self, *args, **kwargs):
        """Mock position close result."""
        import uuid
        
        class MockCloseOrder:
            def __init__(self):
                self.id = f"DRY_RUN_CLOSE_{uuid.uuid4().hex[:8]}"
                self.status = "filled"
        
        return MockCloseOrder()
    
    def _mock_account_result(self):
        """Mock account query result."""
        class MockAccount:
            def __init__(self):
                self.cash = "1000.00"
                self.portfolio_value = "1000.00"
                self.buying_power = "2000.00"
                self.equity = "1000.00"
        
        return MockAccount()
    
    def _mock_positions_result(self):
        """Mock positions query result."""
        return []  # Empty positions list
    
    def log_dry_run_summary(self, operations_attempted: int):
        """
        Log summary of DRY_RUN operations.
        
        Args:
            operations_attempted: Number of operations that would have executed
        """
        if self.dry_run:
            logger.info("=" * 80)
            logger.info(f"DRY_RUN SUMMARY: {operations_attempted} broker operations simulated")
            logger.info("No actual trades were executed")
            logger.info("=" * 80)


# Global instance
_dry_run_wrapper = None


def get_dry_run_wrapper() -> DryRunWrapper:
    """Get global DRY_RUN wrapper instance."""
    global _dry_run_wrapper
    if _dry_run_wrapper is None:
        _dry_run_wrapper = DryRunWrapper()
    return _dry_run_wrapper


def is_dry_run() -> bool:
    """Check if in DRY_RUN mode."""
    return get_dry_run_wrapper().is_dry_run()
