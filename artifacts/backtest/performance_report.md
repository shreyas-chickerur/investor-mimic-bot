# Walk-Forward Backtest Results

## Portfolio Performance Metrics

Generated: 2025-12-30 12:05:21

### Return Metrics
- **Total Return:** 0.00%
- **CAGR:** 0.00%
- **Annual Volatility:** nan%

### Risk-Adjusted Returns
- **Sharpe Ratio:** 0.00
- **Sortino Ratio:** 0.00

### Risk Metrics
- **Max Drawdown:** 0.00%
- **Max Drawdown Duration:** 0 days

### Trading Metrics
- **Number of Trades:** 1
- **Win Rate:** 0.0%
- **Average Win:** $0.00
- **Average Loss:** $0.00
- **Profit Factor:** 0.00
- **Annual Turnover:** 5.0x

## Methodology

- **Framework:** Walk-forward validation
- **Training Period:** 2 years (504 trading days)
- **Test Period:** 6 months (126 trading days)
- **Step Size:** 6 months (126 trading days)
- **Initial Capital:** $100,000

## Risk Controls Active

- Portfolio heat limit (regime-dependent: 30%/25%/20%)
- Daily loss limit (-2%)
- Correlation filter (adaptive windows)
- ATR-based position sizing (1% portfolio risk)
- Execution costs (0.05% slippage + $1 commission)
- Catastrophe stop losses (3x ATR)

## Notes

- All strategies active (RSI, Trend, Breakout, Momentum, ML)
- Regime detection enabled (VIX-based)
- Dynamic allocation based on strategy performance
- No parameter tuning during test periods
- Survivorship bias acknowledged

---

*This backtest uses historical data and does not guarantee future performance.*
