# Windsurf Run Steps & Local Requirements

This doc lists the exact commands I attempted to run plus what you need
to run locally (or in Windsurf) to test with today’s data.

## Environment variables (required)

Set these in Windsurf (or your shell) before running live/data steps:

```bash
export ALPACA_API_KEY="YOUR_KEY"
export ALPACA_SECRET_KEY="YOUR_SECRET"
```

Optional but recommended:

```bash
# Only needed for live trading (paper=false)
export ALPACA_LIVE_ENABLED=true

# Auto-refresh market data if validation fails
export AUTO_UPDATE_DATA=true

# Enable broker reconciliation gate
export ENABLE_BROKER_RECONCILIATION=true

# Optional news sentiment provider
export NEWS_SENTIMENT_PROVIDER=newsapi
export NEWS_API_KEY="YOUR_NEWSAPI_KEY"
```

## Commands I tried (and why)

### 1) Update market data (today’s data)
```bash
python3 scripts/update_data.py
```
This failed here due to missing Alpaca credentials.

### 2) Generate signals for the 5 strategies
```bash
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))
import pandas as pd
from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from strategies.strategy_ml_momentum import MLMomentumStrategy
from strategies.strategy_news_sentiment import NewsSentimentStrategy
from strategies.strategy_ma_crossover import MACrossoverStrategy
from strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy

data_file = Path('data/training_data.csv')
if not data_file.exists():
    raise SystemExit('data/training_data.csv not found')

df = pd.read_csv(data_file, index_col=0)
df.index = pd.to_datetime(df.index)
latest_date = df.index.max()
cutoff_date = latest_date - pd.Timedelta(days=100)
df = df[df.index >= cutoff_date].copy()

strategies = [
    RSIMeanReversionStrategy(1, 20000),
    MLMomentumStrategy(2, 20000),
    NewsSentimentStrategy(3, 20000),
    MACrossoverStrategy(4, 20000),
    VolatilityBreakoutStrategy(5, 20000),
]

print(f"Latest data date: {latest_date.date()}")
for strat in strategies:
    signals = strat.generate_signals(df)
    print(f"{strat.name}: {len(signals)} signals")
    for signal in signals[:5]:
        print(f"  {signal['action']} {signal['symbol']} @ {signal['price']:.2f} ({signal.get('reasoning','')})")
PY
```

## Recommended run sequence (Windsurf or local)

```bash
# 1) Install dependencies
pip install -r requirements.txt

# 2) Pull today’s data
python3 scripts/update_data.py

# 3) Run signal generation for all 5 strategies
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))
import pandas as pd
from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from strategies.strategy_ml_momentum import MLMomentumStrategy
from strategies.strategy_news_sentiment import NewsSentimentStrategy
from strategies.strategy_ma_crossover import MACrossoverStrategy
from strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy

df = pd.read_csv('data/training_data.csv', index_col=0)
df.index = pd.to_datetime(df.index)
latest_date = df.index.max()
df = df[df.index >= latest_date - pd.Timedelta(days=100)]

strategies = [
    RSIMeanReversionStrategy(1, 20000),
    MLMomentumStrategy(2, 20000),
    NewsSentimentStrategy(3, 20000),
    MACrossoverStrategy(4, 20000),
    VolatilityBreakoutStrategy(5, 20000),
]

print(f"Latest data date: {latest_date.date()}")
for strat in strategies:
    signals = strat.generate_signals(df)
    print(f"{strat.name}: {len(signals)} signals")
    for signal in signals[:5]:
        print(f"  {signal['action']} {signal['symbol']} @ {signal['price']:.2f} ({signal.get('reasoning','')})")
PY
```

## Optional: run the full live runner (paper or live)

```bash
python3 src/multi_strategy_main.py
```

If you want live trading, ensure:
```bash
export ALPACA_PAPER=false
export ALPACA_LIVE_ENABLED=true
```

