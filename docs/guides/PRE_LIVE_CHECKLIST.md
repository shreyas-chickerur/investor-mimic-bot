# Pre-Live Trading Checklist

**Version:** 1.0  
**Last Updated:** January 2026  
**Status:** Pre-Production Review

---

## Purpose

This checklist ensures the trading system is production-ready before deploying with real capital. Every item must be verified and signed off before live trading begins.

---

## 🔴 CRITICAL: Pre-Flight Verification

### 1. Capital & Account Setup

- [ ] **Alpaca account funded** with intended capital ($1,000 minimum recommended)
- [ ] **API keys generated** (live trading keys, not paper trading)
- [ ] **API keys stored** in `.env` file (never committed to git)
- [ ] **Trading mode verified**: `TRADING_MODE=live` in `.env`
- [ ] **Account type confirmed**: Margin or Cash account (affects day trading rules)
- [ ] **Buying power verified** via Alpaca dashboard

### 2. Environment Configuration

- [ ] **`.env` file exists** with all required variables:
  ```bash
  ALPACA_API_KEY=<your_live_key>
  ALPACA_SECRET_KEY=<your_live_secret>
  ALPACA_BASE_URL=https://api.alpaca.markets  # LIVE, not paper
  TRADING_MODE=live
  DRY_RUN=false
  ```
- [ ] **Config file validated**: `config/trading_config.yaml` reviewed
- [ ] **Risk parameters set** appropriately for capital size
- [ ] **Database initialized**: `trading.db` exists or will be created
- [ ] **Logs directory exists**: `logs/` folder created

### 3. Risk Controls Verification

- [ ] **Portfolio heat limit**: Set to 30% (or lower for conservative approach)
- [ ] **Daily loss limit**: Set to 2% (halts trading if breached)
- [ ] **Drawdown stops configured**:
  - 8% drawdown → Halt new entries, 10-day cooldown
  - 10% drawdown → Panic mode, flatten all positions
- [ ] **Correlation filter active**: Rejects correlated positions (>0.70)
- [ ] **Position sizing**: ATR-based, 1% portfolio risk per trade
- [ ] **Stop losses enabled**: 2.5x ATR catastrophic stops

### 4. Strategy Configuration

- [ ] **Strategy allocation reviewed** in `config/trading_config.yaml`:
  - RSI Mean Reversion: 20%
  - MA Crossover: 20%
  - ML Momentum: 20%
  - Volatility Breakout: 20%
  - News Sentiment: 20%
- [ ] **Strategy parameters validated** (RSI thresholds, MA periods, etc.)
- [ ] **Universe size appropriate**: 36 stocks (not too many for $1K capital)
- [ ] **Execution timing set**: 4:15 PM ET (avoids lookahead bias)

### 5. Monitoring & Alerts

- [ ] **Email notifications configured**:
  - SMTP settings in `.env`
  - Test email sent successfully
- [ ] **Alert thresholds set**:
  - Drawdown alerts at 8% and 10%
  - No-trade alerts after 7 days
  - Reconciliation failure alerts
- [ ] **Dashboard accessible**: `streamlit run dashboard/app.py`
- [ ] **Artifact directory exists**: `artifacts/` for daily reports

### 6. Broker Reconciliation

- [ ] **Reconciliation enabled**: Runs before every trading session
- [ ] **Tolerance levels set**:
  - Cash tolerance: $10
  - Position price tolerance: $0.50
  - Position quantity tolerance: 0 shares (exact match)
- [ ] **Pause-on-mismatch enabled**: Trading halts if reconciliation fails
- [ ] **Manual resume protocol documented**

### 7. Data & Execution

- [ ] **Historical data collected**: 15 years for 36 stocks (Alpha Vantage)
- [ ] **Data quality checks pass**: No missing dates, valid OHLCV
- [ ] **Execution costs configured**: Slippage 0.05%, commission $0/trade
- [ ] **Order types validated**: Market orders at open/close
- [ ] **Partial fills handled**: System rejects partial fills

---

## 🧪 Testing Requirements

### Unit Tests

- [ ] **All critical tests pass**: `pytest tests/ -v`
- [ ] **Coverage verified**: >80% on critical modules
- [ ] **Risk management tests**: 100% pass rate required
- [ ] **Drawdown stop tests**: All scenarios covered
- [ ] **Broker reconciliation tests**: Pass/fail logic verified

### Integration Tests

- [ ] **Paper trading run**: Minimum 2 weeks, ideally 1 month
- [ ] **No errors in paper trading**: Check logs for exceptions
- [ ] **Trades executed successfully**: Verify in Alpaca dashboard
- [ ] **Risk controls triggered correctly**: Test with simulated losses
- [ ] **Reconciliation works**: Daily checks pass without manual intervention

### Backtesting Validation

- [ ] **Walk-forward backtest completed**: 2-year train, 6-month test, 6-month step
- [ ] **Realistic metrics**:
  - Sharpe ratio: 0.8-1.3 (>2.0 = likely leakage)
  - Max drawdown: 10-20% (<5% = unrealistic)
  - Win rate: 45-55% (>65% = suspicious)
- [ ] **Stress test periods reviewed**:
  - 2008-2009 (systemic crisis)
  - 2020 (volatility shock)
  - 2022 (prolonged bear market)
- [ ] **Known weaknesses documented**

---

## 📋 Operational Procedures

### Daily Pre-Market Routine (Before 9:30 AM ET)

1. [ ] **Check system health**: Review logs for errors
2. [ ] **Run broker reconciliation**: `python src/risk/broker_reconciler.py`
3. [ ] **Verify no circuit breakers active**: Check drawdown status
4. [ ] **Review open positions**: Confirm expected holdings
5. [ ] **Check cash balance**: Ensure sufficient buying power

### Daily Post-Market Routine (After 4:00 PM ET)

1. [ ] **Review trade execution**: Check `artifacts/` for daily report
2. [ ] **Verify P&L**: Compare to Alpaca dashboard
3. [ ] **Check strategy performance**: Review dashboard metrics
4. [ ] **Monitor drawdown**: Ensure within acceptable limits
5. [ ] **Review rejected signals**: Understand why trades were blocked

### Weekly Review

1. [ ] **Strategy allocation review**: Check if any strategy dominates
2. [ ] **Risk metrics review**: Heat, correlation, volatility
3. [ ] **Performance attribution**: Which strategies are working?
4. [ ] **Data quality check**: Any missing/stale data?
5. [ ] **System logs review**: Any recurring warnings?

### Monthly Review

1. [ ] **Full backtest refresh**: Re-run with latest data
2. [ ] **Strategy parameter review**: Any needed adjustments?
3. [ ] **Risk limit review**: Adjust for account growth/decline
4. [ ] **Database maintenance**: Archive old data, optimize queries
5. [ ] **Dependency updates**: Check for security patches

---

## 🚨 Emergency Procedures

### Immediate Actions (Circuit Breakers)

**8% Drawdown Hit:**
1. System automatically halts new entries
2. Existing positions remain open
3. 10-day cooldown period begins
4. Email alert sent
5. Manual review required before resume

**10% Drawdown Hit (PANIC MODE):**
1. System automatically flattens ALL positions
2. Trading halted completely
3. 20-day cooldown period begins
4. Email alert sent (CRITICAL)
5. Full system audit required before resume

**Reconciliation Failure:**
1. Trading paused immediately
2. Email alert sent
3. Manual investigation required
4. Compare database vs. Alpaca positions
5. Resolve discrepancy before force resume

### Manual Intervention

**Force Resume After Circuit Breaker:**
```bash
python -c "from src.risk.drawdown_stop_manager import DrawdownStopManager; \
from src.core.database import TradingDatabase; \
db = TradingDatabase('trading.db'); \
mgr = DrawdownStopManager(db, None); \
mgr.force_resume()"
```

**Force Resume After Reconciliation Failure:**
```bash
python -c "from src.risk.broker_reconciler import BrokerReconciler; \
from src.core.database import TradingDatabase; \
db = TradingDatabase('trading.db'); \
rec = BrokerReconciler(db, None); \
rec.force_resume()"
```

**Emergency Flatten All Positions:**
```bash
python -c "from alpaca.trading.client import TradingClient; \
import os; \
client = TradingClient(os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_SECRET_KEY')); \
client.close_all_positions(cancel_orders=True)"
```

---

## 📊 Performance Expectations

### Realistic Targets (Based on Backtest)

- **Annual Return**: 10-25% (>50% extremely unlikely without leverage)
- **Sharpe Ratio**: 0.8-1.3 (>2.0 indicates possible leakage)
- **Max Drawdown**: 10-20% (<5% unrealistic, >30% excessive risk)
- **Win Rate**: 45-55% (>65% suspicious)
- **Turnover**: Moderate (not day trading, not buy-and-hold)
- **Time in Market**: 40-60% (strategies are selective)

### Red Flags (Investigate Immediately)

- **Sharpe >2.0**: Possible lookahead bias or overfitting
- **Max DD <5%**: Unrealistic, check for data issues
- **Win rate >65%**: Suspicious, verify signal logic
- **Smooth equity curve**: Check for survivorship bias
- **Sudden strategy dominance**: One strategy >50% allocation
- **Correlation breakdown**: Positions highly correlated despite filter

---

## 🔐 Security Checklist

- [ ] **API keys never committed**: `.env` in `.gitignore`
- [ ] **Database not exposed**: `trading.db` local only
- [ ] **Logs sanitized**: No sensitive data in logs
- [ ] **Email credentials secure**: SMTP password in `.env`
- [ ] **Server access restricted**: If running on VPS
- [ ] **Backup strategy**: Database backed up daily
- [ ] **Disaster recovery plan**: Can restore from backup

---

## 📝 Documentation Review

- [ ] **README.md up to date**: Installation, usage, features
- [ ] **Architecture documented**: System design, data flow
- [ ] **Risk controls documented**: How each safety mechanism works
- [ ] **Operational procedures documented**: Daily/weekly routines
- [ ] **Known limitations documented**: What the system can't do
- [ ] **Contact information**: Who to call if system fails

---

## ✅ Final Sign-Off

**Before going live, confirm:**

- [ ] I have read and understand all risk controls
- [ ] I have tested the system in paper trading for at least 2 weeks
- [ ] I have verified all configuration settings
- [ ] I have set up monitoring and alerts
- [ ] I understand the emergency procedures
- [ ] I accept the risk of capital loss
- [ ] I will monitor the system daily during the first month
- [ ] I have a plan to shut down if performance degrades

**Signed:** ___________________________  
**Date:** ___________________________  
**Capital Deployed:** $___________________________

---

## 🚀 Go-Live Procedure

### Day 1: Soft Launch

1. **Start with 50% of intended capital** (e.g., $500 if planning $1K)
2. **Enable dry-run mode first**: `DRY_RUN=true` for 1 day
3. **Review dry-run results**: Check logs, no errors
4. **Switch to live mode**: `DRY_RUN=false`
5. **Monitor continuously**: Watch first trades execute
6. **Verify reconciliation**: Confirm positions match Alpaca

### Week 1: Close Monitoring

1. **Daily checks**: Pre-market and post-market routines
2. **Review every trade**: Understand entry/exit logic
3. **Monitor risk metrics**: Heat, correlation, drawdown
4. **Verify alerts work**: Test email notifications
5. **Document issues**: Log any unexpected behavior

### Month 1: Ramp to Full Capital

1. **Week 2**: Increase to 75% capital if no issues
2. **Week 3**: Increase to 100% capital if performance acceptable
3. **Week 4**: Full operational mode, continue monitoring
4. **End of month**: Full performance review, decide to continue or adjust

---

## 📞 Support & Resources

- **Alpaca Support**: https://alpaca.markets/support
- **System Logs**: `logs/trading_system.log`
- **Dashboard**: `streamlit run dashboard/app.py`
- **Database**: `sqlite3 trading.db`
- **Artifacts**: `artifacts/` directory

---

**REMEMBER:** This is real money. The system is designed to be conservative and risk-aware, but losses are possible. Never deploy more capital than you can afford to lose. Monitor daily, especially in the first month.
