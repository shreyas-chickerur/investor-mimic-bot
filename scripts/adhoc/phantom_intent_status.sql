.mode column
.headers on

-- What's the local status of the phantom-creating BUY intents?
SELECT oi.created_at, oi.symbol, oi.side, oi.target_qty, oi.status, oi.broker_order_id
FROM order_intents oi
WHERE oi.symbol IN ('ABBV', 'AMZN', 'AMD')
  AND oi.side='BUY'
  AND oi.created_at >= datetime('now','-10 days')
ORDER BY oi.created_at DESC;

-- How many intents are FILLED locally (potential paper-mode phantoms)?
SELECT status, COUNT(*), MIN(created_at) AS oldest
FROM order_intents WHERE side='BUY' GROUP BY status;
