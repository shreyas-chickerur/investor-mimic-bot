"""Trading strategy implementations.

The four active strategies used in production are:
- RSIMeanReversionStrategy
- MLMomentumStrategy
- EarningsDriftStrategy
- FactorMomentumStrategy

All strategies inherit from src.core.strategy_base.TradingStrategy.
"""
from __future__ import annotations

__all__ = [
    'RSIMeanReversionStrategy',
    'MLMomentumStrategy',
    'EarningsDriftStrategy',
    'FactorMomentumStrategy',
]

_lazy_map = {
    'RSIMeanReversionStrategy': ('src.strategies.strategy_rsi_mean_reversion', 'RSIMeanReversionStrategy'),
    'MLMomentumStrategy':       ('src.strategies.strategy_ml_momentum',        'MLMomentumStrategy'),
    'EarningsDriftStrategy':    ('src.strategies.strategy_earnings_drift',     'EarningsDriftStrategy'),
    'FactorMomentumStrategy':   ('src.strategies.strategy_factor_momentum',    'FactorMomentumStrategy'),
}


def __getattr__(name: str) -> object:
    if name in _lazy_map:
        import importlib
        mod, cls = _lazy_map[name]
        return getattr(importlib.import_module(mod), cls)
    raise AttributeError(f"module 'src.strategies' has no attribute {name!r}")
