# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
