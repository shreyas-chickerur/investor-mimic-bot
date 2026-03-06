"""Integration and execution components.

Import directly from submodules for best performance:
    from src.integration.strategy_runner import StrategyRunner
    from src.integration.pending_signals_manager import PendingSignalsManager

Package-level imports (``from src.integration import X``) are supported via
lazy loading so that importing one class does not force-load unrelated modules.
"""
from __future__ import annotations

__all__ = [
    'DryRunExecutor',
    'PortfolioBacktester',
    'StrategyRunner',
    'StrategyDatabase',
    'PendingSignalsManager',
    'CashManager',
]

_lazy_map = {
    'DryRunExecutor':      ('src.integration.dry_run_executor',    'DryRunExecutor'),
    'PortfolioBacktester': ('src.integration.portfolio_backtester', 'PortfolioBacktester'),
    'StrategyRunner':      ('src.integration.strategy_runner',      'StrategyRunner'),
    'StrategyDatabase':    ('src.integration.strategy_database',    'StrategyDatabase'),
    'PendingSignalsManager': ('src.integration.pending_signals_manager', 'PendingSignalsManager'),
    'CashManager':         ('src.integration.cash_manager',         'CashManager'),
}


def __getattr__(name: str) -> object:
    if name in _lazy_map:
        import importlib
        module_name, class_name = _lazy_map[name]
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
    raise AttributeError(f"module 'src.integration' has no attribute {name!r}")
