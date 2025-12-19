# 🚀 Investor Mimic Bot

**AI-Powered Investment System with 8-Factor Analysis & Adaptive Learning**

Automated investment bot that mimics top institutional investors using machine learning and multi-factor analysis.

## ✨ Key Features

### **8 Profit-Generating Factors**
- **13F Conviction** (30%) - Follow smart money
- **News Sentiment** (12%) - Market psychology
- **Insider Trading** (12%) - Information edge
- **Technical Indicators** (8%) - RSI, MACD
- **Moving Averages** (18%) - Trend identification
- **Volume Analysis** (10%) - Confirmation
- **Relative Strength** (8%) - Market leaders
- **Earnings Momentum** (2%) - Fundamental catalyst

### **Advanced Features**
- ✅ **Adaptive Regime Detection** - Bull/Bear/Sideways market classification
- ✅ **ML-Optimized Weights** - Trained on 14 years of data
- ✅ **Automated Risk Management** - Stop-loss, position sizing, rebalancing
- ✅ **Interactive Approval** - Review trades before execution
- ✅ **Comprehensive Backtesting** - Validated on 3,913 trading days

### **Key Capabilities**
- 📈 **Adaptive Learning** - ML-optimized factor weights
- 📊 **Risk Management** - Stop-loss, position sizing, rebalancing
- 🎯 **Market Regime Detection** - Bull/Bear/Sideways classification
- 📉 **Interactive Approval** - Review trades before execution
- 🏆 **Comprehensive Backtesting** - Test strategies on historical data

## 🚀 Quick Start

### **Option 1: Quick Demo (Recommended)**
```bash
# Install dependencies
make install

# Run optimized backtest (uses synthetic data)
make quickstart

# View results
open backtest_results/optimized_*/backtest_results.png
```

### **Option 2: Full Setup**
```bash
# 1. Install
make install

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Setup database
psql -U postgres -c "CREATE DATABASE investorbot;"
psql -U postgres -d investorbot -f sql/create_database.sql

# 4. Load 13F data
python3 scripts/fetch_13f_holdings.py
python3 scripts/load_13f_data.py

# 5. Deploy optimized system
make deploy

# 6. Run daily workflow
make run-daily
```

## 📋 Available Commands

### **Backtesting**
```bash
make backtest-baseline      # Baseline system (static weights)
make backtest-optimized     # Optimized system (adaptive weights)
make backtest-ultra         # Ultra-optimized (advanced risk)
make backtest-all           # Run all and compare
```

### **Optimization**
```bash
make optimize-weights       # Train ML models
make analyze-performance    # Analyze results
```

### **Production**
```bash
make run-daily             # Run daily workflow
make run-paper             # Paper trading mode
make deploy                # Deploy configuration
```

### **Code Quality**
```bash
make lint                  # Run linting checks
make format                # Format code
make test                  # Run tests
```

## 📁 Project Structure

```
services/           # Core system components
├── strategy/       # 8-factor engine, profit maximization
├── risk/           # Stop-loss, risk management
├── portfolio/      # Rebalancing, position sizing
├── market/         # Regime detection, macro indicators
├── technical/      # Moving averages, volume, indicators
└── fundamental/    # Earnings momentum

backtesting/        # Backtesting framework
├── backtest_engine.py
├── run_optimized_backtest.py
└── run_ultra_optimized_backtest.py

ml/                 # Machine learning optimization
├── adaptive_learning_engine.py
└── train_optimized_weights.py

scripts/            # Execution scripts
└── resilient_daily_workflow.py

docs/               # Complete documentation
├── COMPLETE_SYSTEM_GUIDE.md
├── OPTIMIZATION_RESULTS_REPORT.md
└── BACKTESTING_AND_ML_GUIDE.md
```

## ⚙️ Configuration

**Required environment variables:**
```bash
# Trading API
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=True

# Data API
ALPHA_VANTAGE_API_KEY=your_key

# Email Notifications
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@email.com
SMTP_PASSWORD=your_app_password
ALERT_EMAIL=your@email.com

# Database
DATABASE_URL=postgresql://postgres@localhost:5432/investorbot
```

**System Configuration:**
- `config/optimized_system_config.json` - Production settings
- `optimization_results/optimized_weights.json` - ML-optimized factor weights

## 🧪 Testing & Code Quality

```bash
# Run all tests
make test

# Lint code
make lint

# Format code
make format

# Check configuration
make check-config
```

## 📖 Documentation

**Complete guides available in `docs/` folder:**

- **[Complete System Guide](docs/COMPLETE_SYSTEM_GUIDE.md)** - Full system overview
- **[Optimization Results](docs/OPTIMIZATION_RESULTS_REPORT.md)** - Performance analysis
- **[Backtesting Guide](docs/BACKTESTING_AND_ML_GUIDE.md)** - ML & backtesting
- **[Advanced Features](docs/ADVANCED_FEATURES_GUIDE.md)** - Stop-loss, rebalancing, etc.
- **[Profit-Maximizing System](docs/PROFIT_MAXIMIZING_SYSTEM.md)** - 8-factor details
- **[Deployment Guide](docs/DEPLOYMENT_READY.md)** - Production deployment
- **[Tuning Analysis](docs/TUNING_ANALYSIS.md)** - Performance tuning

## 🎯 System Capabilities

| Feature | Description |
|---------|-------------|
| Factor Analysis | 8 factors analyzed per stock |
| Market Regimes | Adaptive weights by market condition |
| Risk Controls | Stop-loss, position limits, correlation checks |
| Automation | Daily workflow with email approval |

## 🤝 Contributing

Contributions welcome! Please:
1. Run `make format` before committing
2. Run `make lint` to check code quality
3. Run `make test` to ensure tests pass
4. Update documentation as needed

## 📄 License

MIT

---

**Built with ❤️ for automated, intelligent investing**
