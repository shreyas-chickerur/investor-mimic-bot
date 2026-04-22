# Investor Mimic Bot

**4-strategy quantitative trading system with regime-aware risk, news sentiment filtering, and full broker reconciliation.**

[![Paper Trading](https://img.shields.io/badge/Status-Paper%20Trading-blue)](https://app.alpaca.markets/paper/dashboard/overview)
[![Automated](https://img.shields.io/badge/Execution-Automated%20Daily-green)](.github/workflows/daily_trading.yml)

---

## What This Does

Automated quantitative trading system running **4 independent strategies** on **36 large-cap US stocks** (S&P 500 core). Executes daily at **4:15 PM ET** via GitHub Actions and emails a full digest.

| Strategy | Signal Edge | Profit Target | Stop Loss | Hold Period |
|---|---|---|---|---|
| **RSI Mean Reversion** | RSI < 40 turning up; sells RSI > 55 or 20d | — | 2.5× ATR | Up to 20 days |
| **ML Momentum** | LightGBM (fallback: GradientBoosting) on 12 OHLCV+indicator features; calibrated top-k entries on P(5d gain) | — | 2.5× ATR | 5 days |
| **Earnings Drift (PEAD)** | Volume spike + abnormal return as earnings proxy | 20% | 10% | Up to 40 days |
| **Factor Momentum** | Cross-sectional rank: momentum/quality/reversion/volume; top 5 | 12% | 8% | Up to 20 days |

**News Sentiment Filter** (Google News RSS + VADER, no API key required):
- Score > 0.62 → boost signal confidence ×1.15
- Score < 0.38 → suppress signal confidence ×0.80
- Score < 0.20 → drop BUY signal entirely

- **15 years of split-adjusted historical data** (Alpha Vantage, 2011–present)
- **Dynamic capital allocation** — Sharpe-ratio-weighted per strategy, rebalances weekly
- **Portfolio-level risk**: correlation filter, regime-dependent heat cap, 2.5× ATR stop losses
- **Broker reconciliation** before every run — blocks trading on any position mismatch

---

## Quick Start (Local)

### Prerequisites
```bash
# 1. Clone and install
git clone https://github.com/shreyas-chickerur/investor-mimic-bot
cd investor-mimic-bot
make install

# 2. Configure credentials
cp .env.example .env
# Edit .env — fill in ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPHA_VANTAGE_API_KEY
```

### First-Time Setup
```bash
make init          # Initialize SQLite database
make fetch-data    # Fetch 15 years of split-adjusted OHLCV data (~5 min, premium AV key)
make check-health  # Verify all imports and system health
make news-test     # Confirm news sentiment is fetching live headlines
```

### Daily Use
```bash
make run           # Execute all 4 strategies (paper trading)
make run-dry       # Dry run — generate signals only, no orders
make status        # One-stop dashboard: positions, P&L, strategy weights
make signals-check # Preview today's signals before market close
make metrics       # Detailed multi-strategy performance report
make dashboard     # Streamlit visual dashboard (localhost:8501)
make logs          # Tail last 50 lines of execution log
```

---

## Makefile Reference

Run `make help` to see all commands with descriptions.

### Setup & Installation
| Command | Description |
|---|---|
| `make install` | Install all Python dependencies from requirements.txt |
| `make install-news` | Install VADER sentiment package (included in main install) |
| `make init` | Initialize SQLite database schema |
| `make setup` | Full setup: install + init + fetch-data |
| `make check-health` | Verify all imports resolve and system is healthy |

### Trading
| Command | Description |
|---|---|
| `make run` | Execute trading system (paper mode) |
| `make run-dry` | Dry run — signals generated, no orders submitted |
| `make signals-check` | Preview today's signals without trading |
| `make status` | One-stop dashboard: positions, P&L, allocations |
| `make dashboard` | Launch Streamlit visual dashboard on port 8501 |
| `make close-positions` | **Emergency**: close all open positions immediately |
| `make logs` | View last 50 lines of `logs/multi_strategy.log` |

### Data Management
| Command | Description |
|---|---|
| `make fetch-data` | Full 15-year historical fetch (first-time or annual refresh) |
| `make update-data` | Incremental daily data append (runs automatically in CI) |
| `make sync-broker` | Sync local DB positions with Alpaca account |
| `make clean-data` | Remove local CSV and model files |

### Analysis & Reporting
| Command | Description |
|---|---|
| `make report` | 30-day strategy performance report |
| `make backtest` | Walk-forward backtest across all 4 strategies |
| `make metrics` | Live portfolio metrics (CAGR, Sharpe, drawdown) |
| `make email-test` | Preview daily email digest as HTML |
| `make analyze` | Analyze signal flow without executing trades |
| `make news-test` | Test live news fetch + VADER sentiment for 6 symbols |

### Validation & Debugging
| Command | Description |
|---|---|
| `make validate` | Validate DB invariants for latest run |
| `make verify` | Verify execution criteria were met |
| `make check-broker` | Show Alpaca account state and positions |
| `make import-check` | Verify all module imports resolve cleanly |
| `make debug-signal` | Trace a single signal through the full pipeline |

### Testing
| Command | Description |
|---|---|
| `make test` | Run all tests |
| `make test-unit` | Unit tests only (fast, ~10s) |
| `make test-integration` | Integration tests |
| `make test-coverage` | Tests with HTML coverage report |

### Maintenance
| Command | Description |
|---|---|
| `make clean` | Remove logs, `__pycache__`, `.pyc`, pytest cache |
| `make clean-all` | Deep clean including DB — run `make init` after |
| `make format` | Format with black (line length 100) |
| `make lint` | Lint with flake8 |
| `make type-check` | mypy type check on `src/` |

---

## Project Structure

```
investor-mimic-bot/
├── .github/workflows/      # GitHub Actions CI/CD
│   ├── daily_trading.yml   # Main daily execution (4:15 PM ET)
│   └── resend_email.yml    # Manual email resend
├── config/
│   └── trading_config.yaml # All strategy + risk parameters
├── dashboard/              # Streamlit visual dashboard
├── data/                   # Market data (gitignored — stored as CI artifact)
├── scripts/                # Utility and maintenance scripts
├── src/
│   ├── core/               # MultiStrategyRunner, TradingDatabase, CashManager
│   ├── data/               # DataQualityChecker, UniverseProvider
│   ├── integration/        # PendingSignalsManager, BrokerExecutor
│   ├── monitoring/         # PnLCalculator, StrategyHealthScorer, SignalFunnelTracker
│   ├── regime/             # RegimeDetector, DynamicAllocator
│   ├── risk/               # PortfolioRiskManager, StopLossManager, BrokerReconciler
│   ├── strategies/         # RSI, MLMomentum, EarningsDrift, FactorMomentum
│   └── utils/              # news_sentiment, correlation_filter, structured_logger
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── component/
│   └── functional/
├── .env                    # Local credentials (never committed)
├── .env.example            # Credential template
├── Makefile                # All commands
├── pyproject.toml          # Build config and dependencies
└── requirements.txt        # Pinned dependencies
```

---

## Trading Strategies

### 1. RSI Mean Reversion
- **Entry**: RSI(14) < 40 with slope > 0 (momentum turning up); news sentiment ≥ 0.38
- **Exit**: RSI > 55 OR 20-day hold period
- **Position sizing**: ATR-based, 2.5× ATR catastrophe stop
- **Universe**: All 36 symbols

### 2. ML Momentum
- **Model**: `LightGBM` (`LGBMClassifier`); fallback to `GradientBoostingClassifier` when LightGBM is unavailable
- **Features**: RSI, returns (5d/20d/60d), volatility (60d), volume ratio, price-to-SMA (20/50), SMA ratio, MACD signal, ATR ratio, Bollinger width + position (12 total)
- **Entry**: P(positive 5d return) above confidence floor with daily calibrated top-k selection; news sentiment ≥ 0.20
- **Exit**: 5-day hold period
- **Training**: Rolling walk-forward on 15 years of split-adjusted data

### 3. Earnings Drift (PEAD)
- **Entry**: Abnormal return > 3% + volume > 1.5× average on same day (earnings proxy)
- **Exit**: 20% profit target, 10% stop loss, or 40-day hold
- **Universe**: All 36 symbols

### 4. Factor Momentum
- **Factors**: 12-month momentum (40%), quality proxy (20%), short-term reversion (20%), volume trend (20%)
- **Entry**: Top 5 ranked symbols by composite score
- **Exit**: 12% profit target, 8% stop loss, or 20-day rebalance
- **Universe**: All 36 symbols

---

## Risk Management

### Portfolio-Level Controls
| Control | Value |
|---|---|
| Heat cap (max exposure) | 50% LOW\_VOL / 40% NORMAL / 30% HIGH\_VOL |
| Daily loss circuit breaker | −5% |
| Correlation filter | Reject if >0.8 with existing positions |
| Position sizing | ATR-based, volatility-adjusted |
| Catastrophe stop loss | 2.5× ATR (re-initialized on every startup) |
| Data quality gate | Blocks symbols with >10% NaN, stale >72h, or price outliers |

### Regime Detection
| Regime | VIX Proxy | Heat Cap | Behavior |
|---|---|---|---|
| `LOW_VOL` | < 15 | 50% | All strategies active |
| `NORMAL` | 15–25 | 40% | Standard execution |
| `HIGH_VOL` | > 25 | 30% | Defensive, reduced sizing |

### Dynamic Capital Allocation
- Each strategy starts with equal 25% of portfolio
- After sufficient history, weights rebalance weekly by Sharpe ratio
- Min weight: 10% / Max weight: 40% per strategy

### Broker Reconciliation
- Compares local DB positions vs Alpaca account before every run
- Blocks all trading if any position mismatch >1%
- Fix mismatches: `make sync-broker`

---

## GitHub Actions Setup

The system runs fully automatically. Two workflows:

### Daily Trading (`daily_trading.yml`)
- **Schedule**: Mon–Fri at 4:15 PM ET (21:15 UTC)
- **Steps**: Download DB artifact → Update market data → Reconcile broker → Run strategies → Upload DB + training data → Send email digest
- **Manual trigger**: Actions → Daily Trading Execution → Run workflow

### Required GitHub Secrets

Go to: **Settings → Secrets and variables → Actions**

| Secret | Required | Description |
|---|---|---|
| `ALPACA_API_KEY` | ✅ | Alpaca paper trading API key |
| `ALPACA_SECRET_KEY` | ✅ | Alpaca secret key |
| `ALPHA_VANTAGE_API_KEY` | ✅ | Premium key for market data (parallel fetch) |
| `SENDER_EMAIL` | Optional | Gmail address for email digests |
| `SENDER_PASSWORD` | Optional | Gmail app password (not account password) |
| `RECIPIENT_EMAIL` | Optional | Where to receive daily digests |

---

## Environment Variables (`.env`)

```bash
# Alpaca — paper trading
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_PAPER=true
ALPACA_LIVE_ENABLED=false

# Alpha Vantage — market data
ALPHA_VANTAGE_API_KEY=your_key

# Email digest (optional)
SENDER_EMAIL=you@gmail.com
SENDER_PASSWORD=your_app_password
RECIPIENT_EMAIL=you@gmail.com

# Execution controls (defaults shown)
DRY_RUN=false
TRADING_DISABLED=false
ENABLE_BROKER_RECONCILIATION=true
DATA_VALIDATOR_MAX_AGE_HOURS=288
```

---

## License

MIT
