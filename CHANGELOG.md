# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed - Production Bug Fixes (GitHub Actions log analysis)

- **`initialize_strategies`**: Enforces canonical 4-strategy set (RSI Mean Reversion, ML
  Momentum, Earnings Drift, Factor Momentum). Old DB entries for disabled strategies
  (News Sentiment, MA Crossover, Volatility Breakout) are now ignored; missing canonical
  strategies are created on the fly. Fixes EarningsDrift + FactorMomentum never running.
- **Wash trade prevention**: Added `symbols_bought_this_run` / `symbols_sold_this_run`
  per-run sets in `MultiStrategyRunner`. BUY is skipped if the symbol was sold in the
  same run, and SELL is skipped if the symbol was bought in the same run. Fixes Alpaca
  "potential wash trade detected" rejections for cross-strategy conflicts.
- **Duplicate stop-loss log**: Removed the redundant `logger.info("Stop loss set…")`
  in `_execute_strategy_trades`; `StopLossManager.set_stop_loss` already logs it.
  Also corrects the wrong "3x ATR" label (actual multiplier is 2.5x).
- **VIX hardcoded 18.0**: `RegimeDetector.get_vix_level` now computes 20-day annualized
  realized volatility of the market proxy as a VIX proxy (100 × σ_ann). Falls back to
  18.0 only when market data is unavailable or insufficient. `get_status` and
  `get_regime_adjustments` both forward `market_data` to the new signature.
- **`setup_database.py` schema mismatch**: Positions table now includes
  `current_price`, `market_value`, `unrealized_pnl`, `stop_loss_price`, `entry_date`
  columns and changes `shares` from INTEGER to REAL — matching `database.py`.
- **Signal reasoning chains in daily email**: `generate_daily_email.py` now queries
  today's signals (with `reasoning` and `terminal_state`) grouped by strategy and
  renders a "Signal Reasoning Chains" section for all 4 active strategies.
- **Duplicate log lines**: Added `force=True` to `logging.basicConfig` in
  `execution_engine.py` so imported modules that also call `basicConfig` cannot stack
  extra handlers on the root logger.

### Added - Daily Email Signal Reasoning Flowcharts

- Daily execution email now includes a **Signal Reasoning Flowcharts** section for
  news-linked signals (event chain format: `event -> event -> ... -> signal`).
- News Sentiment strategy signals now attach top news headlines (`news_events`) so
  downstream reporting can explain article-to-signal causality.
- News sentiment provider now exposes structured sentiment context
  (`score + top headlines`) while preserving the existing score API.
- Added component tests for flowchart rendering and HTML escaping in email output.

### Added - Walk-Forward Backtesting & New Alpha Sources

#### Walk-Forward Portfolio Backtester
- Continuous simulation mode: positions carry across windows, no forced closes
- ML models retrain only at window boundaries (proper walk-forward validation)
- Per-symbol cooldown (10 days) prevents re-entry churn
- Minimum hold period (2 days) prevents same-day round-trips
- Portfolio-level confidence filter (0.60 min) and max 3 buys/day
- 5x ATR catastrophe-only stop losses (reduced from 2.5x)

#### New Strategies
- **Earnings Drift (PEAD)**: Detects earnings events via volume spike + abnormal
  return proxy, buys positive surprises, holds for 40-day drift period.
  79.2% win rate in walk-forward backtest.
- **Factor Momentum**: Cross-sectional ranking by composite score (momentum,
  quality proxy, mean-reversion, volume confirmation), buys top 5 stocks,
  holds 20 days. 62.7% win rate in walk-forward backtest.

#### ML Pipeline Rewrite
- 12 features: multi-timeframe momentum (5/10/20/60d), volatility regime,
  volume dynamics, mean-reversion signals (RSI slope), trend strength (ADX)
- LogisticRegression with C=0.1 regularization (replaced overfitting GradientBoosting)
- Proper train/test split via walk-forward windows (no lookahead bias)

#### Tests
- 22 new tests for EarningsDrift and FactorMomentum strategies
- Unit tests, edge cases, integration tests with real market data

### Changed

#### Strategy Mix
- Replaced MA Crossover and News Sentiment with Earnings Drift and Factor Momentum
- Registered new strategies in execution engine for live trading
- Updated `_create_strategy_instance` map for DB-backed strategy loading

#### Backtester Improvements
- Fixed critical bug: backtester now syncs `strat.positions` on all sell paths
  (signal sells + stop losses), preventing strategies from going dormant
- Increased max positions per strategy from 3 to 5
- Walk-forward backtest result (5yr, 2020-2025): +3.96% return vs -6.7%
  buy-and-hold, 0.24 Sharpe, 1.29 profit factor, 54.1% win rate

### Added - Industrial Grade Improvements

#### Dependency Management
- Added `pyproject.toml` for modern Python project configuration
- Implemented dependency version pinning for reproducibility
- Added automated dependency vulnerability scanning
- Weekly dependency update checks via GitHub Actions

#### Code Quality & Standards
- Pre-commit hooks for automated code quality checks
  - Black for code formatting (100 char line length)
  - Ruff for linting (replaces flake8, isort, pyupgrade)
  - mypy for type checking
  - Bandit for security scanning
  - Safety for dependency vulnerability checks
- Comprehensive CI/CD workflow for pull requests
  - Code quality checks
  - Security scanning
  - Type checking
  - Code complexity analysis
  - Documentation validation

#### Data Validation
- Pydantic schemas for formal data validation
  - `MarketDataSchema` - Validates OHLCV data and indicators
  - `SignalSchema` - Validates trading signals
  - `TradeSchema` - Validates executed trades
  - `PortfolioStateSchema` - Validates portfolio state
- Automated data integrity checks

#### Contribution Guidelines
- `CONTRIBUTING.md` with comprehensive guidelines
- `CODEOWNERS` file for required code reviews
- Pull request template with detailed checklist
- Commit message conventions (Conventional Commits)
- Code review requirements and process

#### Monitoring & Observability
- Dependency update monitoring
- Security vulnerability alerts
- Code coverage tracking (minimum 60%)
- Complexity metrics monitoring

### Changed

#### Strategy Optimizations
- RSI Mean Reversion: Buy threshold 35→40, Sell threshold 50→60
- ML Momentum: Fixed feature mismatch error (5→3 features)
- Data filtering: 2010-present only, COVID crash period excluded

#### Data Management
- Historical data window: 100→150 days for indicator calculation
- Data quality checks: Updated for sma_200 support (35% NaN threshold)

#### Workflow Improvements
- Removed test workflow (tests run locally)
- Added daily performance monitoring workflow
- Email alerts only on failures (no daily spam)

### Fixed
- Import path errors in multiple scripts
- `make install` command (pip→python3 -m pip)
- `make analyze` date column ambiguity error
- All Makefile commands now working correctly

## [1.0.0] - 2026-01-26

### Added
- Multi-strategy trading system (5 strategies)
- 32 large-cap US stocks universe
- Automated daily execution (4:15 PM EST)
- Portfolio-level risk management
- Regime-aware allocation
- Broker reconciliation
- Daily performance monitoring
- Email notifications

### Strategies
1. RSI Mean Reversion
2. MA Crossover
3. ML Momentum
4. Volatility Breakout
5. News Sentiment

### Risk Management
- 50% max portfolio heat
- 5% daily loss limit
- 0.8 correlation filter
- ATR-based position sizing
- 2.5x ATR stop losses
- Data quality checks

[Unreleased]: https://github.com/shreyas-chickerur/investor-mimic-bot/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/shreyas-chickerur/investor-mimic-bot/releases/tag/v1.0.0
