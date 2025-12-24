.PHONY: help install run dashboard test clean sync-db view-performance analyze-signals

# Default target
help:
	@echo "📊 Multi-Strategy Trading System - Available Commands"
	@echo ""
	@echo "🚀 MAIN COMMANDS:"
	@echo "  make run              - Run all 5 trading strategies"
	@echo "  make dashboard        - Open web dashboard (http://localhost:5000)"
	@echo "  make analyze          - Analyze all strategies for signals"
	@echo ""
	@echo "📈 MONITORING:"
	@echo "  make view             - View strategy performance (CLI)"
	@echo "  make logs             - View recent trading logs"
	@echo "  make positions        - Check current Alpaca positions"
	@echo ""
	@echo "🔧 SETUP & MAINTENANCE:"
	@echo "  make install          - Install all dependencies"
	@echo "  make sync-db          - Sync database with Alpaca positions"
	@echo "  make update-data      - Update market data"
	@echo ""
	@echo "🧪 TESTING:"
	@echo "  make test             - Run all tests"
	@echo "  make test-single      - Test single RSI strategy"
	@echo "  make test-multi       - Test multi-strategy system"
	@echo ""
	@echo "🧹 CLEANUP:"
	@echo "  make clean            - Clean logs and temp files"
	@echo "  make clean-all        - Clean everything including databases"

# Installation
install:
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt
	@echo "✅ Installation complete"

# Main execution
run:
	@echo "🚀 Running multi-strategy trading system..."
	python3 src/multi_strategy_main.py

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
	python3 scripts/multi_strategy_analysis.py

# Monitoring
view:
	@echo "📊 Strategy Performance Dashboard"
	python3 scripts/view_strategy_performance.py

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
