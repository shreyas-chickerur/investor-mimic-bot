# ETF Trading Guide

## Overview

The system now supports trading both individual stocks and ETFs (Exchange-Traded Funds). ETFs provide diversified exposure to market segments, sectors, and asset classes.

## Supported ETF Categories

### Broad Market ETFs
- **SPY** - S&P 500
- **QQQ** - Nasdaq 100 (Tech-heavy)
- **IWM** - Russell 2000 (Small-cap)
- **DIA** - Dow Jones Industrial Average
- **VTI** - Total Stock Market
- **VOO** - S&P 500 (Vanguard)

### Sector ETFs
- **XLF** - Financial Sector
- **XLE** - Energy Sector
- **XLK** - Technology Sector
- **XLV** - Healthcare Sector
- **XLI** - Industrial Sector
- **XLP** - Consumer Staples
- **XLY** - Consumer Discretionary
- **XLU** - Utilities Sector
- **XLRE** - Real Estate Sector

### International ETFs
- **VEA** - Developed Markets (ex-US)
- **VWO** - Emerging Markets
- **EFA** - EAFE (Europe, Australasia, Far East)
- **EEM** - Emerging Markets
- **VGK** - European Stocks
- **EWJ** - Japan
- **FXI** - China Large-Cap
- **IEMG** - Emerging Markets Core

### Asset Class ETFs
- **AGG** - Aggregate Bond Market
- **BND** - Total Bond Market
- **TLT** - 20+ Year Treasury Bonds
- **GLD** - Gold
- **SLV** - Silver

### Real Estate ETFs
- **VNQ** - Real Estate Investment Trusts
- **IYR** - Real Estate
- **XLRE** - Real Estate Sector

### Thematic/Innovation ETFs
- **ARKK** - ARK Innovation
- **ARKG** - ARK Genomic Revolution
- **ARKW** - ARK Next Generation Internet
- **ARKF** - ARK Fintech Innovation
- **SMH** - Semiconductors
- **SOXX** - Semiconductors
- **XBI** - Biotech
- **IBB** - Biotech

## How Strategies Handle ETFs

### RSI Mean Reversion
- Works well with sector ETFs (XLF, XLE, XLK, etc.)
- Identifies oversold conditions in entire sectors
- Lower volatility than individual stocks
- Suitable for swing trading (5-20 day holds)

### ML Momentum
- Effective with broad market ETFs (SPY, QQQ, IWM)
- Captures sector rotation trends
- Works with thematic ETFs (ARKK, SMH)

### MA Crossover
- Best for broad market and sector ETFs
- Identifies long-term trend changes
- Lower false signals than individual stocks

### Volatility Breakout
- Works with leveraged and thematic ETFs
- Captures momentum in high-volatility ETFs
- Good for ARK funds and sector rotations

### News Sentiment
- Less effective for ETFs (no company-specific news)
- Disabled for most ETF symbols
- May work for thematic ETFs with media coverage

## ETF Trading Advantages

1. **Diversification** - Reduces single-stock risk
2. **Lower Volatility** - Smoother price action
3. **Sector Exposure** - Trade entire sectors vs. stock picking
4. **Liquidity** - High volume, tight spreads
5. **No Earnings Risk** - No single company earnings surprises

## ETF Trading Considerations

1. **Lower Returns** - Less upside than individual stock winners
2. **Expense Ratios** - Small ongoing fees (typically 0.03% - 0.75%)
3. **Tracking Error** - May not perfectly match underlying index
4. **Correlation** - Sector ETFs move together during market stress
5. **Less Signal Frequency** - Fewer extreme RSI readings

## Configuration

ETFs are automatically included in the trading universe via `config/universe.csv`. The system treats them like stocks with the same:
- Position sizing rules
- Risk management filters
- Portfolio heat limits
- Correlation filters

## Data Updates

When running `scripts/update_data.py`, the system now fetches data for all symbols in `config/universe.csv`, including ETFs. This ensures:
- Historical price data
- Technical indicators (RSI, SMA, volatility)
- Volume data

## Monitoring ETF Positions

ETF positions appear in:
- Daily email digests
- Database `positions` table
- Strategy performance reports
- P&L attribution (per-strategy tracking)

## Best Practices

1. **Mix stocks and ETFs** - Use ETFs for core exposure, stocks for alpha
2. **Sector rotation** - Trade sector ETFs based on regime detection
3. **Risk-off positioning** - Use bond ETFs (AGG, TLT) during high volatility
4. **International diversification** - Add VEA, EEM for global exposure
5. **Thematic plays** - Use ARKK, SMH for specific themes

## Example Scenarios

### Defensive Positioning (Crisis Regime)
- Increase allocation to: AGG, TLT, XLU, XLP
- Reduce allocation to: QQQ, XLY, ARKK

### Growth Positioning (Bull Market)
- Increase allocation to: QQQ, XLK, ARKK, SMH
- Reduce allocation to: AGG, TLT, XLU

### Sector Rotation
- Oversold sector ETF (RSI < 30): XLE, XLF, XLI
- Momentum sectors: XLK, XLV, XLY

## Performance Expectations

ETFs typically generate:
- **Lower win rate** - 45-50% (vs. 50-55% for stocks)
- **Lower volatility** - 15-20% annualized (vs. 25-35% for stocks)
- **More consistent returns** - Fewer extreme outliers
- **Better Sharpe ratio** - Higher risk-adjusted returns

## Future Enhancements

Potential ETF-specific features:
- ETF-only strategies (sector rotation, pairs trading)
- Expense ratio consideration in position sizing
- Leveraged ETF handling (2x, 3x funds)
- Options on ETFs for hedging
- International ETF currency risk management
