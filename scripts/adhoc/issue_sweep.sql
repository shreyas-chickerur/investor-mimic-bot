-- Comprehensive issue sweep — run via: sqlite3 -header trading.db < scripts/adhoc/issue_sweep.sql
.mode column
.headers on
.echo on

-- 1. Signal terminal_state distribution (last 14d) — find signals stuck in transient states
SELECT terminal_state, COUNT(*) AS n
FROM signals
WHERE generated_at >= datetime('now','-14 days')
GROUP BY terminal_state ORDER BY n DESC;

-- 2. Signals never assigned a terminal_state (should be 0 for runs older than today)
SELECT s.name, COUNT(*) AS n
FROM signals sig JOIN strategies s ON sig.strategy_id=s.id
WHERE sig.generated_at < datetime('now','-1 day')
  AND (sig.terminal_state IS NULL OR sig.terminal_state = '')
GROUP BY s.id;

-- 3. Trades with NULL/zero pnl on SELL (should be 0)
SELECT t.id, t.executed_at, s.name, t.symbol, t.shares, t.exec_price, t.pnl
FROM trades t JOIN strategies s ON t.strategy_id=s.id
WHERE t.action='SELL' AND (t.pnl IS NULL OR t.pnl = 0)
LIMIT 20;

-- 4. Positions with current_price = 0 or NULL (mark-to-market never happened)
SELECT p.symbol, s.name, p.shares, p.avg_price, p.current_price, p.last_updated
FROM positions p JOIN strategies s ON p.strategy_id=s.id
WHERE p.shares != 0 AND (p.current_price IS NULL OR p.current_price = 0);

-- 5. Stale positions (last_updated > 3 days ago but still open)
SELECT p.symbol, s.name, p.shares, p.last_updated
FROM positions p JOIN strategies s ON p.strategy_id=s.id
WHERE p.shares != 0 AND p.last_updated < datetime('now','-3 days');

-- 6. trade_pnl_detail correctness — does row count match SELL count?
SELECT 'trade_pnl_detail' AS src, COUNT(*) FROM trade_pnl_detail
UNION ALL SELECT 'trades_sell_with_pnl', COUNT(*) FROM trades WHERE action='SELL' AND pnl IS NOT NULL;

-- 7. trade_pnl_detail with absurd gross_pnl_pct (data bug)
SELECT * FROM trade_pnl_detail WHERE gross_pnl_pct > 1.0 OR gross_pnl_pct < -0.5 LIMIT 10;

-- 8. Recent strategy_performance snapshots (is health scorer running?)
SELECT s.name, MAX(sp.snapshot_date) AS last_snapshot, COUNT(*) AS total_snapshots
FROM strategy_performance sp JOIN strategies s ON sp.strategy_id=s.id
GROUP BY s.id ORDER BY last_snapshot DESC;

-- 9. XLV mystery — was it really sold and re-bought, or is BROKER_SYNC a separate position?
SELECT t.executed_at, s.name, t.action, t.shares, t.exec_price, t.pnl
FROM trades t JOIN strategies s ON t.strategy_id=s.id
WHERE t.symbol='XLV' ORDER BY t.executed_at;

-- 10. Are there any orphan signals (referenced strategy_id doesn't exist)?
SELECT COUNT(*) AS orphan_signals
FROM signals WHERE strategy_id NOT IN (SELECT id FROM strategies);

-- 11. Distribution of run_id volume (any run with abnormally low signal count = silent failure?)
SELECT run_id, substr(run_id,1,10) AS day, COUNT(*) AS signals
FROM signals
WHERE generated_at >= datetime('now','-14 days')
GROUP BY run_id ORDER BY day DESC, signals DESC LIMIT 20;

-- 12. Recent kill-switch / system_state activity
SELECT key, substr(value,1,80), timestamp FROM system_state ORDER BY timestamp DESC LIMIT 10;

-- 13. Cash leak check — trades vs cash delta consistency
SELECT 'recent BUY notional', ROUND(SUM(notional),2) FROM trades WHERE action='BUY' AND executed_at >= date('now','-14 days')
UNION ALL SELECT 'recent SELL notional', ROUND(SUM(notional),2) FROM trades WHERE action='SELL' AND executed_at >= date('now','-14 days');

-- 14. Any positions where avg_price = 0 (free shares — bug indicator)
SELECT * FROM positions WHERE shares != 0 AND avg_price <= 0;
