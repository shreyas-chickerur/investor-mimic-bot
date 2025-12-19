# Documentation

**Investor Mimic Bot - Complete Documentation**

---

## Quick Start

- **[System Overview](SYSTEM_OVERVIEW.md)** - Architecture and components
- **[Setup Guide](SETUP_EMAIL_APPROVAL.md)** - Installation and configuration

---

## 📖 Core Documentation

### System Architecture
- **[System Overview](SYSTEM_OVERVIEW.md)** - Complete system architecture
- **[Complete System Guide](COMPLETE_SYSTEM_GUIDE.md)** - Detailed implementation
- **[Multi-Signal System](MULTI_SIGNAL_SYSTEM.md)** - Signal generation

### Features
- **[Advanced Features](ADVANCED_FEATURES_GUIDE.md)** - Stop-loss, rebalancing, regime detection
- **[Profit-Maximizing System](PROFIT_MAXIMIZING_SYSTEM.md)** - 8-factor analysis
- **[Factor Interactions](FACTOR_INTERACTIONS.md)** - How factors work together

### Workflows
- **[Selective Approval](SELECTIVE_APPROVAL.md)** - Trade approval process
- **[Email Setup](SETUP_EMAIL_APPROVAL.md)** - Email configuration

---

## Usage

### Daily Operations
```bash
make run-daily          # Run daily workflow
make run-paper          # Paper trading mode
```

### Development
```bash
make install            # Install dependencies
make lint               # Check code quality
make format             # Format code
make test               # Run tests
```

### Backtesting
```bash
make backtest-optimized # Run backtest
make optimize-weights   # Train ML models
```

---

## Project Structure

```
services/           # Core system components
├── strategy/       # 8-factor engine
├── risk/           # Risk management
├── portfolio/      # Position management
├── market/         # Regime detection
└── technical/      # Indicators

backtesting/        # Backtesting framework
ml/                 # ML optimization
scripts/            # Execution scripts
docs/               # This documentation
```

---

## Key Concepts

### 8-Factor Analysis
The system analyzes stocks using 8 factors:
1. 13F Conviction
2. News Sentiment
3. Insider Trading
4. Technical Indicators
5. Moving Averages
6. Volume Analysis
7. Relative Strength
8. Earnings Momentum

### Market Regimes
Automatically detects and adapts to:
- Bull markets
- Bear markets
- Sideways markets

### Risk Management
- Stop-loss protection
- Position sizing
- Correlation limits
- Sector exposure limits

---

## 🔒 Security

- API keys in environment variables
- Email approval required
- Position limits enforced
- Stop-loss protection active

---

## License

MIT
