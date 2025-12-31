.PHONY: help install run dashboard test clean sync-db view-performance analyze-signals import-check \
	perf-report perf-chart perf-dashboard email-daily email-weekly email-sample \
	validate verify-system check-broker debug-signal backtest fetch-backtest-data run-backtest

# Default target
help:
	@echo "📊 Multi-Strategy Trading System - Available Commands"
	@echo ""
	@echo "🚀 MAIN COMMANDS:"
	@echo "  make run              - Run all 5 trading strategies"
	@echo "  make dashboard        - Open web dashboard (http://localhost:5000)"
	@echo "  make analyze          - Analyze all strategies for signals"
	@echo ""
	@echo "📈 STRATEGY PERFORMANCE:"
	@echo "  make perf-report      - Generate 30-day performance report"
	@echo "  make perf-chart       - Generate performance charts (7 days)"
	@echo "  make perf-dashboard   - Start performance dashboard UI"
	@echo ""
	@echo "📧 EMAIL & NOTIFICATIONS:"
	@echo "  make email-daily      - Generate daily email digest"
	@echo "  make email-weekly     - Generate weekly email with visuals"
	@echo "  make email-sample     - Generate sample email (mock data)"
	@echo "  make email-chart      - Generate performance chart for email"
	@echo ""
	@echo "✅ SYSTEM VALIDATION:"
	@echo "  make validate         - Validate system invariants"
	@echo "  make verify-system    - Verify execution criteria"
	@echo "  make check-broker     - Check broker state"
	@echo "  make import-check     - Verify all modules load"
	@echo ""
	@echo "🐛 ANALYSIS & DEBUGGING:"
	@echo "  make debug-signal     - Debug single signal flow"
	@echo "  make backtest         - Run validation backtest"
	@echo ""
	@echo "📊 BACKTESTING:"
	@echo "  make fetch-backtest-data  - Fetch 15 years historical data"
	@echo "  make run-backtest         - Run walk-forward backtest"
	@echo "  make backtest-full        - Fetch data + run backtest"
	@echo ""
	@echo "📊 MONITORING:"
	@echo "  make view             - View strategy performance (CLI)"
	@echo "  make logs             - View recent trading logs"
	@echo "  make positions        - Check current Alpaca positions"
	@echo ""
	@echo "🔧 DATABASE & DATA:"
	@echo "  make init             - Initialize database schema"
	@echo "  make sync-db          - Sync database with broker"
	@echo "  make update-data      - Update market data"
	@echo "  make fetch-data       - Fetch historical data"
	@echo ""
	@echo "🧪 TESTING:"
	@echo "  make test             - Run all tests"
	@echo "  make test-single      - Test single strategy"
	@echo "  make test-multi       - Test multi-strategy integration"
	@echo ""
	@echo "🧹 MAINTENANCE:"
	@echo "  make clean            - Clean logs and temporary files"
	@echo "  make clean-all        - Deep clean (including databases)"

init:
	@echo "Initializing database..."
	python3 scripts/setup_database.py --db trading.db
	@echo "✅ Database initialized"

fetch-data:
	@echo "Fetching market data (premium API, ~18 seconds)..."
	@set -a && source .env && set +a && python3 scripts/fetch_historical_data.py
	@echo "✅ Market data fetched"

verify-positions:
	@echo "Verifying broker positions..."
	@set -a && source .env && set +a && python3 -c "\
	import sys; \
	sys.path.insert(0, 'src'); \
	from broker_reconciler import BrokerReconciler; \
	r = BrokerReconciler(); \
	s = r.get_broker_state(); \
	print(f'Positions: {len(s[\"positions\"])}'); \
	print(f'Cash: \$${s[\"cash\"]:,.2f}'); \
	exit(0 if len(s['positions']) == 0 else 1)"

run:
	@echo "Running trading execution..."
	@set -a && source .env && set +a && export ENABLE_BROKER_RECONCILIATION=true && python3 src/execution_engine.py
	@echo "✅ Execution complete"

# Single strategy (RSI only)
run-single:
	@echo "🚀 Running single RSI strategy..."
	python3 src/main.py

# Web dashboard
dashboard:
	@echo "📊 Starting web dashboard..."
	@echo "🌐 Open http://localhost:5000 in your browser"
	python3 src/dashboard_server.py

# Analysis
analyze:
	@echo "🔍 Analyzing all strategies for signals..."
	python3 scripts/analyze_signals.py

# Monitoring
view:
	@echo "📊 Strategy Performance Dashboard"
	python3 scripts/view_performance.py

logs:
	@echo "📋 Recent trading logs:"
	@tail -50 logs/multi_strategy.log 2>/dev/null || echo "No logs yet"

positions:
	@echo "💼 Current Alpaca positions:"
	@python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); from alpaca.trading.client import TradingClient; client = TradingClient(os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_SECRET_KEY'), paper=True); positions = client.get_all_positions(); [print(f'{p.symbol}: {p.qty} shares @ \$${p.avg_entry_price}') for p in positions] if positions else print('No positions')"

# Database operations
sync-db:
	@echo "🔄 Syncing database with Alpaca..."
	python3 scripts/sync_database.py

update-data:
	@echo "📥 Updating market data..."
	python3 scripts/update_data.py

# Testing
test:
	@echo "🧪 Running all tests..."
	python3 -m pytest tests/ -v

import-check:
	@echo "🔎 Running import check..."
	python3 scripts/import_check.py

test-single:
	@echo "🧪 Testing single strategy..."
	python3 tests/test_trading_system.py

test-multi:
	@echo "🧪 Testing multi-strategy system..."
	python3 tests/test_integration.py

# Cleanup
clean:
	@echo "🧹 Cleaning logs and temporary files..."
	rm -f logs/*.log
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✅ Cleanup complete"

clean-all: clean
	@echo "🧹 Deep cleaning (including databases)..."
	rm -f data/*.db
	@echo "⚠️  Databases removed - will be recreated on next run"

# Strategy Performance
perf-report:
	@echo "📊 Generating 30-day strategy performance report..."
	python3 scripts/generate_strategy_performance.py --days 30

perf-chart:
	@echo "📈 Generating strategy performance charts..."
	python3 scripts/generate_strategy_chart.py --days 7

perf-dashboard:
	@echo "🌐 Starting strategy performance dashboard..."
	@echo "📊 Open http://localhost:8080/dashboard/strategy_performance.html"
	python3 scripts/serve_dashboard.py

# Email & Notifications
email-daily:
	@echo "📧 Generating daily email digest..."
	python3 scripts/generate_daily_email.py
	@echo "✅ Email generated: /tmp/daily_email.html"

email-weekly:
	@echo "📊 Generating weekly email with visuals..."
	python3 scripts/generate_daily_email.py --include-visuals
	@echo "✅ Email with charts generated: /tmp/daily_email.html"

email-sample:
	@echo "📧 Generating sample email with mock data..."
	python3 examples/send_sample_email.py
	@echo "✅ Sample email generated: /tmp/sample_email.html"

email-sample-visual:
	@echo "📊 Generating sample email with visuals..."
	python3 examples/send_sample_email.py --include-visuals
	@echo "✅ Sample email with charts generated: /tmp/sample_email.html"

email-chart:
	@echo "📈 Generating performance chart for email..."
	python3 scripts/generate_email_chart.py

# System Validation & Management
validate:
	@echo "✅ Validating system invariants..."
	python3 scripts/validate_system.py --latest

verify-system:
	@echo "🔍 Verifying execution criteria..."
	python3 scripts/verify_execution.py

check-broker:
	@echo "💼 Checking broker state..."
	python3 scripts/check_broker_state.py

# Analysis & Debugging
debug-signal:
	@echo "🐛 Debugging single signal flow..."
	python3 scripts/debug_single_signal.py

backtest:
	@echo "📊 Running validation backtest..."
	python3 scripts/run_validation_backtest.py

# Data Cleaning & Backtesting
clean-data:
	@echo "🧹 Cleaning historical data..."
	@echo "   - Forward-fill missing values"
	@echo "   - Impute technical indicators"
	@echo ""
	python3 scripts/clean_data.py
	@echo ""
	@echo "✅ Clean data saved to data/training_data_clean.csv"

backtest-multi-strategy:
	@echo "📊 Running multi-strategy backtest..."
	@echo "   - RSI Mean Reversion"
	@echo "   - MA Crossover"
	@echo "   - Volatility Breakout"
	@echo "   - Momentum"
	@echo "   - ML Momentum"
	@echo ""
	python3 scripts/run_multi_strategy_backtest.py
	@echo ""
	@echo "✅ Results saved to artifacts/backtest/"
	@echo "   - Report: artifacts/backtest/multi_strategy_comparison.md"
	@echo "   - Plot: artifacts/backtest/strategy_comparison.png"

# Development helpers
dev-dashboard:
	@echo "🔧 Starting dashboard in development mode..."
	FLASK_ENV=development python3 src/dashboard_server.py

check-secrets:
	@echo "🔐 Checking GitHub secrets..."
	@python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print('✅ ALPACA_API_KEY:', 'Set' if os.getenv('ALPACA_API_KEY') else '❌ Missing'); print('✅ ALPACA_SECRET_KEY:', 'Set' if os.getenv('ALPACA_SECRET_KEY') else '❌ Missing')"

# Quick start guide
quickstart:
	@echo "🚀 QUICK START GUIDE"
	@echo ""
	@echo "1. Install dependencies:    make install"
	@echo "2. Sync database:           make sync-db"
	@echo "3. Run strategies:          make run"
	@echo "4. View dashboard:          make dashboard"
	@echo ""
	@echo "For help:                   make help"
