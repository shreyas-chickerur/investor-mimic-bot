# Windsurf Update Summary

This document summarizes the key changes delivered in the recent updates so you can
share them with Windsurf and keep a clear changelog of behavior and safety changes.

## Live runner execution wiring
- **Risk, correlation, allocation, and execution cost handling** are now wired into
  the live runner so trades respect:
  - dynamic allocations by strategy,
  - portfolio heat / daily loss limits,
  - correlation filtering,
  - and realistic execution costs.
- **Live trading safety** is gated by `ALPACA_LIVE_ENABLED=true` when `ALPACA_PAPER=false`.
- **Optional auto data refresh** uses `AUTO_UPDATE_DATA=true` to re-run `scripts/update_data.py`
  if data validation fails.
- **Broker reconciliation** can now be enabled in the live runner with
  `ENABLE_BROKER_RECONCILIATION=true`, pausing trading on mismatches.

## Strategy and analytics changes
- **Per-strategy entry tracking** and `asof_date` metadata are included in signal payloads,
  enabling consistent hold-day exit logic and attribution.
- **ML Momentum** now loads/saves its model and scaler to disk:
  - `data/ml_momentum_model.pkl`
  - `data/ml_momentum_scaler.pkl`
- **News Sentiment** now supports an optional API-based provider while retaining a
  fallback heuristic if no API key is configured.

## Regime detection improvements
- **Market-data-based regime detection** now derives realized volatility and trend
  regime from available price data when VIX is not available.

## Dependency / workflow hardening
- **GitHub Actions** workflow uses `actions/upload-artifact@v4` to avoid v3 deprecation.
- **Optional PyYAML** usage for signal injection is now tolerant when the dependency
  is unavailable.

## New/updated configuration (env vars)
- `ALPACA_LIVE_ENABLED=true` (required for live trading when `ALPACA_PAPER=false`)
- `AUTO_UPDATE_DATA=true` (auto refresh data if validation fails)
- `ENABLE_BROKER_RECONCILIATION=true` (enforce broker reconciliation pre-trade)
- `NEWS_SENTIMENT_PROVIDER=newsapi` (optional sentiment provider)
- `NEWS_API_KEY=...` (required for NewsAPI sentiment)

## Tests
- Full test suite executed with `make test` (58 passed, warnings only).
