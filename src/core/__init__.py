"""Core trading system components."""
from __future__ import annotations

__all__ = ['TradingDatabase', 'TradingStrategy']

_lazy_map = {
    'TradingDatabase':  ('src.core.database',       'TradingDatabase'),
    'TradingStrategy':  ('src.core.strategy_base',  'TradingStrategy'),
}


def __getattr__(name: str) -> object:
    if name in _lazy_map:
        import importlib
        mod, cls = _lazy_map[name]
        return getattr(importlib.import_module(mod), cls)
    raise AttributeError(f"module 'src.core' has no attribute {name!r}")
