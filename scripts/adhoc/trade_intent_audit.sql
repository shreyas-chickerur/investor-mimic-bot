.mode column
.headers on

-- Trades whose order_id has NO matching order_intents row at all
SELECT t.executed_at, s.name, t.action, t.symbol, t.shares, t.exec_price, t.order_id
FROM trades t JOIN strategies s ON t.strategy_id=s.id
WHERE t.order_id IS NOT NULL
  AND t.order_id NOT IN (SELECT broker_order_id FROM order_intents WHERE broker_order_id IS NOT NULL)
ORDER BY t.executed_at DESC LIMIT 20;

-- Counts: trades with vs without matching intent
SELECT
  SUM(CASE WHEN t.order_id IN (SELECT broker_order_id FROM order_intents WHERE broker_order_id IS NOT NULL) THEN 1 ELSE 0 END) AS with_intent,
  SUM(CASE WHEN t.order_id IS NOT NULL AND t.order_id NOT IN (SELECT broker_order_id FROM order_intents WHERE broker_order_id IS NOT NULL) THEN 1 ELSE 0 END) AS no_intent_match,
  SUM(CASE WHEN t.order_id IS NULL THEN 1 ELSE 0 END) AS no_order_id
FROM trades t;

-- Trades whose order_id matches an intent that's STILL ACKED (i.e. local says filled, broker side never confirmed)
SELECT t.executed_at, s.name, t.action, t.symbol, t.shares, oi.status AS intent_status
FROM trades t JOIN strategies s ON t.strategy_id=s.id
JOIN order_intents oi ON t.order_id = oi.broker_order_id
WHERE oi.status != 'FILLED'
ORDER BY t.executed_at DESC LIMIT 20;

-- Cash-leak proxy: BUY-SELL imbalance per strategy (last 14d)
SELECT s.name,
  ROUND(SUM(CASE WHEN t.action='BUY' THEN t.notional ELSE 0 END),2) AS buy_notional,
  ROUND(SUM(CASE WHEN t.action='SELL' THEN t.notional ELSE 0 END),2) AS sell_notional,
  ROUND(SUM(CASE WHEN t.action='BUY' THEN -t.notional ELSE t.notional END),2) AS net_cash_impact
FROM trades t JOIN strategies s ON t.strategy_id=s.id
WHERE t.executed_at >= datetime('now','-14 days')
GROUP BY s.id ORDER BY buy_notional DESC;
