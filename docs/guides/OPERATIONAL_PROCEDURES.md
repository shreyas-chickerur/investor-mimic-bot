# Operational Procedures

**Daily, Weekly, and Monthly Trading System Operations**

---

## Daily Operations

### Pre-Market Routine (Before 9:30 AM ET)

#### 1. System Health Check (5 minutes)

```bash
# Check if system is running
ps aux | grep python | grep trading

# Review overnight logs
tail -100 logs/trading_system.log

# Check for errors
grep -i "error\|exception\|failed" logs/trading_system.log | tail -20
```

**Look for:**
- No critical errors in logs
- No exceptions during last run
- System completed previous day's execution

#### 2. Broker Reconciliation (2 minutes)

```bash
# Run reconciliation check
python src/risk/broker_reconciler.py

# Expected output: "✅ Reconciliation PASSED"
```

**If reconciliation fails:**
1. Review mismatch details in output
2. Check Alpaca dashboard for actual positions
3. Compare with `trading.db` positions table
4. Investigate discrepancy (manual trade? System error?)
5. Resolve issue before trading resumes
6. Use `force_resume()` only after confirming data is correct

#### 3. Circuit Breaker Status Check (1 minute)

```bash
# Check if any circuit breakers are active
python -c "from src.core.database import TradingDatabase; \
db = TradingDatabase('trading.db'); \
cursor = db.conn.execute('SELECT * FROM circuit_breaker_status ORDER BY timestamp DESC LIMIT 1'); \
print(cursor.fetchone())"
```

**Verify:**
- No active drawdown stops (8% or 10%)
- No active daily loss limits
- System is in normal trading mode

#### 4. Position Review (2 minutes)

```bash
# View current positions
python -c "from src.core.database import TradingDatabase; \
db = TradingDatabase('trading.db'); \
import pandas as pd; \
positions = pd.read_sql('SELECT * FROM positions WHERE exit_date IS NULL', db.conn); \
print(positions[['symbol', 'shares', 'entry_price', 'strategy_id', 'entry_date']])"
```

**Check:**
- All positions are expected (no surprises)
- Entry dates are reasonable (not stuck positions)
- Shares and prices match Alpaca dashboard

#### 5. Cash Balance Verification (1 minute)

```bash
# Check available cash
python -c "from alpaca.trading.client import TradingClient; \
import os; \
client = TradingClient(os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_SECRET_KEY')); \
account = client.get_account(); \
print(f'Cash: ${float(account.cash):.2f}'); \
print(f'Buying Power: ${float(account.buying_power):.2f}'); \
print(f'Portfolio Value: ${float(account.portfolio_value):.2f}')"
```

**Verify:**
- Sufficient cash for potential trades
- Buying power matches expectations
- Portfolio value is within expected range

---

### Post-Market Routine (After 4:30 PM ET)

#### 1. Trade Execution Review (5 minutes)

```bash
# View today's trades
python -c "from src.core.database import TradingDatabase; \
import pandas as pd; \
from datetime import datetime; \
db = TradingDatabase('trading.db'); \
today = datetime.now().strftime('%Y-%m-%d'); \
trades = pd.read_sql(f\"SELECT * FROM trades WHERE entry_date = '{today}' OR exit_date = '{today}'\", db.conn); \
print(trades[['symbol', 'action', 'shares', 'price', 'strategy_id', 'pnl']])"
```

**Review:**
- All intended trades executed successfully
- No unexpected trades (phantom orders)
- Entry/exit prices are reasonable (no extreme slippage)

#### 2. Daily Artifact Review (3 minutes)

```bash
# View today's artifact
ls -lh artifacts/daily_report_*.json | tail -1
cat artifacts/daily_report_$(date +%Y%m%d).json | python -m json.tool | head -50
```

**Check:**
- Artifact was generated successfully
- Portfolio value updated
- Strategy performance metrics present
- Risk metrics within acceptable ranges

#### 3. P&L Verification (2 minutes)

```bash
# Calculate today's P&L
python -c "from src.monitoring.pnl_calculator import PnLCalculator; \
from src.core.database import TradingDatabase; \
db = TradingDatabase('trading.db'); \
pnl = PnLCalculator(db); \
daily_pnl = pnl.calculate_daily_pnl(); \
print(f'Daily P&L: ${daily_pnl:.2f}')"
```

**Compare with Alpaca:**
- Log into Alpaca dashboard
- Check "Today's P&L"
- Should match system calculation (within $10)

#### 4. Strategy Performance Check (3 minutes)

```bash
# View strategy performance
python -c "from src.core.database import TradingDatabase; \
import pandas as pd; \
db = TradingDatabase('trading.db'); \
perf = pd.read_sql('SELECT strategy_id, COUNT(*) as trades, AVG(pnl) as avg_pnl, SUM(pnl) as total_pnl FROM trades WHERE pnl IS NOT NULL GROUP BY strategy_id', db.conn); \
print(perf)"
```

**Monitor:**
- No single strategy dominating (>50% of trades)
- No strategy with consistent losses
- Win rates are reasonable (40-60%)

#### 5. Drawdown Monitoring (2 minutes)

```bash
# Check current drawdown
python -c "from src.core.database import TradingDatabase; \
db = TradingDatabase('trading.db'); \
cursor = db.conn.execute('SELECT portfolio_value FROM performance_metrics ORDER BY date DESC LIMIT 1'); \
current = cursor.fetchone()[0]; \
cursor = db.conn.execute('SELECT MAX(portfolio_value) FROM performance_metrics'); \
peak = cursor.fetchone()[0]; \
drawdown = (peak - current) / peak; \
print(f'Current Drawdown: {drawdown:.2%}'); \
print(f'Peak: ${peak:.2f}, Current: ${current:.2f}')"
```

**Alert if:**
- Drawdown > 5% (monitor closely)
- Drawdown > 8% (circuit breaker will trigger)
- Drawdown > 10% (panic mode imminent)

#### 6. Review Rejected Signals (3 minutes)

```bash
# View rejected signals
python -c "from src.core.database import TradingDatabase; \
import pandas as pd; \
from datetime import datetime; \
db = TradingDatabase('trading.db'); \
today = datetime.now().strftime('%Y-%m-%d'); \
rejected = pd.read_sql(f\"SELECT * FROM signals WHERE asof_date = '{today}' AND terminal_state != 'executed'\", db.conn); \
print(rejected[['symbol', 'strategy_id', 'terminal_state', 'rejection_reason']].value_counts('terminal_state'))"
```

**Understand:**
- Why signals were rejected (correlation? heat limit? daily loss?)
- Are rejections reasonable?
- Is one filter rejecting too many signals?

---

## Weekly Operations

### Sunday Evening Review (30 minutes)

#### 1. Strategy Allocation Review

```bash
# View strategy allocation over past week
python -c "from src.core.database import TradingDatabase; \
import pandas as pd; \
from datetime import datetime, timedelta; \
db = TradingDatabase('trading.db'); \
week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'); \
trades = pd.read_sql(f\"SELECT strategy_id, COUNT(*) as count, SUM(shares * price) as total_value FROM trades WHERE entry_date >= '{week_ago}' GROUP BY strategy_id\", db.conn); \
print(trades)"
```

**Check:**
- Strategy allocation is balanced (no single strategy >35%)
- All strategies are active (not stuck)
- Allocation matches config targets (±10%)

#### 2. Risk Metrics Review

```bash
# View weekly risk metrics
python -c "from src.core.database import TradingDatabase; \
import pandas as pd; \
from datetime import datetime, timedelta; \
db = TradingDatabase('trading.db'); \
week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'); \
metrics = pd.read_sql(f\"SELECT date, portfolio_value, portfolio_heat, max_drawdown, sharpe_ratio FROM performance_metrics WHERE date >= '{week_ago}' ORDER BY date\", db.conn); \
print(metrics)"
```

**Monitor:**
- Portfolio heat staying below 30%
- Drawdown not increasing consistently
- Sharpe ratio trending positive

#### 3. Performance Attribution

```bash
# Which strategies are working?
python -c "from src.core.database import TradingDatabase; \
import pandas as pd; \
from datetime import datetime, timedelta; \
db = TradingDatabase('trading.db'); \
week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'); \
perf = pd.read_sql(f\"SELECT strategy_id, COUNT(*) as trades, SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins, AVG(pnl) as avg_pnl, SUM(pnl) as total_pnl FROM trades WHERE entry_date >= '{week_ago}' AND pnl IS NOT NULL GROUP BY strategy_id\", db.conn); \
perf['win_rate'] = perf['wins'] / perf['trades']; \
print(perf)"
```

**Identify:**
- Best performing strategy this week
- Worst performing strategy this week
- Any strategy with win rate <30% (investigate)

#### 4. Data Quality Check

```bash
# Check for missing data
python -c "from src.data.data_quality_checker import DataQualityChecker; \
from src.data.universe_provider import UniverseProvider; \
universe = UniverseProvider().get_universe(); \
checker = DataQualityChecker(); \
for symbol in universe[:5]:  # Check first 5 stocks
    print(f'{symbol}: {checker.check_data_quality(symbol)}')"
```

**Verify:**
- No missing dates in recent data
- Indicators calculating correctly
- No stale data (last update within 24 hours)

#### 5. System Logs Review

```bash
# Check for recurring warnings
grep -i "warning" logs/trading_system.log | tail -50 | sort | uniq -c | sort -rn
```

**Investigate:**
- Any warning appearing >10 times
- New warnings not seen before
- Warnings related to data, execution, or risk

---

## Monthly Operations

### First Sunday of Month (2 hours)

#### 1. Full Backtest Refresh

```bash
# Re-run backtest with latest data
python src/integration/portfolio_backtester.py --start-date 2020-01-01 --end-date $(date +%Y-%m-%d)
```

**Compare with previous month:**
- Sharpe ratio trend (improving or degrading?)
- Max drawdown (increasing or stable?)
- Win rate (consistent or changing?)
- Strategy performance (any strategy failing?)

#### 2. Strategy Parameter Review

**Review `config/trading_config.yaml`:**
- Are RSI thresholds still appropriate?
- Are MA periods optimal for current market?
- Is correlation threshold too strict/loose?
- Is portfolio heat limit appropriate for account size?

**DO NOT tune parameters for better performance** - only adjust if:
- Market regime has fundamentally changed
- Strategy is clearly broken (win rate <30% for 3 months)
- Risk limits are inappropriate for account size

#### 3. Risk Limit Review

```bash
# Calculate account growth/decline
python -c "from src.core.database import TradingDatabase; \
db = TradingDatabase('trading.db'); \
cursor = db.conn.execute('SELECT portfolio_value FROM performance_metrics ORDER BY date LIMIT 1'); \
initial = cursor.fetchone()[0]; \
cursor = db.conn.execute('SELECT portfolio_value FROM performance_metrics ORDER BY date DESC LIMIT 1'); \
current = cursor.fetchone()[0]; \
print(f'Initial: ${initial:.2f}, Current: ${current:.2f}, Change: {(current/initial - 1):.2%}')"
```

**Adjust if needed:**
- Account grew >20%: Consider increasing position sizes
- Account declined >10%: Consider reducing position sizes
- Update `config/trading_config.yaml` accordingly

#### 4. Database Maintenance

```bash
# Vacuum database (reclaim space)
sqlite3 trading.db "VACUUM;"

# Analyze query performance
sqlite3 trading.db "ANALYZE;"

# Check database size
du -h trading.db

# Archive old data (optional, if >100MB)
python -c "from src.core.database import TradingDatabase; \
from datetime import datetime, timedelta; \
db = TradingDatabase('trading.db'); \
cutoff = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'); \
db.conn.execute(f\"DELETE FROM signals WHERE asof_date < '{cutoff}'\"); \
db.conn.commit(); \
print('Archived signals older than 1 year')"
```

#### 5. Dependency Updates

```bash
# Check for outdated packages
pip list --outdated

# Update non-breaking packages
pip install --upgrade pandas numpy scikit-learn

# Test after updates
pytest tests/ -v --tb=short
```

**Be cautious with:**
- Major version updates (e.g., pandas 1.x → 2.x)
- Breaking changes in APIs
- Always test after updating

---

## Quarterly Operations

### End of Quarter Review (4 hours)

#### 1. Full System Audit

- Review all logs for past 3 months
- Identify any recurring issues
- Document any manual interventions
- Review all circuit breaker triggers

#### 2. Performance Report

- Generate quarterly performance report
- Compare to benchmark (S&P 500)
- Calculate risk-adjusted returns (Sharpe, Sortino, Calmar)
- Document strategy attribution

#### 3. Strategy Review

- Which strategies performed best?
- Which strategies underperformed?
- Any strategies to disable/modify?
- Any new strategies to add?

#### 4. Risk Control Effectiveness

- How many times did correlation filter trigger?
- How many times did portfolio heat limit trigger?
- Did drawdown stops trigger? (If yes, review)
- Are risk controls too strict or too loose?

#### 5. Infrastructure Review

- Server/VPS performance (if applicable)
- Database size and performance
- Log file management
- Backup strategy working?

---

## Emergency Procedures

### Circuit Breaker Triggered

**8% Drawdown (Halt Mode):**
1. System automatically halts new entries
2. Existing positions remain open
3. Email alert sent
4. Review cause of drawdown (market crash? strategy failure?)
5. Monitor for 10 trading days
6. System auto-resumes after cooldown if conditions met
7. Manual review required before resume

**10% Drawdown (Panic Mode):**
1. System automatically flattens ALL positions
2. Trading halted completely
3. Email alert sent (CRITICAL)
4. Full system audit required
5. Review all strategies, risk controls, data quality
6. Determine root cause before resuming
7. Manual `force_resume()` only after fixes implemented

### Reconciliation Failure

1. Trading paused immediately
2. Email alert sent
3. Compare database vs. Alpaca positions:
   ```bash
   python src/risk/broker_reconciler.py --verbose
   ```
4. Investigate discrepancy:
   - Manual trade placed outside system?
   - System error during execution?
   - Database corruption?
5. Resolve issue (update database or fix system)
6. Force resume only after confirming data is correct:
   ```bash
   python -c "from src.risk.broker_reconciler import BrokerReconciler; \
   from src.core.database import TradingDatabase; \
   db = TradingDatabase('trading.db'); \
   rec = BrokerReconciler(db, None); \
   rec.force_resume()"
   ```

### System Crash/Hang

1. Check if process is running:
   ```bash
   ps aux | grep python | grep trading
   ```
2. Review logs for errors:
   ```bash
   tail -100 logs/trading_system.log
   ```
3. If hung, kill process:
   ```bash
   pkill -f "python.*trading"
   ```
4. Restart system:
   ```bash
   python src/core/execution_engine.py
   ```
5. Monitor for 1 hour to ensure stability

### Data Feed Failure

1. Check Alpaca API status: https://status.alpaca.markets
2. Test API connection:
   ```bash
   python -c "from alpaca.trading.client import TradingClient; \
   import os; \
   client = TradingClient(os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_SECRET_KEY')); \
   print(client.get_account())"
   ```
3. If API is down, system will skip trading for the day
4. If API is up but data is stale, investigate data fetcher
5. Manual data refresh if needed:
   ```bash
   python src/data/data_fetcher.py --symbols AAPL,MSFT,GOOGL --start-date 2024-01-01
   ```

---

## Monitoring Dashboard

### Launch Dashboard

```bash
cd dashboard
streamlit run app.py --server.port 8501
```

**Access:** http://localhost:8501

**Dashboard Sections:**
1. **Portfolio Overview**: Current value, P&L, drawdown
2. **Positions**: Open positions, entry dates, unrealized P&L
3. **Recent Trades**: Last 20 trades, win/loss, strategy attribution
4. **Strategy Performance**: Per-strategy metrics, allocation
5. **Risk Metrics**: Portfolio heat, correlation, drawdown history
6. **Equity Curve**: Portfolio value over time

**Refresh:** Dashboard auto-refreshes every 60 seconds

---

## Backup & Recovery

### Daily Backup

```bash
# Backup database
cp trading.db backups/trading_$(date +%Y%m%d).db

# Backup config
cp config/trading_config.yaml backups/config_$(date +%Y%m%d).yaml

# Keep last 30 days of backups
find backups/ -name "trading_*.db" -mtime +30 -delete
```

### Recovery from Backup

```bash
# Restore database from backup
cp backups/trading_20260115.db trading.db

# Verify integrity
sqlite3 trading.db "PRAGMA integrity_check;"

# Restart system
python src/core/execution_engine.py
```

---

## Contact & Support

**Alpaca Support:** https://alpaca.markets/support  
**System Logs:** `logs/trading_system.log`  
**Database:** `sqlite3 trading.db`  
**Dashboard:** http://localhost:8501  
**Artifacts:** `artifacts/` directory

**Emergency Contact:** [Your email/phone]

---

**Remember:** This is real money. Monitor daily, especially in the first month. Never ignore alerts. When in doubt, halt trading and investigate.
