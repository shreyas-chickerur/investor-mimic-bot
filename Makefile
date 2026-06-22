.PHONY: help install install-news setup init fetch-data update-data sync-broker clean-data diagnose diagnose-local \
	run run-dry logs shell status close-positions \
	test test-unit test-integration test-component test-functional test-coverage test-watch \
	report analyze backtest metrics email-test signals-check news-test \
	validate verify check-broker check-health debug-signal import-check \
	clean clean-all clean-cache format lint type-check \
	dev-setup dev-test dev-run \
	web-mock web-mock-healthy web-mock-recovered web-mock-needs-action web-export web-validate \
	web-dev web-dev-live snapshot snapshot-mock expect-check

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

help:
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║     Investor Mimic Bot — 4-Strategy Quant Trading System      ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)📦 SETUP & INSTALLATION$(NC)"
	@echo "  make install          Install all Python dependencies"
	@echo "  make install-news     Install news/sentiment extras (yfinance + VADER)"
	@echo "  make init             Initialize database schema"
	@echo "  make setup            Full setup (install + init + fetch-data)"
	@echo "  make check-health     Verify imports and system health"
	@echo ""
	@echo "$(GREEN)🌐 WEB DASHBOARD$(NC)"
	@echo "  make web-dev          Run dev server with mock data (http://localhost:3000)"
	@echo "  make web-dev-live     Run dev server with live snapshot data"
	@echo "  make web-export       Export latest.json from live DB"
	@echo "  make web-validate     Validate latest.json against schema"
	@echo "  make web-mock         Export all 3 mock health states"
	@echo "  make snapshot         Print live snapshot summary (text)"
	@echo "  make snapshot-mock    Print mock snapshot summary (text)"
	@echo "  make expect-check     Run post-run expectation checks (paste output to Claude)"
	@echo ""
	@echo "$(GREEN)🚀 TRADING$(NC)"
	@echo "  make run              Execute trading (paper mode)"
	@echo "  make run-dry          Dry run — no orders submitted"
	@echo "  make signals-check    Preview today's signals without trading"
	@echo "  make status           One-stop system status dashboard"
	@echo "  make logs             View last 50 log lines"
	@echo "  make close-positions  Close all open positions (emergency)"
	@echo ""
	@echo "$(GREEN)📰 NEWS & SENTIMENT$(NC)"
	@echo "  make news-test        Test news fetch + sentiment for sample symbols"
	@echo ""
	@echo "$(GREEN)🧪 TESTING$(NC)"
	@echo "  make test             Run all tests"
	@echo "  make test-unit        Run unit tests only (fast)"
	@echo "  make test-integration Run integration tests"
	@echo "  make test-coverage    Run tests with HTML coverage report"
	@echo ""
	@echo "$(GREEN)📊 DATA MANAGEMENT$(NC)"
	@echo "  make fetch-data       Fetch full historical data (15 years)"
	@echo "  make update-data      Incremental daily data update"
	@echo "  make sync-broker      Sync local DB with Alpaca positions"
	@echo "  make clean-data       Remove cached data files"
	@echo ""
	@echo "$(GREEN)📈 ANALYSIS & REPORTING$(NC)"
	@echo "  make report           30-day strategy performance report"
	@echo "  make email-test       Preview daily email HTML locally"
	@echo "  make analyze          Analyze canonical strategy signals (no trading)"
	@echo "  make backtest         Walk-forward backtest"
	@echo "  make metrics          Live portfolio metrics"
	@echo ""
	@echo "$(GREEN)✅ DEBUGGING$(NC)"
	@echo "  make validate         Validate system invariants"
	@echo "  make check-broker     Check Alpaca broker state"
	@echo "  make debug-signal     Debug single signal flow"
	@echo "  make import-check     Verify all imports resolve"
	@echo ""
	@echo "$(GREEN)🧹 MAINTENANCE$(NC)"
	@echo "  make clean            Remove logs, caches, temp files"
	@echo "  make clean-all        Deep clean (removes DB — run 'make init' after)"
	@echo "  make format           Format code with black"
	@echo "  make lint             Lint with flake8"
	@echo "  make type-check       mypy type check"
	@echo ""

# ============================================================================
# SETUP & INSTALLATION
# ============================================================================

install:
	@echo "$(BLUE)📦 Installing Python dependencies...$(NC)"
	@python3 -m pip install --upgrade pip
	@python3 -m pip install -r requirements.txt
	@echo "$(GREEN)✅ Dependencies installed$(NC)"

install-news:
	@echo "$(BLUE)📰 Installing news/sentiment extras...$(NC)"
	@python3 -m pip install yfinance vaderSentiment
	@echo "$(GREEN)✅ News dependencies installed$(NC)"

init:
	@echo "$(BLUE)🗄️  Initializing database...$(NC)"
	@python3 scripts/setup_database.py --db trading.db
	@echo "$(GREEN)✅ Database initialized$(NC)"

fetch-data:
	@echo "$(BLUE)📥 Fetching historical market data (15 years)...$(NC)"
	@set -a && source .env && set +a && python3 scripts/fetch_historical_data.py
	@echo "$(GREEN)✅ Market data fetched$(NC)"

setup: install init fetch-data
	@echo "$(GREEN)✅ Setup complete! Run 'make run' to start trading.$(NC)"

check-health:
	@echo "$(BLUE)🏥 Checking system health...$(NC)"
	@python3 scripts/import_check.py
	@python3 scripts/local_health_check.py
	@echo "$(GREEN)✅ System health check complete$(NC)"

# ============================================================================
# DEVELOPMENT
# ============================================================================

run:
	@echo "$(BLUE)🚀 Running trading system...$(NC)"
	@set -a && source .env && set +a && export ENABLE_BROKER_RECONCILIATION=true && python3 src/core/execution_engine.py
	@echo "$(GREEN)✅ Execution complete$(NC)"

run-dry:
	@echo "$(BLUE)🧪 Running in DRY RUN mode (no actual trades)...$(NC)"
	@set -a && source .env && set +a && export DRY_RUN=true && python3 src/core/execution_engine.py
	@echo "$(GREEN)✅ Dry run complete$(NC)"

logs:
	@echo "$(BLUE)📋 Recent trading logs:$(NC)"
	@tail -50 logs/multi_strategy.log 2>/dev/null || echo "$(YELLOW)No logs yet$(NC)"

shell:
	@echo "$(BLUE)🐍 Opening Python shell with sys.path configured...$(NC)"
	@python3 -c "import sys; sys.path.insert(0, '.'); import src; print('src/ on path — import freely'); \
	__import__('IPython').embed()" 2>/dev/null || \
	python3 -i -c "import sys; sys.path.insert(0, '.'); print('src/ on path. Try: from src.core.database import TradingDatabase')"

# ============================================================================
# TESTING
# ============================================================================

test:
	@echo "$(BLUE)🧪 Running fast tests (use 'make test-all' to include slow/real-data tests)...$(NC)"
	@python3 -m pytest tests/unit/ tests/component/ --durations=5
	@echo "$(GREEN)✅ Fast tests passed$(NC)"

test-all:
	@echo "$(BLUE)🧪 Running full test suite (including slow/real-data tests)...$(NC)"
	@python3 -m pytest tests/ -m "" --durations=10
	@echo "$(GREEN)✅ All tests passed$(NC)"

test-unit:
	@echo "$(BLUE)🧪 Running unit tests...$(NC)"
	@python3 -m pytest tests/unit/ --durations=5
	@echo "$(GREEN)✅ Unit tests passed$(NC)"

test-integration:
	@echo "$(BLUE)🧪 Running integration tests...$(NC)"
	@python3 -m pytest tests/integration/ -v --tb=short
	@echo "$(GREEN)✅ Integration tests passed$(NC)"

test-component:
	@echo "$(BLUE)🧪 Running component tests...$(NC)"
	@python3 -m pytest tests/component/ --durations=5
	@echo "$(GREEN)✅ Component tests passed$(NC)"

test-functional:
	@echo "$(BLUE)🧪 Running functional tests...$(NC)"
	@python3 -m pytest tests/functional/ -v --tb=short
	@echo "$(GREEN)✅ Functional tests passed$(NC)"

test-coverage:
	@echo "$(BLUE)📊 Running tests with coverage...$(NC)"
	@python3 -m pytest tests/ -m "" --cov=src --cov-report=html --cov-report=term
	@echo "$(GREEN)✅ Coverage report generated: htmlcov/index.html$(NC)"

test-watch:
	@echo "$(BLUE)👀 Running tests in watch mode...$(NC)"
	@python3 -m pytest tests/unit/ tests/component/ -f

# ============================================================================
# DATA MANAGEMENT
# ============================================================================

update-data:
	@echo "$(BLUE)📥 Updating market data...$(NC)"
	@set -a && source .env && set +a && python3 scripts/update_daily_data.py
	@echo "$(GREEN)✅ Market data updated$(NC)"

sync-broker:
	@echo "$(BLUE)🔄 Syncing database with broker...$(NC)"
	@python3 scripts/sync_broker_state.py
	@echo "$(GREEN)✅ Database synced$(NC)"

clean-data:
	@echo "$(BLUE)🧹 Cleaning cached data...$(NC)"
	@rm -rf data/*.csv data/*.pkl
	@echo "$(GREEN)✅ Data cache cleaned$(NC)"

# ============================================================================
# ANALYSIS & REPORTING
# ============================================================================

report:
	@echo "$(BLUE)📊 Generating performance report...$(NC)"
	@python3 scripts/generate_strategy_performance.py --days 30
	@echo "$(GREEN)✅ Report generated$(NC)"

analyze:
	@echo "$(BLUE)🔍 Analyzing canonical strategy signals (no trading)...$(NC)"
	@set -a && source .env && set +a && python3 scripts/check_signals.py
	@echo "$(GREEN)✅ Analysis complete$(NC)"

backtest:
	@echo "$(BLUE)📊 Running walk-forward backtest...$(NC)"
	@python3 scripts/run_backtest.py
	@echo "$(GREEN)✅ Backtest complete$(NC)"

metrics:
	@echo "$(BLUE)📈 Portfolio metrics:$(NC)"
	@python3 scripts/view_performance.py

# --- Strategy experiments (disabled-strategy revival tracking) ---
screen-pairs:
	@echo "$(BLUE)🔎 Screening universe for tradeable pairs...$(NC)"
	@python3 scripts/research/screen_pairs.py

eval-ml-features:
	@echo "$(BLUE)🧪 Purged walk-forward: baseline vs enriched ML features...$(NC)"
	@python3 scripts/research/eval_ml_features.py

strategy-review:
	@echo "$(BLUE)🧪 Reviewing strategy experiments (all pending)...$(NC)"
	@python3 scripts/research/review_experiments.py --all $(if $(DB),--db $(DB),)

email-test:
	@echo "$(BLUE)📧 Generating email preview...$(NC)"
	$(if $(STATE), \
		python3 scripts/generate_daily_email.py --mock-state $(STATE), \
		python3 scripts/generate_daily_email.py)
	@open /tmp/daily_email.html 2>/dev/null || xdg-open /tmp/daily_email.html 2>/dev/null || echo "Email HTML at /tmp/daily_email.html"
	@echo "$(GREEN)✅ Email preview ready$(NC)"

status:
	@echo "$(BLUE)📊 System status dashboard...$(NC)"
	@python3 scripts/status.py

close-positions:
	@echo "$(RED)⚠️  Closing ALL open positions...$(NC)"
	@set -a && source .env && set +a && python3 scripts/close_all_positions.py

news-test:
	@echo "$(BLUE)📰 Testing news fetch + sentiment...$(NC)"
	@python3 scripts/check_news_sentiment.py

signals-check:
	@echo "$(BLUE)🔍 Checking today's signals (no orders submitted)...$(NC)"
	@set -a && source .env && set +a && python3 scripts/check_signals.py
	@echo "$(GREEN)✅ Signal check complete$(NC)"

# ============================================================================
# VALIDATION & DEBUGGING
# ============================================================================

validate:
	@echo "$(BLUE)✅ Validating system invariants...$(NC)"
	@python3 scripts/validate_system.py --latest

verify:
	@echo "$(BLUE)🔍 Verifying execution criteria...$(NC)"
	@python3 scripts/verify_execution.py

check-broker:
	@echo "$(BLUE)💼 Checking broker state...$(NC)"
	@python3 scripts/check_broker_state.py

debug-signal:
	@echo "$(BLUE)🐛 Debugging signal flow...$(NC)"
	@python3 scripts/debug_single_signal.py

import-check:
	@echo "$(BLUE)🔎 Verifying imports...$(NC)"
	@python3 scripts/import_check.py

# ============================================================================
# MAINTENANCE
# ============================================================================

clean:
	@echo "$(BLUE)🧹 Cleaning temporary files...$(NC)"
	@rm -f logs/*.log
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@rm -rf .pytest_cache .coverage htmlcov/
	@echo "$(GREEN)✅ Cleanup complete$(NC)"

clean-all: clean
	@echo "$(BLUE)🧹 Deep cleaning (including databases)...$(NC)"
	@rm -f trading.db data/*.db
	@echo "$(YELLOW)⚠️  Databases removed - run 'make init' to recreate$(NC)"

clean-cache:
	@echo "$(BLUE)🧹 Cleaning Python cache...$(NC)"
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "$(GREEN)✅ Cache cleaned$(NC)"

format:
	@echo "$(BLUE)🎨 Formatting code with black...$(NC)"
	@python3 -m black src/ tests/ scripts/ --line-length 100
	@echo "$(GREEN)✅ Code formatted$(NC)"

lint:
	@echo "$(BLUE)🔍 Linting code with flake8...$(NC)"
	@python3 -m flake8 src/ tests/ scripts/ --max-line-length 100 --ignore=E203,W503
	@echo "$(GREEN)✅ Linting complete$(NC)"

type-check:
	@echo "$(BLUE)🔍 Type checking with mypy...$(NC)"
	@python3 -m mypy src/ --ignore-missing-imports
	@echo "$(GREEN)✅ Type check complete$(NC)"

# ============================================================================
# DEVELOPMENT HELPERS
# ============================================================================

dev-setup: install init
	@echo "$(GREEN)✅ Development environment ready$(NC)"

dev-test: clean-cache test-unit
	@echo "$(GREEN)✅ Quick test complete$(NC)"

dev-run: clean-cache run-dry
	@echo "$(GREEN)✅ Development run complete$(NC)"

# ============================================================================
# WEB DASHBOARD — snapshot export + validation
# ============================================================================

web-export:
	@echo "$(BLUE)📤 Exporting live snapshot...$(NC)"
	@mkdir -p web/public/data/history
	@python3 scripts/export_snapshot.py
	@echo "$(GREEN)✅ Snapshot exported$(NC)"

web-validate:
	@echo "$(BLUE)🔍 Validating snapshot schema...$(NC)"
	@python3 scripts/validate_snapshot.py
	@echo "$(GREEN)✅ Schema valid$(NC)"

web-mock-healthy:
	@echo "$(BLUE)🟢 Generating HEALTHY mock snapshot...$(NC)"
	@python3 scripts/export_snapshot.py --mock healthy
	@python3 scripts/validate_snapshot.py --file web/public/data/mock/latest.json
	@echo "$(GREEN)✅ healthy  →  web/public/data/mock/$(NC)"

web-mock-recovered:
	@echo "$(BLUE)🟡 Generating AUTO-RECOVERED mock snapshot...$(NC)"
	@python3 scripts/export_snapshot.py --mock auto-recovered
	@python3 scripts/validate_snapshot.py --file web/public/data/mock/latest.json
	@echo "$(GREEN)✅ auto-recovered  →  web/public/data/mock/$(NC)"

web-mock-needs-action:
	@echo "$(BLUE)🔴 Generating NEEDS-ACTION mock snapshot...$(NC)"
	@python3 scripts/export_snapshot.py --mock needs-action
	@python3 scripts/validate_snapshot.py --file web/public/data/mock/latest.json
	@echo "$(GREEN)✅ needs-action  →  web/public/data/mock/$(NC)"

web-mock: web-mock-healthy web-mock-recovered web-mock-needs-action
	@echo ""
	@echo "$(GREEN)✅ All three mock health states generated and validated.$(NC)"
	@echo "$(BLUE)   web/public/data/mock/latest.json    ← needs-action (last written)$(NC)"
	@echo "$(BLUE)   web/public/data/mock/history/       ← all three dated copies$(NC)"
	@echo "$(BLUE)   web/public/data/                    ← UNTOUCHED (real data stays clean)$(NC)"

web-dev: web-mock-healthy
	@echo "$(BLUE)🌐 Starting dev server with MOCK data...$(NC)"
	@echo "$(YELLOW)   Open http://localhost:3000$(NC)"
	@cd web && NEXT_PUBLIC_SNAPSHOT_URL=http://localhost:3000/data/mock/latest.json npm run dev

web-dev-live:
	@echo "$(BLUE)🌐 Starting dev server with LIVE data (from web/public/data/latest.json)...$(NC)"
	@echo "$(YELLOW)   Open http://localhost:3000$(NC)"
	@cd web && NEXT_PUBLIC_SNAPSHOT_URL=http://localhost:3000/data/latest.json npm run dev

snapshot:
	@echo "$(BLUE)📊 Current live snapshot summary:$(NC)"
	@python3 scripts/read_snapshot.py

snapshot-mock:
	@echo "$(BLUE)📊 Mock snapshot summary:$(NC)"
	@python3 scripts/read_snapshot.py --mock

expect-check:
	@echo "$(BLUE)🔍 Post-run expectation check (paste output to Claude if something went wrong):$(NC)"
	@python3 scripts/post_run_expect.py --db trading.db --no-email || true

diagnose:
	@echo "$(BLUE)🩺 Platform diagnosis (fetches latest run artifacts via gh)...$(NC)"
	@python3 scripts/diagnose.py --fetch

diagnose-local:
	@echo "$(BLUE)🩺 Platform diagnosis (local trading.db only)...$(NC)"
	@python3 scripts/diagnose.py --no-gha
