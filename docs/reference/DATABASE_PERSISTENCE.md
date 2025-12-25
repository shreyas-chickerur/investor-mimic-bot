# Database Persistence in GitHub Actions

## Problem

GitHub Actions runs in ephemeral containers - each run starts fresh with no data from previous runs.

## Solution

We use GitHub Actions artifacts to persist databases between runs.

---

## How It Works

### 1. **Download Previous Database** (Start of Run)
```yaml
- name: Download previous databases
  uses: dawidd6/action-download-artifact@v2
  with:
    workflow: daily-trading.yml
    name: trading-databases-latest
    path: data/
```
- Downloads databases from last successful run
- Continues even if no previous database exists (first run)

### 2. **Update Market Data** (Before Trading)
```yaml
- name: Update market data
  run: python3 scripts/update_data.py
```
- Fetches latest stock prices from Alpaca
- Updates `training_data.csv` with fresh data
- **Guarantees data is current**

### 3. **Sync Database** (Before Trading)
```yaml
- name: Sync database with Alpaca
  run: python3 scripts/sync_database.py
```
- Reconciles local database with Alpaca positions
- Ensures position counts match
- **Guarantees database accuracy**

### 4. **Execute Trading** (Main Run)
```yaml
- name: Run Multi-Strategy Trading System
  run: python3 src/multi_strategy_main.py
```
- Runs with fresh data and synced database
- Executes all 5 strategies
- Updates database with new trades

### 5. **Upload Databases** (End of Run)
```yaml
- name: Upload databases (latest)
  uses: actions/upload-artifact@v4
  with:
    name: trading-databases-latest
    retention-days: 90
```
- Saves updated databases as artifacts
- Two copies: timestamped + latest
- Next run downloads "latest"

---

## Data Freshness Guarantees

### ✅ Market Data
- **Updated every run** before trading
- Fetches latest prices from Alpaca API
- Maximum staleness: 0 minutes

### ✅ Database
- **Synced every run** with Alpaca positions
- Reconciles any discrepancies
- Always matches live account

### ✅ Strategy Performance
- **Persisted across runs** via artifacts
- Historical tracking maintained
- Performance metrics accumulate over time

---

## Workflow Sequence

```
1. Start GitHub Actions Run
   ↓
2. Download previous databases (if exist)
   ↓
3. Update market data (fresh prices)
   ↓
4. Sync database with Alpaca (reconcile positions)
   ↓
5. Run trading strategies (execute trades)
   ↓
6. Upload updated databases (for next run)
   ↓
7. End Run
```

**Next run starts at step 1 with databases from step 6**

---

## Local vs GitHub Actions

### Local Development
- Databases persist on your machine
- `data/trading_system.db` stays between runs
- `data/strategy_performance.db` accumulates history
- Data updates manual: `make update-data`

### GitHub Actions (Cloud)
- Databases downloaded from artifacts
- Updated during run
- Uploaded back to artifacts
- Data updates automatic every run

---

## Artifact Retention

| Artifact | Retention | Purpose |
|----------|-----------|---------|
| `trading-databases-latest` | 90 days | Used by next run |
| `trading-databases-{run_number}` | 30 days | Historical snapshots |
| `trading-logs-{run_number}` | 30 days | Execution logs |
| `strategy-report-{run_number}` | 30 days | Performance reports |

---

## Monitoring Database Health

### Check if Database is Current
```bash
# Download latest artifact from GitHub Actions
# Check last update time
sqlite3 data/strategy_performance.db "SELECT MAX(date) FROM strategy_performance"
```

### Verify Data Freshness
```bash
# Check training_data.csv date range
python3 -c "import pandas as pd; df = pd.read_csv('data/training_data.csv', index_col=0); print(f'Latest data: {df.index.max()}')"
```

### Force Full Refresh
```bash
# Manually trigger workflow with fresh start
# Go to Actions → Daily Paper Trading → Run workflow
# Databases will be recreated from Alpaca
```

---

## Troubleshooting

### Database Not Persisting
**Symptom:** Performance metrics reset every run

**Solution:**
1. Check artifact upload succeeded
2. Verify `trading-databases-latest` exists in Actions
3. Check download step didn't fail

### Stale Data
**Symptom:** Old prices in trading decisions

**Solution:**
1. Check `update_data.py` step succeeded
2. Verify Alpaca API credentials
3. Check for rate limiting errors

### Position Mismatch
**Symptom:** Database shows different positions than Alpaca

**Solution:**
1. Check `sync_database.py` step succeeded
2. Manually run: `make sync-db`
3. Verify no manual trades outside system

---

## Best Practices

1. **Always sync before trading** - Guaranteed by workflow
2. **Update data every run** - Guaranteed by workflow
3. **Keep artifacts** - 90-day retention for latest
4. **Monitor logs** - Check for update/sync failures
5. **Backup locally** - Download artifacts periodically

---

## Web Dashboard Compatibility

### Local Dashboard
```bash
make dashboard
```
- Uses local databases
- Shows real-time data
- Updated when you run `make run`

### GitHub Actions
- Databases only exist during workflow run
- Download artifacts to view locally
- Or use Alpaca dashboard for live view

**Note:** Web dashboard requires local database access. For cloud monitoring, use Alpaca's dashboard or download artifacts.
