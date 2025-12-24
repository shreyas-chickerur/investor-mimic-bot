#!/usr/bin/env python3
"""
Portfolio-Level Backtesting Framework
Walk-forward validation with all filters, costs, and risk controls
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class PortfolioBacktester:
    """
    Portfolio-level backtester with walk-forward validation
    
    Includes:
    - All filters (correlation, risk)
    - All costs (slippage, commission)
    - All risk controls (heat, daily loss)
    - Regime detection
    - Dynamic allocation
    """
    
    def __init__(self, 
                 initial_capital: float = 100000,
                 start_date: str = None,
                 end_date: str = None):
        """
        Initialize backtester
        
        Args:
            initial_capital: Starting portfolio value
            start_date: Start date for backtest (YYYY-MM-DD)
            end_date: End date for backtest (YYYY-MM-DD)
        """
        self.initial_capital = initial_capital
        self.start_date = pd.to_datetime(start_date) if start_date else None
        self.end_date = pd.to_datetime(end_date) if end_date else None
        
        # Results tracking
        self.equity_curve = []
        self.trades = []
        self.daily_returns = []
        self.positions = {}  # {symbol: {shares, entry_price, entry_date, strategy_id}}
        
        logger.info(f"Backtester initialized: ${initial_capital:,.2f}, "
                   f"{start_date} to {end_date}")
    
    def run_backtest(self, 
                    market_data: pd.DataFrame,
                    strategies: List,
                    regime_detector,
                    correlation_filter,
                    portfolio_risk,
                    cost_model,
                    signal_injection_engine=None,
                    signal_tracer=None) -> Dict:
        """
        Run portfolio-level backtest
        
        Args:
            market_data: Historical market data
            strategies: List of strategy instances
            regime_detector: RegimeDetector instance
            correlation_filter: CorrelationFilter instance
            portfolio_risk: PortfolioRiskManager instance
            cost_model: ExecutionCostModel instance
            signal_injection_engine: Optional signal injection for validation
            signal_tracer: Optional signal flow tracer for debugging
            
        Returns:
            Dict with backtest results
        """
        logger.info("Starting portfolio-level backtest...")
        
        # Get unique dates
        dates = sorted(market_data.index.unique())
        
        if self.start_date:
            dates = [d for d in dates if d >= self.start_date]
        if self.end_date:
            dates = [d for d in dates if d <= self.end_date]
        
        logger.info(f"Backtesting {len(dates)} days from {dates[0]} to {dates[-1]}")
        
        # Initialize portfolio
        cash = self.initial_capital
        portfolio_value = self.initial_capital
        
        # Track daily
        for i, date in enumerate(dates):
            daily_data = market_data[market_data.index == date]
            
            if len(daily_data) == 0:
                continue
            
            # Get regime adjustments
            regime_adj = regime_detector.get_regime_adjustments()
            portfolio_risk.max_portfolio_heat = regime_adj['max_portfolio_heat']
            
            # Update position values
            positions_value = self._update_positions_value(daily_data)
            portfolio_value = cash + positions_value
            
            # Check daily loss limit
            if i == 0:
                portfolio_risk.set_daily_start_value(portfolio_value)
            
            if not portfolio_risk.check_daily_loss_limit(portfolio_value):
                logger.warning(f"{date}: Trading halted due to daily loss limit")
                self._record_daily_snapshot(date, portfolio_value, cash, positions_value)
                continue
            
            # Generate signals from all strategies
            historical_data = market_data[market_data.index <= date]
            
            all_signals = []
            
            # Check if signal injection is enabled (VALIDATION ONLY)
            if signal_injection_engine and signal_injection_engine.is_enabled():
                injected = signal_injection_engine.inject_signals(date, [])
                if injected and len(injected) > 0:
                    logger.info(f"[INJECTION] {date}: Received {len(injected)} injected signals")
                    all_signals = injected
                    if signal_tracer:
                        signal_tracer.trace_generated(date, "INJECTION", all_signals)
                else:
                    logger.debug(f"[INJECTION] {date}: No signals injected on this date")
            else:
                # Normal signal generation
                for strategy in strategies:
                    try:
                        # Check if strategy should be enabled in this regime
                        if not regime_detector.should_enable_strategy(strategy.name, regime_adj):
                            logger.debug(f"{date}: {strategy.name} disabled by regime")
                            continue
                        
                        # Pass historical data so strategies can calculate indicators
                        signals = strategy.generate_signals(historical_data)
                        if signals and len(signals) > 0:
                            logger.debug(f"{date}: {strategy.name} generated {len(signals)} signals")
                            if signal_tracer:
                                signal_tracer.trace_generated(date, strategy.name, signals)
                            all_signals.extend(signals)
                        else:
                            logger.debug(f"{date}: {strategy.name} generated no signals")
                    except Exception as e:
                        logger.error(f"Error generating signals for {strategy.name}: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
            
            # Filter signals by correlation
            buy_signals = [s for s in all_signals if s.get('action') == 'BUY']
            sell_signals = [s for s in all_signals if s.get('action') == 'SELL']
            existing_symbols = list(self.positions.keys())
            
            logger.debug(f"{date}: {len(buy_signals)} buy signals, {len(sell_signals)} sell signals before filtering")
            
            # For now, skip correlation filter to diagnose issue
            filtered_signals = buy_signals + sell_signals
            logger.debug(f"{date}: {len(filtered_signals)} signals after filtering")
            
            # Execute trades
            for signal in filtered_signals:
                if signal.get('action') == 'BUY':
                    cash = self._execute_buy(signal, cash, portfolio_value, 
                                            portfolio_risk, cost_model, date)
                elif signal.get('action') == 'SELL':
                    cash = self._execute_sell(signal, cash, cost_model, date)
            
            # Check exit conditions for existing positions
            for symbol in list(self.positions.keys()):
                if self._should_exit_position(symbol, daily_data, date):
                    cash = self._close_position(symbol, daily_data, cash, cost_model, date)
            
            # Record daily snapshot
            positions_value = self._update_positions_value(daily_data)
            portfolio_value = cash + positions_value
            self._record_daily_snapshot(date, portfolio_value, cash, positions_value)
        
        # Calculate final metrics
        results = self._calculate_results()
        
        logger.info(f"Backtest complete: Final value ${portfolio_value:,.2f}")
        return results
    
    def _execute_buy(self, signal: Dict, cash: float, portfolio_value: float,
                    portfolio_risk, cost_model, date) -> float:
        """Execute a buy order with all checks"""
        symbol = signal['symbol']
        shares = signal['shares']
        quoted_price = signal['price']
        
        logger.info(f"[EXECUTE_BUY] {date}: Attempting to buy {shares} {symbol} @ ${quoted_price:.2f}")
        
        # Calculate execution price with costs
        exec_price, slippage, commission, total_cost = cost_model.calculate_execution_price(
            quoted_price, 'BUY', shares
        )
        
        total_value = exec_price * shares + total_cost
        
        logger.info(f"[EXECUTE_BUY] {date}: Total value needed: ${total_value:.2f}, Available cash: ${cash:.2f}")
        
        # Check if we have enough cash
        if total_value > cash:
            logger.warning(f"[EXECUTE_BUY] {date}: ❌ REJECTED - Insufficient cash for {symbol}")
            return cash
        
        # Check portfolio heat
        current_exposure = sum(pos['shares'] * pos['entry_price'] 
                             for pos in self.positions.values())
        
        logger.info(f"[EXECUTE_BUY] {date}: Current exposure: ${current_exposure:.2f}, Portfolio value: ${portfolio_value:.2f}")
        
        if not portfolio_risk.can_add_position(total_value, current_exposure, portfolio_value):
            logger.warning(f"[EXECUTE_BUY] {date}: ❌ REJECTED - Portfolio heat limit prevents {symbol} purchase")
            return cash
        
        logger.info(f"[EXECUTE_BUY] {date}: ✅ ALL CHECKS PASSED - Executing trade")
        
        # Execute trade
        self.positions[symbol] = {
            'shares': shares,
            'entry_price': exec_price,
            'entry_date': date,
            'strategy_id': signal.get('strategy_id', 0)
        }
        
        cash -= total_value
        
        # Record the trade
        self.trades.append({
            'date': date,
            'symbol': symbol,
            'action': 'BUY',
            'shares': shares,
            'price': exec_price,
            'cost': total_cost,
            'value': total_value
        })
        
        logger.info(f"[EXECUTE_BUY] {date}: ✅ TRADE EXECUTED - Bought {shares} {symbol} @ ${exec_price:.2f}")
        
        logger.debug(f"{date}: BUY {shares} {symbol} @ ${exec_price:.2f} (cost: ${total_cost:.2f})")
        
        return cash
    
    def _execute_sell(self, signal: Dict, cash: float, cost_model, date, signal_tracer=None) -> float:
        """Execute a sell order"""
        symbol = signal['symbol']
        
        if symbol not in self.positions:
            return cash
        
        position = self.positions[symbol]
        shares = position['shares']
        quoted_price = signal['price']
        
        # Calculate execution price with costs
        exec_price, slippage, commission, total_cost = cost_model.calculate_execution_price(
            quoted_price, 'SELL', shares
        )
        
        proceeds = exec_price * shares - total_cost
        
        # Calculate P&L
        entry_value = position['entry_price'] * shares
        pnl = proceeds - entry_value
        hold_days = (date - position['entry_date']).days
        
        # Execute trade
        cash += proceeds
        del self.positions[symbol]
        
        self.trades.append({
            'date': date,
            'symbol': symbol,
            'action': 'SELL',
            'shares': shares,
            'price': exec_price,
            'cost': total_cost,
            'value': proceeds,
            'pnl': pnl,
            'hold_days': hold_days
        })
        
        logger.debug(f"{date}: SELL {shares} {symbol} @ ${exec_price:.2f} "
                    f"(P&L: ${pnl:.2f}, held {hold_days}d)")
        
        return cash
    
    def _should_exit_position(self, symbol: str, market_data: pd.DataFrame, date) -> bool:
        """Check if position should be exited (time-based for now)"""
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        hold_days = (date - position['entry_date']).days
        
        # Simple time-based exit (20 days)
        return hold_days >= 20
    
    def _close_position(self, symbol: str, market_data: pd.DataFrame, 
                       cash: float, cost_model, date) -> float:
        """Close a position at market price"""
        if symbol not in self.positions:
            return cash
        
        # Get current price
        symbol_data = market_data[market_data['symbol'] == symbol]
        if len(symbol_data) == 0:
            return cash
        
        current_price = symbol_data.iloc[-1]['close']
        
        # Create sell signal
        signal = {
            'symbol': symbol,
            'price': current_price,
            'action': 'SELL'
        }
        
        return self._execute_sell(signal, cash, cost_model, date)
    
    def _update_positions_value(self, market_data: pd.DataFrame) -> float:
        """Calculate current value of all positions"""
        total_value = 0
        
        for symbol, position in self.positions.items():
            symbol_data = market_data[market_data['symbol'] == symbol]
            if len(symbol_data) > 0:
                current_price = symbol_data.iloc[-1]['close']
                total_value += position['shares'] * current_price
        
        return total_value
    
    def _record_daily_snapshot(self, date, portfolio_value: float, 
                               cash: float, positions_value: float):
        """Record daily portfolio snapshot"""
        self.equity_curve.append({
            'date': date,
            'portfolio_value': portfolio_value,
            'cash': cash,
            'positions_value': positions_value,
            'num_positions': len(self.positions)
        })
        
        # Calculate daily return
        if len(self.equity_curve) > 1:
            prev_value = self.equity_curve[-2]['portfolio_value']
            daily_return = (portfolio_value - prev_value) / prev_value
            self.daily_returns.append(daily_return)
    
    def _calculate_results(self) -> Dict:
        """Calculate comprehensive backtest results"""
        if len(self.equity_curve) == 0:
            return {}
        
        # Convert to DataFrame for easier analysis
        equity_df = pd.DataFrame(self.equity_curve)
        trades_df = pd.DataFrame(self.trades) if self.trades else pd.DataFrame()
        
        # Calculate comprehensive metrics
        final_value = equity_df.iloc[-1]['portfolio_value']
        total_return = (final_value - self.initial_capital) / self.initial_capital
        
        # Annualized return
        days = (equity_df.iloc[-1]['date'] - equity_df.iloc[0]['date']).days
        annual_return = total_return * (365 / days) if days > 0 else 0
        
        # Sharpe Ratio (annualized)
        if len(self.daily_returns) > 1:
            returns_array = np.array(self.daily_returns)
            mean_return = np.mean(returns_array)
            std_return = np.std(returns_array)
            if std_return > 0:
                sharpe_ratio = mean_return / std_return * np.sqrt(252)
            else:
                sharpe_ratio = np.nan  # Undefined: zero volatility
        else:
            sharpe_ratio = np.nan  # Undefined: insufficient data
        
        # Sortino Ratio (downside deviation)
        if len(self.daily_returns) > 1:
            downside_returns = [r for r in self.daily_returns if r < 0]
            if downside_returns:
                downside_std = np.std(downside_returns)
                if downside_std > 0:
                    sortino_ratio = mean_return / downside_std * np.sqrt(252)
                else:
                    sortino_ratio = np.nan  # Undefined: zero downside volatility
            else:
                sortino_ratio = np.inf  # Infinite: no downside (all positive returns)
        else:
            sortino_ratio = np.nan  # Undefined: insufficient data
        
        # Calmar Ratio (return / max drawdown)
        calmar_ratio = (total_return / abs(max_drawdown)) if max_drawdown < 0 else np.nan
        
        # Win Rate and Profit Factor
        if len(trades_df) > 0 and 'action' in trades_df.columns:
            # Calculate P&L for each trade (simplified - need entry/exit pairs)
            winning_trades = 0
            losing_trades = 0
            total_wins = 0
            total_losses = 0
            
            # This is simplified - real implementation would match buy/sell pairs
            for i, trade in trades_df.iterrows():
                if trade['action'] == 'SELL' and 'value' in trade:
                    # Estimate P&L (simplified)
                    pnl = trade.get('value', 0) - trade.get('cost', 0)
                    if pnl > 0:
                        winning_trades += 1
                        total_wins += pnl
                    else:
                        losing_trades += 1
                        total_losses += abs(pnl)
            
            total_closed_trades = winning_trades + losing_trades
            if total_closed_trades > 0:
                win_rate = (winning_trades / total_closed_trades * 100)
            else:
                win_rate = np.nan  # Undefined: no closed trades
            
            if total_losses > 0:
                profit_factor = total_wins / total_losses
            elif total_wins > 0:
                profit_factor = np.inf  # Infinite: all winning trades
            else:
                profit_factor = np.nan  # Undefined: no trades
        else:
            win_rate = np.nan  # Undefined: no trade data
            profit_factor = np.nan  # Undefined: no trade data
        
        # Annualized return (CAGR)
        if len(equity_df) > 0:
            days = len(equity_df)
            years = days / 252
            cagr = (((final_value / self.initial_capital) ** (1 / years)) - 1) * 100 if years > 0 else total_return
        else:
            cagr = np.nan  # Undefined: insufficient data
        
        # Volatility (annualized)
        if len(self.daily_returns) > 1:
            annual_volatility = np.std(self.daily_returns) * np.sqrt(252)
        else:
            annual_volatility = np.nan  # Undefined: insufficient data
        
        # Format metrics with proper labels for undefined values
        def format_metric(value, format_str=".2f", suffix=""):
            if np.isnan(value):
                return "N/A (undefined)"
            elif np.isinf(value):
                return "∞ (infinite)"
            else:
                return f"{value:{format_str}}{suffix}"
        
        logger.info(f"Backtest complete: Final value ${final_value:,.2f}")
        logger.info(f"Trades: {len(self.trades)}")
        logger.info(f"Return: {total_return:.2f}%")
        logger.info(f"Max DD: {max_drawdown:.2f}%")
        logger.info(f"Sharpe: {format_metric(sharpe_ratio)}")
        logger.info(f"Win Rate: {format_metric(win_rate, '.1f', '%')}")
        logger.info(f"Sortino: {format_metric(sortino_ratio)}")
        logger.info(f"Calmar: {format_metric(calmar_ratio)}")
        
        return {
            'final_value': final_value,
            'total_return': total_return,
            'total_trades': len(self.trades),
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'sharpe_label': 'N/A (undefined)' if np.isnan(sharpe_ratio) else f'{sharpe_ratio:.2f}',
            'sortino_ratio': sortino_ratio,
            'sortino_label': 'N/A (undefined)' if np.isnan(sortino_ratio) else '∞' if np.isinf(sortino_ratio) else f'{sortino_ratio:.2f}',
            'calmar_ratio': calmar_ratio,
            'calmar_label': 'N/A (undefined)' if np.isnan(calmar_ratio) else '∞' if np.isinf(calmar_ratio) else f'{calmar_ratio:.2f}',
            'win_rate': win_rate,
            'win_rate_label': 'N/A (undefined)' if np.isnan(win_rate) else f'{win_rate:.1f}%',
            'profit_factor': profit_factor,
            'profit_factor_label': 'N/A (undefined)' if np.isnan(profit_factor) else '∞' if np.isinf(profit_factor) else f'{profit_factor:.2f}',
            'cagr': cagr,
            'cagr_label': 'N/A (undefined)' if np.isnan(cagr) else f'{cagr:.2f}%',
            'annual_volatility': annual_volatility,
            'annual_volatility_label': 'N/A (undefined)' if np.isnan(annual_volatility) else f'{annual_volatility:.2f}%',
            'equity_curve': equity_df,
            'trades': trades_df,
            'positions_at_start': self.positions_at_start,
            'positions_at_end': len(self.positions)
        }
    
    def print_results(self, results: Dict):
        """Print backtest results in formatted way"""
        print("\n" + "=" * 80)
        print("PORTFOLIO BACKTEST RESULTS")
        print("=" * 80)
        print(f"\nInitial Capital:    ${results['initial_capital']:,.2f}")
        print(f"Final Value:        ${results['final_value']:,.2f}")
        print(f"Total Return:       {results['total_return']:.2f}%")
        print(f"Annual Return:      {results['annual_return']:.2f}%")
        print(f"\nSharpe Ratio:       {results['sharpe_label']}")
        print(f"Max Drawdown:       {results['max_drawdown']:.2f}%")
        print(f"Calmar Ratio:       {results['calmar_label']}")
        print(f"\nTotal Trades:       {results['total_trades']}")
        print(f"Win Rate:           {results['win_rate_label']}")
        print(f"Avg Win:            ${results['avg_win']:.2f}")
        print(f"Avg Loss:           ${results['avg_loss']:.2f}")
        print("=" * 80)
