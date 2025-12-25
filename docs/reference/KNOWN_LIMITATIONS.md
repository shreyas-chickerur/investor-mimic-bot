# Known Limitations and Fallback Behaviors

**Last updated:** 2025-12-24

This document describes known limitations, fallback behaviors, and proxy implementations in the trading system.

---

## 1. News Sentiment Strategy - API Key Fallback

**Limitation:** News sentiment strategy requires `NEWS_API_KEY` to fetch real sentiment data.

**Behavior without API key:**
- Strategy falls back to momentum-based proxy
- Uses price momentum as sentiment indicator
- Logs warning: "News sentiment provider not configured"
- Strategy continues to function but without true sentiment analysis

**Impact:**
- Not a crash or error
- Strategy generates signals based on momentum instead of news
- Less accurate sentiment representation

**Fix:**
- Set `NEWS_API_KEY` environment variable
- Get API key from: https://newsapi.org/

**Code location:** `src/news_sentiment.py`, `src/strategies/strategy_news_sentiment.py`

---

## 2. Regime Detection - VIX Proxy

**Limitation:** System uses realized volatility proxy instead of real VIX feed.

**Current implementation:**
- Calculates realized volatility from price returns
- Uses simple moving averages for trend detection
- Thresholds: Low vol <15%, High vol >25%

**Why it's a proxy:**
- No real-time VIX data feed
- Realized volatility lags actual VIX
- May miss rapid volatility regime shifts

**Impact:**
- Regime detection works but is approximate
- May be slower to detect regime changes
- Good enough for paper trading validation

**Future improvement:**
- Add real VIX data feed (CBOE)
- Use VIX futures for forward-looking regime detection

**Code location:** `src/regime_detector.py`

---

## 3. P&L Metrics - Currently Placeholder

**Limitation:** Daily P&L and drawdown metrics are currently set to 0.0 in artifacts.

**Current state:**
- `daily_pnl`: 0.0 (placeholder)
- `cumulative_pnl`: 0.0 (placeholder)
- `drawdown`: 0.0 (placeholder)
- `max_drawdown`: 0.0 (placeholder)

**Why:**
- Runner doesn't calculate real P&L yet
- Requires tracking: entry prices, exit prices, position sizes, costs

**Impact:**
- Artifacts don't show real profit/loss
- Can't track actual trading performance
- Reconciliation still works (uses positions, not P&L)

**Fix needed:**
- Wire portfolio value tracking
- Calculate daily P&L from position changes
- Track cumulative P&L over time
- Calculate drawdown from peak portfolio value

**Code location:** `src/daily_artifact_writer.py`, `src/multi_strategy_main.py`

---

## 4. Filled Orders - Based on Execution Not Confirmation

**Limitation:** Artifacts list "filled_orders" based on executed trades, not confirmed fills from Alpaca.

**Current behavior:**
- `filled_orders` = trades marked as executed by runner
- No verification that Alpaca actually filled the order
- May overstate fills if orders were rejected or pending

**Potential issues:**
- Order submitted → marked as filled
- But Alpaca rejects it → still shows as filled in artifact
- Reconciliation will catch this (discrepancy between local and broker)

**Impact:**
- Artifacts may show more fills than actually occurred
- Reconciliation is the source of truth
- Not a critical issue if reconciliation is enabled

**Fix needed:**
- Query Alpaca for actual fill confirmations
- Update artifacts with confirmed fills only
- Add "pending_orders" field for submitted but unconfirmed

**Code location:** `src/multi_strategy_main.py`

---

## 5. Broker Credentials Required for Reconciliation

**Requirement:** Broker reconciliation requires `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`.

**What happens without credentials:**
- `BrokerReconciler.get_broker_state()` fails
- Error: "You must supply a method of authentication"
- System cannot verify broker state
- Reconciliation step fails

**This is expected behavior:**
- Reconciliation must connect to broker
- Cannot verify state without API access
- Not a bug, just a requirement

**Solution:**
- Set environment variables before running
- Or add to `.env` file
- See: `docs/ADD_GITHUB_SECRETS.md`

**Code location:** `src/broker_reconciler.py`

---

## 6. Artifact Writer Wiring

**Status:** ✅ Wired and functional

**Implementation:**
- `DailyArtifactWriter` exists in `src/daily_artifact_writer.py`
- Called by runner in `src/multi_strategy_main.py`
- Generates both JSON and Markdown artifacts
- Artifacts saved to `artifacts/json/` and `artifacts/markdown/`

**Verification:**
```bash
# Check if artifacts are being generated
ls -la artifacts/json/
ls -la artifacts/markdown/
```

**Code location:** `src/daily_artifact_writer.py`, `src/multi_strategy_main.py`

---

## Summary

| Issue | Status | Impact | Fix Priority |
|-------|--------|--------|--------------|
| News sentiment fallback | Working as designed | Low (strategy still functions) | Low |
| Regime VIX proxy | Working as designed | Low (good enough for Phase 5) | Medium |
| P&L metrics placeholder | Needs fix | Medium (can't track performance) | High |
| Filled orders not confirmed | Needs fix | Low (reconciliation catches it) | Medium |
| Broker credentials required | Expected behavior | None (requirement) | N/A |
| Artifact writer wiring | ✅ Complete | None | N/A |

---

## Recommendations

### Before Phase 5 Day 1:
1. ✅ Verify artifact writer is working (check `artifacts/` folder)
2. ✅ Set Alpaca credentials (required for reconciliation)
3. ⚠️ Consider setting `NEWS_API_KEY` (optional but recommended)

### During Phase 5:
1. Monitor reconciliation status (source of truth for fills)
2. Ignore P&L metrics in artifacts (placeholders)
3. Regime detection works but is approximate

### After Phase 5:
1. Wire real P&L calculation (high priority)
2. Add confirmed fill tracking (medium priority)
3. Consider real VIX feed (medium priority)
4. Add NEWS_API_KEY for true sentiment (low priority)
