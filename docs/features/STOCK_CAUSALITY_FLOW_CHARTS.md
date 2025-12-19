# Stock Causality Flow Charts

Detailed causal analysis for stock recommendations with interactive flow charts.

---

## Overview

The Stock Causality Flow Chart system provides transparent, data-driven explanations for every stock recommendation. Each recommendation includes an interactive flow chart showing the chain of events and factors that led to the system's decision.

## Features

### Real Data Sources (No Hallucination)

All analysis is based on real, scraped data from:

- **News Sources**: Alpha Vantage, Finnhub
- **SEC Filings**: 13F institutional holdings, Form 4 insider trades
- **Earnings Reports**: Quarterly earnings, EPS surprises
- **Technical Indicators**: RSI, MACD, volume, price movements
- **Market Data**: Real-time price changes, volume analysis

### Interactive Flow Charts

Each recommendation includes:

1. **Step-by-step causal chain** showing how events led to the recommendation
2. **Expandable details** for each step (click to reveal)
3. **Color-coded impact** (green = positive, red = negative, gray = neutral)
4. **Source attribution** for every data point
5. **Timestamps** showing when events occurred

### Event Types Analyzed

**News Events**
- Recent news articles (last 30 days)
- Sentiment analysis (bullish/bearish/neutral)
- Source and relevance scoring

**Earnings Events**
- Quarterly earnings reports
- EPS surprises (beat/miss estimates)
- Revenue growth trends

**Insider Trading**
- Recent Form 4 filings (last 90 days)
- Buy/sell transactions by executives
- Transaction values and timing

**Institutional Activity**
- 13F filing changes (last 180 days)
- New positions, increases, decreases
- Major institutional investors

**Technical Signals**
- Overbought/oversold conditions (RSI)
- Momentum indicators (MACD crossovers)
- Volume analysis
- Trend strength (ADX)

**Price Movements**
- Significant price changes (>5%)
- Volume spikes
- Support/resistance levels

---

## How It Works

### 1. Data Collection

When a recommendation is generated, the system:

```python
from services.analysis.stock_causality_analyzer import analyze_stock_recommendation

causality_data = analyze_stock_recommendation(
    ticker="AAPL",
    action="BUY",
    signal_score=0.85
)
```

This scrapes and analyzes:
- Last 30 days of news
- Last 2 quarters of earnings
- Last 90 days of insider trades
- Last 180 days of institutional activity
- Last 30 days of technical signals
- Last 30 days of price movements

### 2. Event Analysis

Each event is analyzed for:
- **Impact**: positive, negative, or neutral
- **Magnitude**: 0-1 scale of importance
- **Timestamp**: when it occurred
- **Source**: where the data came from

### 3. Causal Chain Building

Events are sorted and organized into a logical flow:

```
Market Context
    ↓
Key Event 1 (e.g., Earnings Beat)
    ↓
Key Event 2 (e.g., Insider Buying)
    ↓
Key Event 3 (e.g., Positive News)
    ↓
Technical Signal (e.g., MACD Crossover)
    ↓
BUY Recommendation
```

### 4. Email Integration

Flow charts are automatically included in daily digest emails with:
- Interactive dropdowns for each step
- Clean, professional styling
- Mobile-responsive design

---

## Example Flow Chart

### AAPL - BUY Recommendation

**Step 1: Market Context**
Analyzed 15 events over the past 30-90 days
- Details: Found 10 positive signals and 5 negative signals

**Step 2: Q4 Earnings Report**
Reported EPS: $1.52 vs Est: $1.39. Surprise: +9.4%
- Source: Alpha Vantage | Date: 2024-01-25 | Impact: Positive

**Step 3: Insider BUY**
Tim Cook bought 50,000 shares at $175.00 ($8,750,000 total)
- Source: SEC Form 4 | Date: 2024-01-28 | Impact: Positive

**Step 4: Institutional INCREASED**
Vanguard increased position: 5,000,000 shares (+12.5%)
- Source: 13F Filing | Date: 2024-02-01 | Impact: Positive

**Step 5: Bullish MACD Crossover**
MACD crossed above signal line, indicating bullish momentum
- Source: Technical Analysis | Date: 2024-02-10 | Impact: Positive

**Step 6: BUY Recommendation**
Based on analysis of all factors, system recommends BUY
- Signal Score: 0.85 | Confidence: 85%

---

## Configuration

### API Keys Required

```bash
# .env file
ALPHA_VANTAGE_API_KEY=your_key  # For news and earnings
FINNHUB_API_KEY=your_key        # For additional news (optional)
```

### Database Tables Used

- `insider_trades` - Form 4 insider transactions
- `holdings` - 13F institutional holdings
- `technical_indicators` - Technical analysis data
- `price_history` - Historical price data
- `news_articles` - Stored news articles

---

## Usage

### In Daily Digest

Flow charts are automatically generated for all recommendations in the daily digest email. No additional configuration needed.

### Manual Analysis

```python
from services.analysis.stock_causality_analyzer import StockCausalityAnalyzer

analyzer = StockCausalityAnalyzer()
result = analyzer.analyze_recommendation(
    ticker="MSFT",
    action="SELL",
    signal_score=0.72
)

# Access causal chain
for step in result["causal_chain"]:
    print(f"Step {step['step']}: {step['title']}")
    print(f"  {step['description']}")
```

### Generate Flow Chart HTML

```python
from services.monitoring.flow_chart_generator import generate_flow_chart_html

html = generate_flow_chart_html(causality_data)
# Returns interactive HTML for embedding
```

---

## Data Quality

### No Hallucination Policy

All data points must be:
1. **Scraped from real sources** (APIs, databases)
2. **Timestamped** with actual dates
3. **Attributed** to specific sources
4. **Verifiable** through source URLs when available

### Error Handling

If data cannot be retrieved:
- System logs the error
- Continues with available data
- Does not fabricate information
- Shows "Data unavailable" if needed

---

## Performance

### API Rate Limits

- Alpha Vantage: 5 calls/minute (free tier)
- Finnhub: 60 calls/minute (free tier)

### Processing Time

- Single stock analysis: 5-10 seconds
- 5 recommendations: 25-50 seconds
- Cached data reduces subsequent calls

### Optimization

- Events are cached for 1 hour
- Database queries are optimized
- Parallel API calls where possible

---

## Customization

### Adjust Event Lookback Periods

Edit `services/analysis/stock_causality_analyzer.py`:

```python
# Change lookback periods
news_days = 30      # Default: 30 days
insider_days = 90   # Default: 90 days
institutional_days = 180  # Default: 180 days
```

### Adjust Significance Thresholds

```python
# Price movement threshold
if abs(price_change_pct) > 5:  # Change threshold

# RSI thresholds
if rsi > 70:  # Overbought
if rsi < 30:  # Oversold
```

### Customize Flow Chart Styling

Edit `services/monitoring/daily_digest_email_template_extended.py`:

```python
# Change colors
color_map = {
    "positive": "#27ae60",  # Green
    "negative": "#e74c3c",  # Red
    "neutral": "#7f8c8d"    # Gray
}
```

---

## Testing

### Test Causality Analysis

```bash
python3 -c "
from services.analysis.stock_causality_analyzer import analyze_stock_recommendation
result = analyze_stock_recommendation('AAPL', 'BUY', 0.85)
print(f'Found {result[\"total_events\"]} events')
print(f'Causal chain has {len(result[\"causal_chain\"])} steps')
"
```

### Test Flow Chart Generation

```bash
python3 -c "
from services.monitoring.flow_chart_generator import generate_flow_chart_html
from services.analysis.stock_causality_analyzer import analyze_stock_recommendation

causality = analyze_stock_recommendation('MSFT', 'SELL', 0.72)
html = generate_flow_chart_html(causality)
print(f'Generated HTML: {len(html)} characters')
"
```

---

## Troubleshooting

### No Events Found

**Issue**: Flow chart shows "No events found"

**Solutions**:
1. Check API keys are configured
2. Verify database has historical data
3. Check date ranges in queries
4. Review API rate limits

### Missing Data Sources

**Issue**: Some event types are empty

**Solutions**:
1. Run data collection scripts
2. Populate database tables
3. Check API connectivity
4. Verify table schemas exist

### Flow Chart Not Displaying

**Issue**: Email shows no flow charts

**Solutions**:
1. Check recommendations have causality_data
2. Verify import statements
3. Check email client supports JavaScript
4. Review HTML rendering

---

## Future Enhancements

Potential improvements:

- Add more data sources (Twitter, Reddit, analyst reports)
- Machine learning for event importance ranking
- Correlation analysis between events
- Historical accuracy tracking
- A/B testing different causal chains
- Natural language generation for explanations

---

## Summary

The Stock Causality Flow Chart system provides:

- Transparent, data-driven recommendation explanations
- Real data from multiple verified sources
- Interactive, user-friendly visualizations
- No hallucination or fabricated information
- Comprehensive event analysis
- Professional email integration

All recommendations now include detailed causal analysis showing exactly why the system made each decision.
