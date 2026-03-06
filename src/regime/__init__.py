"""Regime detection and dynamic allocation."""
from __future__ import annotations

__all__ = ['RegimeDetector', 'DynamicAllocator']

_lazy_map = {
    'RegimeDetector':  ('src.regime.regime_detector',  'RegimeDetector'),
    'DynamicAllocator': ('src.regime.dynamic_allocator', 'DynamicAllocator'),
}


def __getattr__(name: str) -> object:
    if name in _lazy_map:
        import importlib
        mod, cls = _lazy_map[name]
        return getattr(importlib.import_module(mod), cls)
    raise AttributeError(f"module 'src.regime' has no attribute {name!r}")
