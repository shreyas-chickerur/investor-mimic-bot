.mode column
.headers on

-- All order_intents touching XLV
SELECT created_at, status, side, target_qty, broker_order_id, COALESCE(error_message,'') AS err
FROM order_intents WHERE symbol='XLV' ORDER BY created_at;

-- Cross-check: trades vs intents for XLV
SELECT t.executed_at, t.action, t.shares, t.exec_price, t.order_id, t.run_id
FROM trades t WHERE t.symbol='XLV' ORDER BY t.executed_at;

-- Recon discrepancies mentioning XLV
SELECT snapshot_date, snapshot_type, reconciliation_status,
       substr(discrepancies_json,1,400) AS discr
FROM broker_state
WHERE discrepancies_json LIKE '%XLV%' OR snapshot_type='SYNC'
ORDER BY snapshot_date DESC LIMIT 10;

-- Was the 2026-05-21 run signals-low for ALL strategies or just some?
SELECT s.name, COUNT(*) AS sig_count
FROM signals sig JOIN strategies s ON sig.strategy_id=s.id
WHERE sig.run_id LIKE '20260521%' OR sig.run_id LIKE '20260527_05395%'
GROUP BY sig.run_id, s.id ORDER BY sig.run_id, s.id;
