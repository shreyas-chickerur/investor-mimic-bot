#!/usr/bin/env python3
"""
Stress Test Framework
Analyzes system performance during specific crisis periods

REQUIRED PERIODS (per specification):
- 2008-2009: Systemic crisis
- 2011: Euro debt volatility
- 2015-2016: Sideways/chop
- 2020: Volatility shock
- 2022: Prolonged bear market
"""
import pandas as pd
import numpy as np
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StressTestAnalyzer:
    """Analyze system behavior during crisis periods"""
    
    # Crisis periods (FIXED - per specification)
    CRISIS_PERIODS = {
        '2008_financial_crisis': {
            'start': '2008-09-01',
            'end': '2009-03-31',
            'description': 'Systemic financial crisis (Lehman collapse)'
        },
        '2011_euro_debt': {
            'start': '2011-07-01',
            'end': '2011-12-31',
            'description': 'Euro debt volatility'
        },
        '2015_2016_chop': {
            'start': '2015-08-01',
            'end': '2016-06-30',
            'description': 'Sideways/choppy market'
        },
        '2020_covid_shock': {
            'start': '2020-02-01',
            'end': '2020-04-30',
            'description': 'COVID-19 volatility shock'
        },
        '2022_bear_market': {
            'start': '2022-01-01',
            'end': '2022-12-31',
            'description': 'Prolonged bear market'
        }
    }
    
    def __init__(self):
        pass
    
    def analyze_period(self, equity_curve: pd.DataFrame, trades: pd.DataFrame,
                      period_name: str, start_date: str, end_date: str,
                      description: str) -> dict:
        """
        Analyze system performance during a specific period
        
        Returns:
            Dict with period analysis
        """
        logger.info(f"\nAnalyzing: {description}")
        logger.info(f"Period: {start_date} to {end_date}")
        
        # Filter data to period
        period_equity = equity_curve[
            (equity_curve['date'] >= start_date) & 
            (equity_curve['date'] <= end_date)
        ].copy()
        
        period_trades = trades[
            (trades['date'] >= start_date) & 
            (trades['date'] <= end_date)
        ].copy() if len(trades) > 0 else pd.DataFrame()
        
        if len(period_equity) == 0:
            logger.warning(f"No data available for {period_name}")
            return {
                'period': period_name,
                'description': description,
                'data_available': False
            }
        
        # Calculate metrics
        start_value = period_equity.iloc[0]['portfolio_value']
        end_value = period_equity.iloc[-1]['portfolio_value']
        period_return = (end_value - start_value) / start_value * 100
        
        # Max drawdown during period
        running_max = period_equity['portfolio_value'].expanding().max()
        drawdown = (period_equity['portfolio_value'] - running_max) / running_max * 100
        max_drawdown = abs(drawdown.min())
        
        # Daily returns
        period_equity['daily_return'] = period_equity['portfolio_value'].pct_change()
        daily_returns = period_equity['daily_return'].dropna()
        
        # Volatility
        volatility = daily_returns.std() * np.sqrt(252) * 100
        
        # Worst single day
        worst_day = daily_returns.min() * 100
        worst_day_date = period_equity.loc[daily_returns.idxmin(), 'date'] if len(daily_returns) > 0 else None
        
        # Number of positions over time
        avg_positions = period_equity['num_positions'].mean() if 'num_positions' in period_equity else 0
        
        # Trade statistics
        if len(period_trades) > 0:
            completed_trades = period_trades[period_trades['action'] == 'SELL']
            num_trades = len(completed_trades)
            if len(completed_trades) > 0:
                winning_trades = completed_trades[completed_trades['pnl'] > 0]
                win_rate = len(winning_trades) / len(completed_trades) * 100
            else:
                win_rate = 0
        else:
            num_trades = 0
            win_rate = 0
        
        results = {
            'period': period_name,
            'description': description,
            'start_date': start_date,
            'end_date': end_date,
            'data_available': True,
            'start_value': start_value,
            'end_value': end_value,
            'period_return_pct': period_return,
            'max_drawdown_pct': max_drawdown,
            'volatility_pct': volatility,
            'worst_day_pct': worst_day,
            'worst_day_date': worst_day_date,
            'avg_positions': avg_positions,
            'num_trades': num_trades,
            'win_rate_pct': win_rate
        }
        
        # Log results
        logger.info(f"  Return: {period_return:.2f}%")
        logger.info(f"  Max Drawdown: {max_drawdown:.2f}%")
        logger.info(f"  Volatility: {volatility:.2f}%")
        logger.info(f"  Worst Day: {worst_day:.2f}% on {worst_day_date}")
        logger.info(f"  Avg Positions: {avg_positions:.1f}")
        logger.info(f"  Trades: {num_trades}, Win Rate: {win_rate:.1f}%")
        
        return results
    
    def run_all_stress_tests(self, equity_curve: pd.DataFrame, 
                            trades: pd.DataFrame) -> list:
        """
        Run stress tests on all defined crisis periods
        
        Returns:
            List of stress test results
        """
        logger.info("="*80)
        logger.info("STRESS TEST ANALYSIS")
        logger.info("="*80)
        
        all_results = []
        
        for period_name, period_info in self.CRISIS_PERIODS.items():
            results = self.analyze_period(
                equity_curve=equity_curve,
                trades=trades,
                period_name=period_name,
                start_date=period_info['start'],
                end_date=period_info['end'],
                description=period_info['description']
            )
            all_results.append(results)
        
        return all_results
    
    def generate_stress_test_report(self, stress_test_results: list) -> str:
        """Generate formatted stress test report"""
        report = []
        report.append("\n" + "="*80)
        report.append("STRESS TEST SUMMARY")
        report.append("="*80 + "\n")
        
        for result in stress_test_results:
            if not result['data_available']:
                report.append(f"\n{result['description']}")
                report.append(f"Period: {result['period']}")
                report.append("Status: No data available\n")
                continue
            
            report.append(f"\n{result['description']}")
            report.append(f"Period: {result['start_date']} to {result['end_date']}")
            report.append(f"Return: {result['period_return_pct']:.2f}%")
            report.append(f"Max Drawdown: {result['max_drawdown_pct']:.2f}%")
            report.append(f"Volatility: {result['volatility_pct']:.2f}%")
            report.append(f"Worst Day: {result['worst_day_pct']:.2f}% ({result['worst_day_date']})")
            report.append(f"Avg Positions: {result['avg_positions']:.1f}")
            report.append(f"Trades: {result['num_trades']}, Win Rate: {result['win_rate_pct']:.1f}%")
            
            # Identify failure modes
            if result['max_drawdown_pct'] > 30:
                report.append("⚠️  FAILURE MODE: Excessive drawdown (>30%)")
            if result['period_return_pct'] < -20:
                report.append("⚠️  FAILURE MODE: Severe loss (>20%)")
            if result['num_trades'] == 0:
                report.append("⚠️  FAILURE MODE: No trading activity")
            
            report.append("")
        
        report.append("="*80)
        
        return "\n".join(report)

def main():
    """Test stress test analyzer"""
    logger.info("Stress test analyzer ready. Call with actual backtest results.")

if __name__ == '__main__':
    main()
