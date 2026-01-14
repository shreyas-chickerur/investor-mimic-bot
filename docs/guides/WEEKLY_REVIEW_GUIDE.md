# Weekly Review Guide

This guide provides step-by-step instructions for conducting weekly reviews of the trading system to monitor performance, identify issues, and optimize operations.

---

## Overview

**Frequency:** Weekly (recommended: Sunday evening or Monday morning)  
**Duration:** 15-30 minutes  
**Purpose:** Monitor system health, analyze performance, identify optimization opportunities

---

## Quick Review Checklist

- [ ] Check daily email digests (7 days)
- [ ] Review reconciliation status
- [ ] Analyze signal funnel patterns
- [ ] Check strategy health scores
- [ ] Review rejection reasons
- [ ] Verify data quality
- [ ] Check for errors/warnings
- [ ] Review P&L and drawdown

---

## Step-by-Step Review Process

### 1. Check Daily Email Digests (5 min)

Review the last 7 daily email summaries to get a high-level overview.

**What to Look For:**
- Consistent execution (no missed days)
- Reconciliation status (should be PASS every day)
- Trade volume (are strategies generating signals?)
- Any error alerts

**Action Items:**
- If reconciliation failed: Run `python3 scripts/sync_broker_state.py`
- If no trades for 3+ days: Check data quality and market conditions
- If error alerts: Review logs and fix issues

---

### 2. Review Weekly Artifacts (10 min)

#### Check Latest 7 Daily Artifacts

```bash
# View last 7 artifacts
ls -lt artifacts/json/ | head -8

# Quick check of reconciliation status
for file in artifacts/json/2026-01-*.json; do
    echo "$(basename $file):"
    python3 -c "
import json
with open('$file') as f:
    data = json.load(f)
    print(f\"  Reconciliation: {data['system_health']['reconciliation_status']}\")
    print(f\"  Trades: {len(data.get('executed_signals', []))}\")
    print(f\"  Daily P&L: \${data['performance']['daily_pnl']:.2f}\")
"
done
```

#### Analyze Signal Funnel Patterns

```bash
# Check signal funnel for each strategy
ls artifacts/funnel/signal_funnel_*_$(date +%Y%m)*.json | tail -5 | while read file; do
    echo "$(basename $file):"
    python3 -c "
import json
with open('$file') as f:
    data = json.load(f)
    funnel = data['funnel']
    print(f\"  Raw: {funnel['raw_signals']}\")
    print(f\"  After regime: {funnel['after_regime']}\")
    print(f\"  After correlation: {funnel['after_correlation']}\")
    print(f\"  After risk: {funnel['after_risk']}\")
    print(f\"  Executed: {funnel['executed']}\")
    print(f\"  Conversion: {data['conversion_rates']['overall_conversion']:.1%}\")
"
done
```

**What to Look For:**
- **High rejection rates** (>80%): May indicate overly strict filters
- **Low conversion** (<10%): Check if correlation/risk filters too aggressive
- **Zero raw signals**: Strategy not finding opportunities (market conditions or data issue)

---

### 3. Check Strategy Health Scores (5 min)

```bash
# Generate strategy health summary
python3 -c "
import sys
sys.path.insert(0, 'src')
from database import TradingDatabase
from strategy_health_scorer import StrategyHealthScorer

db = TradingDatabase('trading.db')
scorer = StrategyHealthScorer(db)

# Get all strategies
strategies = db.get_all_strategies()
strategy_list = [(s['id'], s['name']) for s in strategies]

# Generate health summary
summary = scorer.generate_health_summary(strategy_list)

print('='*80)
print('STRATEGY HEALTH SUMMARY')
print('='*80)
for strategy_name, health in summary.items():
    print(f'\n{strategy_name}:')
    print(f\"  Health Score: {health.get('health_score', 'N/A')}\")
    print(f\"  Status: {health.get('status', 'N/A')}\")
    print(f\"  Trades (7d): {health.get('trades_7d', 0)}\")
    print(f\"  Trades (30d): {health.get('trades_30d', 0)}\")
    print(f\"  Win Rate: {health.get('win_rate', 0):.1%}\")
    print(f\"  Avg P&L: \${health.get('avg_pnl', 0):.2f}\")
"
```

**What to Look For:**
- **Unhealthy strategies**: Health score < 50
- **Low win rates**: <40% (may need review)
- **Negative avg P&L**: Strategy losing money
- **Zero trades**: Not generating signals

**Action Items:**
- If strategy unhealthy for 2+ weeks: Consider disabling via `STRATEGY_DISABLED_LIST`
- If multiple strategies unhealthy: Check market regime (may be unfavorable conditions)

---

### 4. Review Rejection Reasons (5 min)

```bash
# Analyze rejection patterns
python3 -c "
import json
import os
from collections import Counter

rejection_files = [f for f in os.listdir('artifacts/funnel') if 'rejections' in f]
recent_files = sorted(rejection_files)[-7:]  # Last 7 days

all_rejections = []
for file in recent_files:
    with open(f'artifacts/funnel/{file}') as f:
        data = json.load(f)
        for stage, rejections in data.get('rejections_by_stage', {}).items():
            for rejection in rejections:
                all_rejections.append((stage, rejection.get('reason', 'unknown')))

# Count by stage and reason
stage_counts = Counter([r[0] for r in all_rejections])
reason_counts = Counter([r[1] for r in all_rejections])

print('='*80)
print('REJECTION ANALYSIS (Last 7 Days)')
print('='*80)
print('\nBy Stage:')
for stage, count in stage_counts.most_common():
    print(f'  {stage}: {count}')

print('\nBy Reason:')
for reason, count in reason_counts.most_common(10):
    print(f'  {reason}: {count}')
"
```

**What to Look For:**
- **High correlation rejections**: Portfolio may be too concentrated
- **High risk rejections**: Portfolio heat limit being hit frequently
- **Data quality rejections**: Check data freshness and quality

**Action Items:**
- If >50% correlation rejections: Consider relaxing correlation threshold
- If >30% risk rejections: May need to increase heat limit or reduce position sizes
- If data quality issues: Run `python3 scripts/update_data.py`

---

### 5. Check System Logs (5 min)

```bash
# Check for errors in last 7 days
echo "Errors in last 7 days:"
grep -i "error\|exception\|failed" logs/multi_strategy.log | tail -20

# Check for warnings
echo -e "\nWarnings in last 7 days:"
grep -i "warning" logs/multi_strategy.log | tail -20

# Check kill switch activations
echo -e "\nKill switch activations:"
grep -i "kill switch\|trading halted" logs/multi_strategy.log | tail -10
```

**What to Look For:**
- **Repeated errors**: Same error multiple times (needs fixing)
- **API errors**: Alpaca connection issues
- **Kill switch activations**: Understand why trading was halted

---

### 6. Review Performance Metrics (5 min)

```bash
# Weekly P&L summary
python3 -c "
import sys
sys.path.insert(0, 'src')
from database import TradingDatabase
from datetime import datetime, timedelta

db = TradingDatabase('trading.db')

# Get trades from last 7 days
seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT 
        COUNT(*) as trade_count,
        SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) as losses,
        SUM(realized_pnl) as total_pnl,
        AVG(realized_pnl) as avg_pnl,
        MAX(realized_pnl) as best_trade,
        MIN(realized_pnl) as worst_trade
    FROM trades
    WHERE exit_date >= ?
''', (seven_days_ago,))

result = cursor.fetchone()
conn.close()

if result and result[0] > 0:
    trade_count, wins, losses, total_pnl, avg_pnl, best, worst = result
    win_rate = (wins / trade_count * 100) if trade_count > 0 else 0
    
    print('='*80)
    print('WEEKLY PERFORMANCE (Last 7 Days)')
    print('='*80)
    print(f'Total Trades: {trade_count}')
    print(f'Wins: {wins} | Losses: {losses}')
    print(f'Win Rate: {win_rate:.1f}%')
    print(f'Total P&L: \${total_pnl:.2f}')
    print(f'Avg P&L per Trade: \${avg_pnl:.2f}')
    print(f'Best Trade: \${best:.2f}')
    print(f'Worst Trade: \${worst:.2f}')
else:
    print('No trades in last 7 days')
"
```

**What to Look For:**
- **Win rate**: Should be 45-55% (outside this range may indicate issues)
- **Total P&L**: Positive is good, but small sample size (7 days)
- **Avg P&L**: Should be positive over time
- **Large losses**: Review if any single trade lost >2% of portfolio

---

### 7. Check Data Quality (2 min)

```bash
# Check data freshness
python3 -c "
import pandas as pd
from datetime import datetime

df = pd.read_csv('data/training_data.csv', index_col=0)
df.index = pd.to_datetime(df.index)

latest_date = df.index.max()
age_hours = (datetime.now() - latest_date).total_seconds() / 3600

print(f'Data freshness: {age_hours:.1f} hours old')
print(f'Latest date: {latest_date}')

if age_hours > 72:
    print('⚠️  WARNING: Data is stale (>72 hours)')
    print('   Action: Run python3 scripts/update_data.py')
else:
    print('✅ Data is fresh')
"
```

**Action Items:**
- If data >72 hours old: Run `python3 scripts/update_data.py`

---

## Weekly Review Template

Use this template to document your weekly review:

```markdown
# Weekly Review - [Date]

## Summary
- Total trades: X
- Win rate: X%
- Weekly P&L: $X
- Issues found: X

## Strategy Performance
- RSI Mean Reversion: [Health score, trades, P&L]
- ML Momentum: [Health score, trades, P&L]
- MA Crossover: [Health score, trades, P&L]
- News Sentiment: [Health score, trades, P&L]
- Volatility Breakout: [Health score, trades, P&L]

## Signal Funnel
- Average conversion rate: X%
- Main rejection reasons: [List top 3]

## Issues & Actions
1. [Issue]: [Action taken]
2. [Issue]: [Action taken]

## Notes
[Any observations, market conditions, etc.]

## Next Week Focus
[What to monitor or optimize]
```

---

## Quick Commands Reference

```bash
# Update market data
python3 scripts/update_data.py

# Sync database with broker
python3 scripts/sync_broker_state.py

# Run manual execution (dry run)
DRY_RUN=true python3 src/execution_engine.py

# Check broker positions
make positions

# View recent logs
make logs

# Generate performance report
python3 scripts/view_performance.py
```

---

## Red Flags to Watch For

### Critical (Act Immediately)
- ❌ Reconciliation failures 2+ days in a row
- ❌ Circuit breaker triggered
- ❌ Drawdown >8%
- ❌ Multiple API errors

### Warning (Monitor Closely)
- ⚠️ Win rate <40% for 2+ weeks
- ⚠️ No trades for 5+ days
- ⚠️ Data >72 hours old
- ⚠️ All strategies unhealthy

### Informational (Review When Convenient)
- ℹ️ High rejection rates (>70%)
- ℹ️ Low signal generation
- ℹ️ Single strategy dominating (>60% of trades)

---

## Optimization Opportunities

Based on your weekly review, consider these optimizations:

### If Rejection Rate >70%
- Relax correlation threshold (currently 0.7)
- Increase portfolio heat limit (currently 30%)
- Review regime detection settings

### If Win Rate <45%
- Review strategy parameters
- Check if market regime unfavorable
- Consider disabling underperforming strategies

### If No Signals Generated
- Check data quality and freshness
- Review market conditions (low volatility?)
- Verify strategies are enabled

### If Drawdown >5%
- Reduce position sizes
- Tighten stop losses
- Review risk management settings

---

## Monthly Deep Dive (Optional)

Once a month, perform a deeper analysis:

1. **Backtest validation**: Compare live results vs backtest expectations
2. **Correlation analysis**: Check if portfolio correlation has changed
3. **Regime analysis**: Review performance by market regime
4. **Strategy optimization**: Consider parameter adjustments
5. **Cost analysis**: Review execution costs and slippage

---

## Support & Troubleshooting

**Common Issues:**

1. **Reconciliation failures**: Run `python3 scripts/sync_broker_state.py`
2. **Stale data**: Run `python3 scripts/update_data.py`
3. **No signals**: Check `artifacts/funnel/why_no_trade_summary_*.json`
4. **Errors in logs**: Review `logs/multi_strategy.log` and `logs/api_error.log`

**Documentation:**
- Full troubleshooting: `docs/guides/USAGE_GUIDE.md`
- Live trading runbook: `docs/guides/LIVE_TRADING_RUNBOOK.md`
- Reconciliation fix: `docs/guides/RECONCILIATION_FIX.md`

---

**Remember:** The goal is to monitor system health, not to constantly tweak parameters. Let the system run and only make changes when clear issues are identified.
