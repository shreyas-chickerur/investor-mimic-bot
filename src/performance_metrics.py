#!/usr/bin/env python3
"""
Performance Metrics Tracker
Comprehensive metrics beyond simple P&L
"""
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PerformanceMetrics:
    """Tracks comprehensive trading performance metrics"""
    
    def __init__(self):
        self.trades = []
        self.daily_returns = []
        self.equity_curve = []
        
    def add_trade(self, entry_price: float, exit_price: float, shares: int, 
                  entry_date: datetime, exit_date: datetime, costs: float = 0):
        """Record a completed trade"""
        pnl = (exit_price - entry_price) * shares - costs
        return_pct = ((exit_price - entry_price) / entry_price) * 100
        hold_days = (exit_date - entry_date).days
        
        self.trades.append({
            'entry_price': entry_price,
            'exit_price': exit_price,
            'shares': shares,
            'pnl': pnl,
            'return_pct': return_pct,
            'hold_days': hold_days,
            'entry_date': entry_date,
            'exit_date': exit_date,
            'costs': costs
        })
    
    def add_daily_return(self, date: datetime, portfolio_value: float, 
                        cash: float, positions_value: float):
        """Record daily portfolio snapshot"""
        self.equity_curve.append({
            'date': date,
            'portfolio_value': portfolio_value,
            'cash': cash,
            'positions_value': positions_value
        })
        
        if len(self.equity_curve) > 1:
            prev_value = self.equity_curve[-2]['portfolio_value']
            daily_return = (portfolio_value - prev_value) / prev_value
            self.daily_returns.append(daily_return)
    
    def calculate_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics"""
        if not self.trades:
            return self._empty_metrics()
        
        df_trades = pd.DataFrame(self.trades)
        
        # Win/Loss metrics
        wins = df_trades[df_trades['pnl'] > 0]
        losses = df_trades[df_trades['pnl'] <= 0]
        
        win_rate = len(wins) / len(df_trades) * 100 if len(df_trades) > 0 else 0
        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
        avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
        
        # Risk-adjusted metrics
        total_pnl = df_trades['pnl'].sum()
        
        # Sharpe Ratio (annualized)
        if len(self.daily_returns) > 0:
            returns_array = np.array(self.daily_returns)
            sharpe = np.sqrt(252) * (returns_array.mean() / returns_array.std()) if returns_array.std() > 0 else 0
        else:
            sharpe = 0
        
        # Max Drawdown
        if len(self.equity_curve) > 0:
            equity_values = [e['portfolio_value'] for e in self.equity_curve]
            running_max = np.maximum.accumulate(equity_values)
            drawdown = (equity_values - running_max) / running_max
            max_drawdown = abs(min(drawdown)) * 100 if len(drawdown) > 0 else 0
        else:
            max_drawdown = 0
        
        # Calmar Ratio
        if len(self.equity_curve) > 1:
            total_return = (self.equity_curve[-1]['portfolio_value'] - self.equity_curve[0]['portfolio_value']) / self.equity_curve[0]['portfolio_value']
            days = (self.equity_curve[-1]['date'] - self.equity_curve[0]['date']).days
            annual_return = total_return * (365 / days) if days > 0 else 0
            calmar = annual_return / (max_drawdown / 100) if max_drawdown > 0 else 0
        else:
            calmar = 0
        
        # Sortino Ratio (downside deviation)
        if len(self.daily_returns) > 0:
            returns_array = np.array(self.daily_returns)
            downside_returns = returns_array[returns_array < 0]
            downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 0
            sortino = np.sqrt(252) * (returns_array.mean() / downside_std) if downside_std > 0 else 0
        else:
            sortino = 0
        
        # Profit Factor
        total_wins = wins['pnl'].sum() if len(wins) > 0 else 0
        total_losses = abs(losses['pnl'].sum()) if len(losses) > 0 else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Average hold time
        avg_hold_days = df_trades['hold_days'].mean()
        
        # Total costs
        total_costs = df_trades['costs'].sum()
        
        return {
            'total_trades': len(df_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_pnl': total_pnl,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'max_drawdown': max_drawdown,
            'calmar_ratio': calmar,
            'profit_factor': profit_factor,
            'avg_hold_days': avg_hold_days,
            'total_costs': total_costs,
            'net_pnl': total_pnl - total_costs
        }
    
    def _empty_metrics(self) -> Dict:
        """Return empty metrics structure"""
        return {
            'total_trades': 0,
            'win_rate': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'total_pnl': 0,
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'max_drawdown': 0,
            'calmar_ratio': 0,
            'profit_factor': 0,
            'avg_hold_days': 0,
            'total_costs': 0,
            'net_pnl': 0
        }
    
    def get_summary(self) -> str:
        """Get formatted metrics summary"""
        metrics = self.calculate_metrics()
        
        summary = f"""
Performance Metrics Summary
{'=' * 50}
Total Trades: {metrics['total_trades']}
Win Rate: {metrics['win_rate']:.1f}%
Avg Win: ${metrics['avg_win']:.2f}
Avg Loss: ${metrics['avg_loss']:.2f}
Profit Factor: {metrics['profit_factor']:.2f}

Risk-Adjusted Returns:
Sharpe Ratio: {metrics['sharpe_ratio']:.2f}
Sortino Ratio: {metrics['sortino_ratio']:.2f}
Max Drawdown: {metrics['max_drawdown']:.2f}%
Calmar Ratio: {metrics['calmar_ratio']:.2f}

P&L:
Gross P&L: ${metrics['total_pnl']:.2f}
Total Costs: ${metrics['total_costs']:.2f}
Net P&L: ${metrics['net_pnl']:.2f}

Avg Hold Time: {metrics['avg_hold_days']:.1f} days
"""
        return summary
