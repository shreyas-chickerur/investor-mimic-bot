"""Risk management components."""
from __future__ import annotations

__all__ = ['PortfolioRiskManager', 'DrawdownStopManager', 'StopLossManager', 'CorrelationFilter', 'BrokerReconciler']

_lazy_map = {
    'PortfolioRiskManager':  ('src.risk.portfolio_risk_manager', 'PortfolioRiskManager'),
    'DrawdownStopManager':   ('src.risk.drawdown_stop_manager',  'DrawdownStopManager'),
    'StopLossManager':       ('src.risk.stop_loss_manager',       'StopLossManager'),
    'CorrelationFilter':     ('src.risk.correlation_filter',      'CorrelationFilter'),
    'BrokerReconciler':      ('src.risk.broker_reconciler',       'BrokerReconciler'),
}


def __getattr__(name: str) -> object:
    if name in _lazy_map:
        import importlib
        mod, cls = _lazy_map[name]
        return getattr(importlib.import_module(mod), cls)
    raise AttributeError(f"module 'src.risk' has no attribute {name!r}")
