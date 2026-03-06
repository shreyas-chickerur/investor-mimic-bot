"""Utility components."""
from __future__ import annotations

__all__ = ['EmailNotifier', 'ExecutionCostModel', 'KillSwitchService', 'get_config']

_lazy_map = {
    'EmailNotifier':    ('src.utils.email_notifier',  'EmailNotifier'),
    'ExecutionCostModel': ('src.utils.execution_costs', 'ExecutionCostModel'),
    'KillSwitchService': ('src.utils.kill_switch_service', 'KillSwitchService'),
    'get_config':       ('src.utils.config_loader',   'get_config'),
}


def __getattr__(name: str) -> object:
    if name in _lazy_map:
        import importlib
        mod, obj = _lazy_map[name]
        return getattr(importlib.import_module(mod), obj)
    raise AttributeError(f"module 'src.utils' has no attribute {name!r}")
