# Bug Fix Log

*Historical record of critical fixes. See SIGNAL_GENERATION_GUIDE.md for current strategy reference.*

---

## 2026-03-03 — Critical Strategy Logic Fixes (Paper Trading)

### RSI VWAP Exit (High Impact)
- **What broke:** The `vwap` column in `training_data.csv` is a trailing 20-day VWAP
  (~70% of current close). `price >= vwap` was always True, causing every position
  to exit immediately — zero holding periods, zero P&L.
- **Fix:** Removed VWAP exit. Exits are now RSI > 55 or 20-day time limit only.
- **File:** `src/strategies/strategy_rsi_mean_reversion.py`

### Factor Momentum Ranking Collapse (High Impact)
- **What broke:** `_rank_normalize(sigmoid(value))` applied independently to each symbol
  compressed all composite scores into 0.50–0.65. "Top 5" selection was nearly random.
- **Fix:** Cross-sectional `DataFrame.rank(pct=True)` across the full universe.
- **File:** `src/strategies/strategy_factor_momentum.py`

### ML Momentum Signal Blackout (High Impact)
- **What broke:** `min_confidence=0.55` killed all signals — logistic regression rarely
  exceeds 0.55 on financial data. Also: single `class_weight` default biased predictions.
- **Fix:** `min_confidence=0.52`, `class_weight='balanced'`, daily retraining via
  `_train_date`, future return threshold 1% → 0.5%.
- **Files:** `src/strategies/strategy_ml_momentum.py`, `config/trading_config.yaml`

### Signal Throttle Blocking Factor Momentum (Medium Impact)
- **What broke:** Hardcoded `signals[:3]` cut Factor Momentum's `top_n=5` to 3.
- **Fix:** `signals[:getattr(strategy, 'top_n', 5)]`
- **File:** `src/core/execution_engine.py`

---

## 2026-01-28 — Production Bug Fixes (GitHub Actions)

### Strategy Initialization
- Old disabled strategies (News Sentiment, MA Crossover, Volatility Breakout) were loaded
  from DB and run. Fixed by enforcing canonical 4-strategy set.

### Wash Trade Prevention
- Cross-strategy BUY/SELL same symbol same run triggered Alpaca wash-trade rejection.
  Fixed with per-run bought/sold sets.

### VIX Hardcoded
- `RegimeDetector.get_vix_level()` hardcoded 18.0. Fixed to 20-day realized volatility proxy.

### Database Schema Mismatch
- `setup_database.py` missing columns that `database.py` expected. Fixed to match.

### Duplicate Logging
- `stop_loss set` logged twice. Removed duplicate.
