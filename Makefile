.PHONY: help install test lint format clean run-baseline run-optimized run-ultra backtest-all deploy docs

# Default target
help:
	@echo "Investor Mimic Bot - Makefile Commands"
	@echo "======================================="
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install          - Install all dependencies"
	@echo "  make install-dev      - Install development dependencies"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             - Run all linting checks (flake8, mypy)"
	@echo "  make format           - Format code with black"
	@echo "  make format-check     - Check code formatting without changes"
	@echo "  make test             - Run all tests
  make test-unit        - Run unit tests only
  make test-functional  - Run functional tests only
  make test-integration - Run integration tests only
  make test-performance - Run performance tests only
  make test-coverage    - Run tests with coverage report
  make test-quick       - Run quick tests (unit only)"
	@echo ""
	@echo "Backtesting:"
	@echo "  make backtest-baseline    - Run baseline backtest (static weights)"
	@echo "  make backtest-optimized   - Run optimized backtest (adaptive weights)"
	@echo "  make backtest-ultra       - Run ultra-optimized backtest (advanced risk)"
	@echo "  make backtest-all         - Run all backtests and compare"
	@echo "  make generate-data        - Generate synthetic historical data"
	@echo ""
	@echo "Optimization:"
	@echo "  make optimize-weights     - Train ML models and optimize factor weights"
	@echo "  make analyze-performance  - Analyze backtest results"
	@echo ""
	@echo "Production:"
	@echo "  make run-daily           - Run daily workflow (production)"
	@echo "  make run-paper           - Run in paper trading mode"
	@echo "  make deploy              - Deploy optimized configuration"
	@echo ""
	@echo "Data Collection:"
	@echo "  make collect-data        - Collect real historical data"
	@echo "  make collect-13f         - Update 13F filings"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean               - Clean generated files"
	@echo "  make docs                - Generate documentation"
	@echo "  make check-config        - Validate configuration files"

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install black flake8 mypy pytest pytest-cov

# Code Quality
lint:
	@echo "Running flake8..."
	python3 -m flake8 services/ scripts/ backtesting/ ml/ utils/ --max-line-length=120 --ignore=E203,W503 || true
	@echo ""
	@echo "Running mypy..."
	python3 -m mypy services/ scripts/ backtesting/ ml/ utils/ --ignore-missing-imports || true

format:
	@echo "Formatting code with black..."
	python3 -m black services/ scripts/ backtesting/ ml/ tests/ utils/ --line-length=120

format-check:
	@echo "Checking code formatting..."
	python3 -m black services/ scripts/ backtesting/ ml/ tests/ utils/ --line-length=120 --check

test:
	@echo "Running all tests..."
	python3 -m pytest tests/ -v --cov=services --cov=backtesting --cov=ml --cov=utils

test-unit:
	@echo "Running unit tests..."
	python3 -m pytest tests/unit/ -v

test-functional:
	@echo "Running functional tests..."
	python3 -m pytest tests/functional/ -v

test-integration:
	@echo "Running integration tests..."
	python3 -m pytest tests/integration/ -v

test-performance:
	@echo "Running performance tests..."
	python3 -m pytest tests/performance/ -v

test-coverage:
	@echo "Running tests with coverage report..."
	python3 -m pytest tests/ -v --cov=services --cov=backtesting --cov=ml --cov=utils --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/index.html"

test-quick:
	@echo "Running quick tests (unit only)..."
	python3 -m pytest tests/unit/ -v -x

# Data Generation
generate-data:
	@echo "Generating synthetic historical data..."
	python3 scripts/generate_synthetic_backtest_data.py

collect-data:
	@echo "Collecting real historical data..."
	python3 scripts/collect_historical_data.py

collect-13f:
	@echo "Updating 13F filings..."
	python3 scripts/load_13f_data.py

# Backtesting
backtest-baseline:
	@echo "Running baseline backtest (static weights)..."
	python3 backtesting/run_simple_backtest.py

backtest-optimized:
	@echo "Running optimized backtest (adaptive weights)..."
	python3 backtesting/run_optimized_backtest.py

backtest-ultra:
	@echo "Running ultra-optimized backtest (advanced risk management)..."
	python3 backtesting/run_ultra_optimized_backtest.py

backtest-all: generate-data backtest-baseline backtest-optimized backtest-ultra
	@echo ""
	@echo "All backtests complete! Check backtest_results/ for details."

# Optimization
optimize-weights:
	@echo "Training ML models and optimizing factor weights..."
	python3 ml/train_optimized_weights.py

analyze-performance:
	@echo "Analyzing backtest performance..."
	@python3 -c "import json; import pandas as pd; \
	from pathlib import Path; \
	results_dir = Path('backtest_results'); \
	for result_dir in sorted(results_dir.glob('*/metrics.json'))[-3:]: \
		with open(result_dir) as f: \
			metrics = json.load(f); \
			print(f'\n{result_dir.parent.name}:'); \
			print(f\"  Return: {metrics['total_return']:.2%}\"); \
			print(f\"  Sharpe: {metrics['sharpe_ratio']:.2f}\"); \
			print(f\"  Drawdown: {metrics['max_drawdown']:.2%}\")"

# Production
run-daily:
	@echo "Running daily workflow..."
	python3 scripts/resilient_daily_workflow.py

run-paper:
	@echo "Running in paper trading mode..."
	ALPACA_PAPER=True python3 scripts/resilient_daily_workflow.py

deploy:
	@echo "Deploying optimized configuration..."
	@echo "Checking configuration..."
	@python3 -c "import json; \
	with open('config/optimized_system_config.json') as f: \
		config = json.load(f); \
		print('✓ Configuration valid'); \
		print(f\"  Version: {config['system_version']}\"); \
		print(f\"  Backtest Return: {config['backtest_results']['annualized_return']:.2%}\")"
	@echo ""
	@echo "✓ System ready for deployment!"
	@echo "  Run 'make run-daily' to start"

# Configuration
check-config:
	@echo "Validating configuration files..."
	@python3 -c "import json; \
	from pathlib import Path; \
	configs = ['config/optimized_system_config.json', 'optimization_results/optimized_weights.json']; \
	for config_file in configs: \
		if Path(config_file).exists(): \
			with open(config_file) as f: \
				json.load(f); \
				print(f'✓ {config_file}'); \
		else: \
			print(f'✗ {config_file} not found')"

# Documentation
docs:
	@echo "Documentation available in docs/ folder:"
	@ls -1 docs/*.md | sed 's/^/  /'

# Cleanup
clean:
	@echo "Cleaning generated files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".DS_Store" -delete
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov
	@echo "✓ Cleanup complete"

# Quick start workflow
quickstart: install generate-data backtest-optimized
	@echo ""
	@echo "✅ Quickstart complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Review results in backtest_results/"
	@echo "  2. Run 'make deploy' to prepare for production"
	@echo "  3. Run 'make run-daily' to start trading"

# Development workflow
dev-setup: install-dev format lint test
	@echo ""
	@echo "✅ Development environment ready!"
