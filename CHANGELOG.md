# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Platform Improvements A–G (2026-05-22)

- **A — Equal capital normalization**: Capital now normalized each run as
  `deployed_capital_pct (0.85) × portfolio_value / N active strategies`, ensuring all
  strategies are always comparable regardless of when they were created. Added
  `update_strategy_capital_allocation()` to `TradingDatabase` and `deployed_capital_pct`
  config key.
- **B — Regime-conditional strategy weights (REGIME_WEIGHT_TABLE)**: Replaced scattered
  if/elif regime chains with an explicit table mapping 5 regimes (TRENDING_BULL, RANGING,
  HIGH_VOL, LOW_VOL, NORMAL) to per-strategy additive weight deltas. Legacy vol/trend
  logic retained only as NORMAL fallback. Output clamped to [0.5, 1.5].
- **C — Confidence-scaled position sizing**: Linear interpolation on signal confidence:
  conf=0.55→0.75× size, conf=0.90→1.25× size. Clamps at both ends; replaces flat 50–100%
  clamp. Applied in execution engine before order submission.
- **D — Kelly fractional rebalancing**: Quarter-Kelly (0.25×f*) applied to strategy weights
  once a strategy accumulates ≥ 20 closed trades. f* = p − (1−p)/b where p is win rate
  and b is avg win / avg loss. Neutral (1.0×) for all strategies below the trade threshold.
- **E — 5-regime composite detector**: `detect_composite_regime()` added to `RegimeDetector`.
  Uses VIX thresholds first; then ADX (Wilder-smoothed, period 14) and market breadth
  (fraction of symbols above 20-day SMA) to distinguish TRENDING_BULL vs RANGING vs NORMAL
  when VIX is 15–25. Explicit NORMAL fallback when market data is absent.
- **F — Platform status report**: `scripts/generate_platform_status.py` generates
  `artifacts/platform_status.md` on every GHA run (after trading, before artifact upload).
  Includes portfolio snapshot, system health, per-strategy status table, regime→weight
  mapping, and Kelly state.
- **G — Per-strategy backtest CLI**: `scripts/run_backtest.py --per-strategy` runs each of
  the 6 backtestable strategies in isolation, compares results, writes
  `artifacts/backtest/per_strategy_results.json` and per-strategy equity curves. Triggered
  automatically on Mondays (3-year walk-forward).

### Fixed - Critical Strategy Logic (Paper Trading Performance)

- **RSI VWAP exit bug**: The `vwap` column in training data is a trailing 20-day VWAP
  (always ~70% of current close), so `price >= vwap` fired on *every* position, causing
  immediate same-day exits and zero holding periods. Removed VWAP exit entirely;
  exits are now RSI > 55 (mean reversion complete) or 20-day time exit.
- **Factor Momentum ranking collapse**: `_rank_normalize(sigmoid(value))` applied
  independently to each symbol compressed all composite scores into 0.50–0.65,
  making "top 5" selection nearly random. Replaced with proper cross-sectional
  percentile ranking (`DataFrame.rank(pct=True)` across the universe), giving
  a score spread of 0.0–1.0 that actually reflects relative standing.
- **ML Momentum signal blackout**: `min_confidence=0.55` blocked all signals because
  logistic regression on noisy financial data rarely produces probabilities > 0.55.
  Lowered to 0.52. Added `class_weight='balanced'` to handle class imbalance. Daily
  retraining (controlled by `_train_date`) to keep model current. Future return
  threshold lowered from 1% to 0.5% to provide more balanced training labels.
  Uses pre-computed `future_return_5d` column from training data when available.
- **Signal throttle killing Factor Momentum**: Hardcoded `signals[:3]` cut every
  strategy to 3 signals. Changed to `signals[:max_signals]` where `max_signals =
  getattr(strategy, 'top_n', 5)`, allowing Factor Momentum to execute its full 5.
- **ML config sync**: `config/trading_config.yaml` `min_confidence` updated to 0.52.

### Added - News Sentiment Integration

- **`src/utils/news_sentiment.py`** fully rewritten:
  - `fetch_symbol_news(symbol)`: fetches headlines from yfinance, scores each title
    with VADER sentiment analyzer (falls back to keyword matching if VADER unavailable)
  - `NewsSentimentProvider`: batch-fetches N symbols in parallel (ThreadPoolExecutor),
    caches results for the calendar day to avoid redundant API calls
  - `NewsSignalFilter.apply(signals, sentiment_map)`: applies as confidence modifier —
    score > 0.62 → ×1.15, score < 0.38 → ×0.80, score < 0.25 + BUY → signal dropped
    SELL signals are never dropped regardless of sentiment
- **Execution engine integration**: `_news_filter` pre-fetches sentiment for all signal
  symbols after the correlation filter; applied before execution for all 4 strategies
- Added `yfinance==0.2.36` and `vaderSentiment==3.3.2` to `requirements.txt`
- New Makefile targets: `news-test`, `install-news`

### Added - Test Suite for Strategy Logic

- `tests/unit/test_strategy_logic.py`: 23 targeted tests covering all critical fixes:
  - RSI: VWAP exit regression test, buy/no-buy conditions, RSI exit, time exit
  - Factor Momentum: score spread assertion, ranking direction, top_n enforcement
  - ML Momentum: confidence threshold, class_weight, daily retraining, training classes
  - Earnings Drift: event detection, positive/negative surprise routing
  - News filter: boost/suppress/drop logic, SELL signal preservation

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

### Changed - Strategy Mix and Configuration

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

### Changed - Strategy Optimizations

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
