"""Monitoring and performance tracking components."""
from __future__ import annotations

__all__ = ['PnLCalculator', 'SignalFunnelTracker', 'StrategyHealthScorer', 'DailyArtifactWriter']

_lazy_map = {
    'PnLCalculator':        ('src.monitoring.pnl_calculator',         'PnLCalculator'),
    'SignalFunnelTracker':  ('src.monitoring.signal_funnel_tracker',  'SignalFunnelTracker'),
    'StrategyHealthScorer': ('src.monitoring.strategy_health_scorer', 'StrategyHealthScorer'),
    'DailyArtifactWriter':  ('src.monitoring.artifact_writer',        'DailyArtifactWriter'),
}


def __getattr__(name: str) -> object:
    if name in _lazy_map:
        import importlib
        mod, cls = _lazy_map[name]
        return getattr(importlib.import_module(mod), cls)
    raise AttributeError(f"module 'src.monitoring' has no attribute {name!r}")
