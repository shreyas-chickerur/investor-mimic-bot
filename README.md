# 🚀 Investor Mimic Bot

**AI-Powered Investment System with 8-Factor Analysis & Adaptive Learning**

Automated investment bot that mimics top institutional investors using machine learning and multi-factor analysis.

**Latest Updates (Dec 2025):**
- 📧 Daily Digest Email with Morning Brew style
- 🔍 Stock Causality Flow Charts with interactive explanations
- 🔄 Continuous Learning ML Pipeline
- 👤 User Management & Authentication System
- 🌐 Web Dashboard Architecture (in development)
- ✅ GitHub CI/CD with automated testing

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
- ✅ **Daily Digest Email** - Morning Brew style investment digest
- ✅ **Causality Analysis** - Transparent recommendation explanations
- ✅ **Continuous Learning** - Automated model retraining
- ✅ **User Authentication** - JWT-based secure access
- ✅ **CI/CD Pipeline** - Automated testing on every PR

### **Key Capabilities**
- 📈 **Adaptive Learning** - ML-optimized factor weights with continuous retraining
- 📊 **Risk Management** - Stop-loss, position sizing, rebalancing
- 🎯 **Market Regime Detection** - Bull/Bear/Sideways classification
- 📉 **Interactive Approval** - Review trades before execution
- 🏆 **Comprehensive Backtesting** - Test strategies on historical data
- 📧 **Daily Digest** - Personalized morning investment email
- 🔍 **Transparent AI** - Interactive flow charts showing recommendation reasoning
- 👤 **Multi-User Support** - User accounts, settings, and tracking

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

### **Email & Notifications**
```bash
make send-digest           # Send daily digest email
```

### **Code Quality**
```bash
make lint                  # Run linting checks
make format                # Format code
make test                  # Run tests (58 unit tests)
make test-unit             # Unit tests only
make test-integration      # Integration tests
make test-functional       # Functional tests
```

## 📁 Project Structure

```
services/           # Core system components
├── strategy/       # 8-factor engine, profit maximization
├── risk/           # Stop-loss, risk management
├── portfolio/      # Rebalancing, position sizing
├── market/         # Regime detection, macro indicators
├── technical/      # Moving averages, volume, indicators
├── fundamental/    # Earnings momentum
├── monitoring/     # Daily digest, email templates
├── analysis/       # Stock causality analyzer
└── approval/       # Trade approval system

api/                # FastAPI backend
└── auth.py         # JWT authentication

backtesting/        # Backtesting framework
├── backtest_engine.py
├── run_optimized_backtest.py
└── run_ultra_optimized_backtest.py

ml/                 # Machine learning optimization
├── continuous_learning_engine.py
├── data_collection_pipeline.py
├── feature_engineering_pipeline.py
└── train_optimized_weights.py

scripts/            # Execution scripts
├── resilient_daily_workflow.py
├── send_daily_digest.py
└── automated_ml_pipeline.py

docs/               # Complete documentation
├── features/       # Feature documentation
├── user-actions/   # Setup guides & action items
├── COMPLETE_SYSTEM_GUIDE.md
├── OPTIMIZATION_RESULTS_REPORT.md
└── WEB_DASHBOARD_ARCHITECTURE.md
```

## ⚙️ Configuration

**Required environment variables:**
```bash
# Trading API
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=True

# Data APIs
ALPHA_VANTAGE_API_KEY=your_key  # Required for news & earnings
FINNHUB_API_KEY=your_key         # Optional for additional news
NEWSAPI_KEY=your_key              # Optional for news aggregation

# Email Notifications (Required for daily digest)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@email.com
SMTP_PASSWORD=your_app_password
ALERT_EMAIL=your@email.com

# Authentication (Required for web dashboard)
JWT_SECRET_KEY=your_generated_secret  # Generate with: openssl rand -hex 32
FRONTEND_URL=http://localhost:3000

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

**Start here:** [docs/user-actions/USER_ACTION_ITEMS.md](docs/user-actions/USER_ACTION_ITEMS.md) - Complete setup checklist

**User Actions & Setup:**
- **[USER_ACTION_ITEMS.md](docs/user-actions/USER_ACTION_ITEMS.md)** - 7-phase setup guide
- **[GITHUB_BRANCH_PROTECTION_SETUP.md](docs/user-actions/GITHUB_BRANCH_PROTECTION_SETUP.md)** - CI/CD setup
- **[SYSTEM_ANALYSIS_AND_GAPS.md](docs/user-actions/SYSTEM_ANALYSIS_AND_GAPS.md)** - System analysis

**Feature Documentation:**
- **[Daily Digest Guide](docs/features/DAILY_DIGEST_GUIDE.md)** - Email digest setup
- **[Stock Causality Flow Charts](docs/features/STOCK_CAUSALITY_FLOW_CHARTS.md)** - Recommendation explanations
- **[Continuous Learning Guide](docs/features/CONTINUOUS_LEARNING_GUIDE.md)** - ML training
- **[Advanced Features](docs/features/ADVANCED_FEATURES_GUIDE.md)** - Stop-loss, rebalancing

**Core Documentation:**
- **[Complete System Guide](docs/COMPLETE_SYSTEM_GUIDE.md)** - Full system overview
- **[Optimization Results](docs/OPTIMIZATION_RESULTS_REPORT.md)** - Performance analysis
- **[Testing Guide](docs/TESTING_GUIDE.md)** - How to test the system
- **[Documentation Index](docs/INDEX.md)** - Complete documentation index

## 🎯 System Capabilities

| Feature | Description |
|---------|-------------|
| Factor Analysis | 8 factors analyzed per stock |
| Market Regimes | Adaptive weights by market condition |
| Risk Controls | Stop-loss, position limits, correlation checks |
| Automation | Daily workflow with email approval |
| Daily Digest | Morning Brew style personalized email |
| Causality Analysis | Transparent AI with interactive flow charts |
| Continuous Learning | Automated ML model retraining |
| User Management | Multi-user support with authentication |
| CI/CD Pipeline | Automated testing on every PR (58 tests) |
| Data Collection | 13F, news, earnings, insider trades, technicals |

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
