.mode column
.headers on

-- All SELL order_intents (last 30 days)
SELECT created_at, status, symbol, target_qty, broker_order_id
FROM order_intents WHERE side='SELL' AND created_at >= datetime('now','-30 days')
ORDER BY created_at DESC;

-- Counts of SELL intents by status
SELECT status, COUNT(*) FROM order_intents WHERE side='SELL' GROUP BY status;

-- Try to match each SELL trade to a SELL intent by (strategy, symbol, day, qty)
-- since broker_order_id linkage is missing
SELECT t.executed_at, t.symbol, t.shares,
       (SELECT intent_id FROM order_intents oi
        WHERE oi.side='SELL' AND oi.symbol=t.symbol
          AND oi.target_qty=t.shares
          AND date(oi.created_at)=date(t.executed_at)
          AND oi.strategy_id=t.strategy_id
        LIMIT 1) AS matched_intent
FROM trades t WHERE t.action='SELL'
ORDER BY t.executed_at DESC LIMIT 25;
