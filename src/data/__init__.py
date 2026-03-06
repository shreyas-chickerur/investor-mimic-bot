"""Data fetching and validation components."""
from __future__ import annotations

__all__ = ['AlpacaDataFetcher', 'AlphaVantageFetcher', 'VIXDataFetcher', 'DataValidator', 'DataQualityChecker', 'UniverseProvider']

_lazy_map = {
    'AlpacaDataFetcher':    ('src.data.alpaca_data_fetcher',   'AlpacaDataFetcher'),
    'AlphaVantageFetcher':  ('src.data.alpha_vantage_fetcher', 'AlphaVantageFetcher'),
    'VIXDataFetcher':       ('src.data.vix_data_fetcher',      'VIXDataFetcher'),
    'DataValidator':        ('src.data.data_validator',        'DataValidator'),
    'DataQualityChecker':   ('src.data.data_quality_checker',  'DataQualityChecker'),
    'UniverseProvider':     ('src.data.universe_provider',     'UniverseProvider'),
}


def __getattr__(name: str) -> object:
    if name in _lazy_map:
        import importlib
        mod, cls = _lazy_map[name]
        return getattr(importlib.import_module(mod), cls)
    raise AttributeError(f"module 'src.data' has no attribute {name!r}")
