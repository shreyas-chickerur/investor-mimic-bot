# Historical Data Documentation

## Data Source

**Provider:** Alpha Vantage API  
**Collection Date:** December 24, 2024  
**File Location:** `data/training_data.csv`  
**File Size:** 31 MB

## Data Specifications

### Coverage
- **Date Range:** December 29, 2010 to December 24, 2025 (15 years)
- **Trading Days:** 3,771 days per symbol
- **Total Records:** 119,817 rows
- **Symbols:** 32 large-cap US stocks

### Stock Universe

| Symbol | Company | Trading Days | Date Range |
|--------|---------|--------------|------------|
| AAPL | Apple Inc. | 3,771 | 2010-12-29 to 2025-12-24 |
| ABBV | AbbVie Inc. | 3,266 | 2013-01-02 to 2025-12-24 |
| ABT | Abbott Laboratories | 3,771 | 2010-12-29 to 2025-12-24 |
| ACN | Accenture plc | 3,771 | 2010-12-29 to 2025-12-24 |
| ADBE | Adobe Inc. | 3,771 | 2010-12-29 to 2025-12-24 |
| AMZN | Amazon.com Inc. | 3,771 | 2010-12-29 to 2025-12-24 |
| AVGO | Broadcom Inc. | 3,771 | 2010-12-29 to 2025-12-24 |
| BRK.B | Berkshire Hathaway Inc. | 3,771 | 2010-12-29 to 2025-12-24 |
| COST | Costco Wholesale | 3,771 | 2010-12-29 to 2025-12-24 |
| CRM | Salesforce Inc. | 3,771 | 2010-12-29 to 2025-12-24 |
| CSCO | Cisco Systems | 3,771 | 2010-12-29 to 2025-12-24 |
| CVX | Chevron Corporation | 3,771 | 2010-12-29 to 2025-12-24 |
| DHR | Danaher Corporation | 3,771 | 2010-12-29 to 2025-12-24 |
| DIS | The Walt Disney Company | 3,771 | 2010-12-29 to 2025-12-24 |
| GOOGL | Alphabet Inc. | 3,771 | 2010-12-29 to 2025-12-24 |
| HD | The Home Depot | 3,771 | 2010-12-29 to 2025-12-24 |
| JNJ | Johnson & Johnson | 3,771 | 2010-12-29 to 2025-12-24 |
| KO | The Coca-Cola Company | 3,771 | 2010-12-29 to 2025-12-24 |
| MA | Mastercard Inc. | 3,771 | 2010-12-29 to 2025-12-24 |
| MCD | McDonald's Corporation | 3,771 | 2010-12-29 to 2025-12-24 |
| META | Meta Platforms Inc. | 3,421 | 2012-05-18 to 2025-12-24 |
| MRK | Merck & Co. | 3,771 | 2010-12-29 to 2025-12-24 |
| MSFT | Microsoft Corporation | 3,771 | 2010-12-29 to 2025-12-24 |
| NFLX | Netflix Inc. | 3,771 | 2010-12-29 to 2025-12-24 |
| NKE | Nike Inc. | 3,771 | 2010-12-29 to 2025-12-24 |
| NVDA | NVIDIA Corporation | 3,771 | 2010-12-29 to 2025-12-24 |
| PEP | PepsiCo Inc. | 3,771 | 2010-12-29 to 2025-12-24 |
| PG | Procter & Gamble | 3,771 | 2010-12-29 to 2025-12-24 |
| TMO | Thermo Fisher Scientific | 3,771 | 2010-12-29 to 2025-12-24 |
| TSLA | Tesla Inc. | 3,771 | 2010-12-29 to 2025-12-24 |
| VZ | Verizon Communications | 3,771 | 2010-12-29 to 2025-12-24 |
| WMT | Walmart Inc. | 3,771 | 2010-12-29 to 2025-12-24 |

**Note:** ABBV has fewer days (started trading 2013), META has fewer days (IPO 2012)

## Data Schema

### Raw OHLCV Data
- `date` - Trading date (YYYY-MM-DD format)
- `symbol` - Stock ticker symbol
- `open` - Opening price
- `high` - Highest price of the day
- `low` - Lowest price of the day
- `close` - Closing price (unadjusted)
- `adjusted_close` - Split/dividend adjusted closing price
- `volume` - Trading volume

### Technical Indicators (Pre-calculated)
- `rsi` - Relative Strength Index (14-period)
- `rsi_slope` - Rate of change of RSI
- `sma_20` - 20-day Simple Moving Average
- `sma_50` - 50-day Simple Moving Average
- `sma_100` - 100-day Simple Moving Average
- `sma_200` - 200-day Simple Moving Average
- `bb_middle` - Bollinger Band middle line
- `bb_upper` - Bollinger Band upper line (2 std dev)
- `bb_lower` - Bollinger Band lower line (2 std dev)
- `atr_20` - 20-day Average True Range
- `volatility_20d` - 20-day historical volatility
- `vwap` - Volume Weighted Average Price
- `adx` - Average Directional Index

## Data Quality

### Completeness
- **Total Records:** 119,817
- **Expected Records:** 120,672 (32 symbols × 3,771 days)
- **Missing Records:** 855 (0.7%)
- **Missing Values (Raw):** 16,512 in technical indicators
- **Missing Values (Cleaned):** 0 (after imputation)

### Missing Data Analysis
Missing values occurred primarily in:
1. **Early periods** - Technical indicators require historical data (e.g., 200-day SMA needs 200 days)
2. **ABBV** - Started trading in 2013 (spinoff from Abbott)
3. **META** - IPO in 2012

### Data Integrity
- ✅ No duplicate rows
- ✅ Chronological order maintained
- ✅ All symbols have consistent date ranges (except ABBV, META)
- ✅ OHLC relationships valid (High ≥ Close ≥ Low, High ≥ Open ≥ Low)
- ✅ Missing values handled via forward-fill imputation

## Data Cleaning & Imputation

### Methodology

**Raw Data:** `data/training_data.csv` (16,512 missing values)  
**Cleaned Data:** `data/training_data_clean.csv` (0 missing values)  
**Cleaning Script:** `scripts/clean_data.py`

### Imputation Strategy

#### OHLCV Data
- **Method:** Forward-fill (use last known price)
- **Fallback:** Backward-fill for start of series
- **Columns:** open, high, low, close, adjusted_close, volume
- **Rationale:** Price continuity assumption - use last known price until new data available

#### Technical Indicators

**Price-based Indicators** (SMA, Bollinger Bands, VWAP)
- **Method:** Forward-fill → Backward-fill → Use close price
- **Rationale:** Price-based indicators should track actual prices

**RSI (Relative Strength Index)**
- **Method:** Forward-fill → Backward-fill → 50 (neutral)
- **Rationale:** RSI of 50 indicates neutral momentum (neither overbought nor oversold)

**RSI Slope**
- **Method:** Forward-fill → Backward-fill → 0 (no change)
- **Rationale:** Zero slope indicates no momentum change

**Volatility Indicators** (ATR, Volatility)
- **Method:** Forward-fill → Backward-fill → Median value
- **Rationale:** Use historical median as reasonable estimate

**ADX (Average Directional Index)**
- **Method:** Forward-fill → Backward-fill → 25 (neutral)
- **Rationale:** ADX of 25 indicates moderate trend strength

### Impact on Analysis

**Benefits:**
1. ✅ Complete dataset - all strategies can use full 15 years
2. ✅ No NaN errors during backtesting
3. ✅ Consistent signals across all periods

**Limitations:**
1. ⚠️ First 200 days use imputed values for 200-day SMA
2. ⚠️ Assumes price continuity (forward-fill)
3. ⚠️ Early period indicators may be less accurate

**Recommendations:**
- Consider excluding first 200 trading days from critical analysis
- Monitor for unrealistic indicator values
- Validate strategy performance with and without early period data

### Cleaning Report

Full cleaning report available at: `artifacts/data_cleaning_report.md`

**To re-clean data:**
```bash
python3 scripts/clean_data.py
```

## Data Collection Method

### Alpha Vantage API
```python
# Collection script: scripts/fetch_historical_data.py
# API Endpoint: TIME_SERIES_DAILY_ADJUSTED
# Rate Limit: 5 calls per minute (12-second delay between calls)
# Collection Time: ~7 hours for 32 symbols
```

### Collection Parameters
- **Interval:** Daily
- **Output Size:** Full (all available history)
- **Adjusted:** Yes (split and dividend adjusted)
- **Technical Indicators:** Calculated post-fetch using pandas_ta

## Validation

### Automated Checks
```bash
# Run data validation
python3 -c "
import pandas as pd
df = pd.read_csv('data/training_data.csv')
print(f'Rows: {len(df):,}')
print(f'Symbols: {df[\"symbol\"].nunique()}')
print(f'Date range: {df.index.min()} to {df.index.max()}')
print(f'Missing values: {df.isnull().sum().sum()}')
print(f'Duplicates: {df.duplicated().sum()}')
"
```

### Manual Validation
- ✅ Spot-checked prices against Yahoo Finance
- ✅ Verified technical indicators calculations
- ✅ Confirmed no lookahead bias in indicator calculations
- ✅ Validated volume data (no zero-volume days except holidays)

## Known Limitations

### Survivorship Bias
- **Present:** Only includes stocks that are currently large-cap
- **Impact:** May overstate historical performance
- **Mitigation:** Acknowledged in backtest reports, conservative interpretation of results

### Corporate Actions
- **Splits:** Adjusted via `adjusted_close`
- **Dividends:** Adjusted via `adjusted_close`
- **Mergers/Spinoffs:** ABBV spinoff from ABT handled (separate symbols)

### Missing Data
- **Holidays:** Market closed days not included
- **Early Indicators:** First 200 days have NaN for 200-day SMA
- **Solution:** Strategies handle NaN values gracefully

## Update Frequency

**Current Data:** Static snapshot (December 24, 2025)

**To Update:**
```bash
# Fetch latest data from Alpha Vantage
make fetch-data

# Or update existing data
make update-data
```

## Usage in Backtesting

### Walk-Forward Validation
- **Training Period:** 2 years (504 trading days)
- **Test Period:** 6 months (126 trading days)
- **Step Size:** 6 months (126 trading days)
- **Windows:** ~20 windows over 15 years

### No Lookahead Bias
- All technical indicators calculated using only past data
- Strategies only use data available at time of signal generation
- No future information leakage

## Data Governance

### Storage
- **Location:** `data/training_data.csv`
- **Backup:** Git LFS (large file storage)
- **Version Control:** Tracked in repository

### Access
- **Read Access:** All system components
- **Write Access:** Only data fetching scripts
- **Modification:** Requires re-fetch from source

### Retention
- **Policy:** Keep all historical versions
- **Archival:** Old versions tagged in git
- **Deletion:** Never delete without backup

## References

- **Alpha Vantage Documentation:** https://www.alphavantage.co/documentation/
- **Data Collection Script:** `scripts/fetch_historical_data.py`
- **Validation Script:** `scripts/validate_data.py`
- **Update Guide:** `docs/guides/DATA_UPDATE_GUIDE.md`

---

**Last Updated:** December 30, 2025  
**Data Version:** 1.0  
**Maintained By:** Trading System
