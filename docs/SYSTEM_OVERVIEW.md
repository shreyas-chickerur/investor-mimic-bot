# 📚 System Overview

**AI-Powered Investment System with Multi-Factor Analysis**

---

## 🎯 Purpose

Automated investment system that analyzes stocks using multiple factors and provides trade recommendations with an interactive approval workflow.

---

## 🔧 Core Components

### **8-Factor Analysis Engine**

1. **13F Conviction** - Institutional investor holdings
2. **News Sentiment** - Market sentiment analysis
3. **Insider Trading** - Corporate insider activity
4. **Technical Indicators** - RSI, MACD, momentum
5. **Moving Averages** - Trend identification (50-day, 200-day)
6. **Volume Analysis** - Trading volume patterns
7. **Relative Strength** - Performance vs market
8. **Earnings Momentum** - Fundamental catalyst tracking

### **Adaptive Features**

- **Market Regime Detection** - Identifies Bull/Bear/Sideways markets
- **Dynamic Weight Allocation** - Adjusts factor weights by market condition
- **Risk Management** - Stop-loss, position sizing, rebalancing
- **Sector Rotation** - Tracks sector performance trends

### **Automation**

- **Daily Workflow** - Automated analysis at scheduled times
- **Email Approval** - Interactive trade approval system
- **Risk Controls** - Automated stop-loss and position limits
- **Database Integration** - Stores 13F filings and holdings data

### **System Infrastructure**

- **Environment Management** - Separate dev/staging/prod configurations
- **Rate Limiting** - Token bucket algorithm for API calls
- **Error Handling** - Centralized error handling with retry logic
- **Monitoring** - System health checks and performance tracking
- **Logging** - Structured logging with database persistence
- **Data Validation** - Input/output validation across all layers
- **API Client** - Resilient API calls with exponential backoff

---

## 🏗️ Architecture

### **Data Layer**
```
services/sec/          # SEC EDGAR data (13F filings)
services/news/         # News sentiment analysis
services/technical/    # Technical indicators
services/fundamental/  # Earnings data
```

### **Analysis Layer**
```
services/strategy/     # 8-factor signal engine
services/market/       # Regime detection
services/risk/         # Risk management
services/portfolio/    # Position management
```

### **Execution Layer**
```
services/execution/    # Trade planning
services/approval/     # Email approval workflow
services/monitoring/   # Alerts and notifications
```

### **Infrastructure Layer**
```
utils/environment.py   # Environment configuration manager
utils/rate_limiter.py  # API rate limiting
utils/error_handler.py # Centralized error handling
utils/monitoring.py    # System monitoring and metrics
utils/enhanced_logging.py # Structured logging
utils/validators.py    # Data validation layer
utils/api_client.py    # Resilient API client
```

---

## 🔄 Workflow

1. **Data Collection** - Fetch 13F filings, news, prices
2. **Signal Generation** - Calculate 8-factor scores
3. **Regime Detection** - Identify current market condition
4. **Weight Adjustment** - Apply regime-specific weights
5. **Risk Analysis** - Check position limits, correlations
6. **Trade Planning** - Generate buy/sell recommendations
7. **Approval Request** - Send email with trade details
8. **Execution** - Execute approved trades via Alpaca
9. **Monitoring** - Track positions, send alerts

---

## 📊 Factor Weights

Weights are dynamically adjusted based on market regime:

**Bull Market:**
- Emphasis on momentum (Moving Averages, Relative Strength, Volume)
- Reduced emphasis on defensive factors

**Bear Market:**
- Emphasis on quality (13F Conviction, Insider Trading)
- Reduced emphasis on momentum

**Sideways Market:**
- Balanced approach across all factors

---

## 🛡️ Risk Management

### **Position Limits**
- Maximum position size: 15% of portfolio
- Maximum sector exposure: 25%
- Correlation limits to prevent concentration

### **Stop-Loss Protection**
- Automatic stop-loss orders
- Trailing stops for profit protection
- Volatility-adjusted sizing

### **Portfolio Controls**
- Daily rebalancing checks
- Position size monitoring
- Cash buffer requirements

---

## 🔧 Configuration

### **Environment Variables**
```bash
ALPACA_API_KEY         # Trading API key
ALPACA_SECRET_KEY      # Trading API secret
ALPHA_VANTAGE_API_KEY  # News sentiment API
SMTP_SERVER            # Email server
SMTP_USERNAME          # Email username
SMTP_PASSWORD          # Email password
DATABASE_URL           # PostgreSQL connection
```

### **System Parameters**
```python
MAX_POSITIONS = 10           # Maximum concurrent positions
REBALANCE_FREQUENCY = 10     # Days between rebalancing
SIGNAL_THRESHOLD = 0.6       # Minimum signal strength
STOP_LOSS_PCT = 0.20        # Stop-loss percentage
```

---

## 🚀 Usage

### **Daily Workflow**
```bash
make run-daily          # Run daily analysis and trading
```

### **Backtesting**
```bash
make backtest-optimized # Test strategy on historical data
```

### **Data Collection**
```bash
make collect-13f        # Update 13F filings
make collect-data       # Fetch historical prices
```

### **Optimization**
```bash
make optimize-weights   # Train ML models for weight optimization
```

---

## 📖 Additional Documentation

- **[Setup Guide](SETUP.md)** - Installation and configuration
- **[API Reference](API.md)** - Endpoint documentation
- **[Development Guide](DEVELOPMENT.md)** - Contributing guidelines

---

## ⚙️ Technology Stack

- **Backend:** Python, FastAPI
- **Database:** PostgreSQL with migrations
- **Trading:** Alpaca API with retry logic
- **Data Sources:** SEC EDGAR, Alpha Vantage
- **ML:** scikit-learn, pandas, numpy
- **Automation:** Cron, launchd
- **CI/CD:** GitHub Actions
- **Monitoring:** psutil, custom metrics
- **Logging:** Structured logging with DB persistence

---

## 🔒 Security

- API keys stored in environment variables
- Database credentials encrypted
- Email approval required for all trades
- Position limits enforced
- Stop-loss protection active
- SQL injection prevention via input sanitization
- Rate limiting on all API calls
- Comprehensive error handling and logging

---

## 📝 License

MIT

---

*For detailed setup instructions, see [Setup Guide](SETUP.md)*
