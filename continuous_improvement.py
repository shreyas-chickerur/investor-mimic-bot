#!/usr/bin/env python3
"""
Continuous Improvement System

Analyzes trading performance, identifies areas for improvement,
and suggests optimizations based on actual results.

Usage:
    python3 continuous_improvement.py
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json

class ContinuousImprovement:
    def __init__(self, db_path='data/trading_system.db'):
        self.db_path = db_path
        self.report = {
            'timestamp': datetime.now().isoformat(),
            'metrics': {},
            'issues': [],
            'recommendations': [],
            'optimizations': []
        }
    
    def analyze_performance(self):
        """Analyze overall trading performance"""
        print("\n" + "=" * 80)
        print("CONTINUOUS IMPROVEMENT ANALYSIS")
        print("=" * 80)
        
        if not Path(self.db_path).exists():
            print("\n⚠️ No database found. Run the trading system first.")
            return
        
        conn = sqlite3.connect(self.db_path)
        
        # Get closed positions
        closed_positions = pd.read_sql_query(
            "SELECT * FROM positions WHERE status = 'closed'",
            conn
        )
        
        # Get all signals
        signals = pd.read_sql_query(
            "SELECT * FROM signals",
            conn
        )
        
        # Get performance history
        performance = pd.read_sql_query(
            "SELECT * FROM performance ORDER BY date",
            conn
        )
        
        conn.close()
        
        if len(closed_positions) == 0:
            print("\n⚠️ No closed positions yet. Need more trading history.")
            self.report['issues'].append("Insufficient trading history")
            return
        
        # Calculate metrics
        self._calculate_metrics(closed_positions, signals, performance)
        self._identify_issues(closed_positions, signals)
        self._generate_recommendations(closed_positions, signals)
        self._suggest_optimizations(closed_positions, signals, performance)
        
        # Print report
        self._print_report()
        
        # Save report
        self._save_report()
    
    def _calculate_metrics(self, positions, signals, performance):
        """Calculate key performance metrics"""
        print("\n📊 PERFORMANCE METRICS")
        print("-" * 80)
        
        # Win rate
        wins = len(positions[positions['return_pct'] > 0])
        total = len(positions)
        win_rate = (wins / total * 100) if total > 0 else 0
        
        # Average returns
        avg_return = positions['return_pct'].mean() * 100
        avg_win = positions[positions['return_pct'] > 0]['return_pct'].mean() * 100
        avg_loss = positions[positions['return_pct'] < 0]['return_pct'].mean() * 100
        
        # Profit factor
        total_wins = positions[positions['profit_loss'] > 0]['profit_loss'].sum()
        total_losses = abs(positions[positions['profit_loss'] < 0]['profit_loss'].sum())
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Signal efficiency
        executed_signals = len(signals[signals['action_taken'] == 'EXECUTED'])
        total_signals = len(signals)
        signal_efficiency = (executed_signals / total_signals * 100) if total_signals > 0 else 0
        
        # Store metrics
        metrics = {
            'total_trades': total,
            'win_rate': win_rate,
            'avg_return': avg_return,
            'avg_win': avg_win if not pd.isna(avg_win) else 0,
            'avg_loss': avg_loss if not pd.isna(avg_loss) else 0,
            'profit_factor': profit_factor,
            'total_profit': positions['profit_loss'].sum(),
            'signal_efficiency': signal_efficiency
        }
        
        self.report['metrics'] = metrics
        
        # Print metrics
        print(f"Total Trades: {total}")
        print(f"Win Rate: {win_rate:.1f}% (Target: >60%)")
        print(f"Avg Return/Trade: {avg_return:.2f}% (Target: >2%)")
        print(f"Avg Win: {avg_win:.2f}%")
        print(f"Avg Loss: {avg_loss:.2f}%")
        print(f"Profit Factor: {profit_factor:.2f} (Target: >2.0)")
        print(f"Total P/L: ${positions['profit_loss'].sum():.2f}")
        print(f"Signal Efficiency: {signal_efficiency:.1f}%")
    
    def _identify_issues(self, positions, signals):
        """Identify potential issues"""
        print("\n🔍 ISSUE DETECTION")
        print("-" * 80)
        
        metrics = self.report['metrics']
        issues_found = False
        
        # Check win rate
        if metrics['win_rate'] < 55:
            issue = f"⚠️ Win rate ({metrics['win_rate']:.1f}%) below minimum threshold (55%)"
            print(issue)
            self.report['issues'].append(issue)
            issues_found = True
        
        # Check average return
        if metrics['avg_return'] < 1.5:
            issue = f"⚠️ Avg return ({metrics['avg_return']:.2f}%) below target (2%)"
            print(issue)
            self.report['issues'].append(issue)
            issues_found = True
        
        # Check profit factor
        if metrics['profit_factor'] < 1.5:
            issue = f"⚠️ Profit factor ({metrics['profit_factor']:.2f}) below target (2.0)"
            print(issue)
            self.report['issues'].append(issue)
            issues_found = True
        
        # Check for consecutive losses
        positions_sorted = positions.sort_values('exit_date')
        consecutive_losses = 0
        max_consecutive_losses = 0
        
        for _, pos in positions_sorted.iterrows():
            if pos['return_pct'] < 0:
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            else:
                consecutive_losses = 0
        
        if max_consecutive_losses >= 5:
            issue = f"⚠️ Max consecutive losses: {max_consecutive_losses} (concerning)"
            print(issue)
            self.report['issues'].append(issue)
            issues_found = True
        
        # Check signal efficiency
        if metrics['signal_efficiency'] < 50:
            issue = f"⚠️ Low signal efficiency ({metrics['signal_efficiency']:.1f}%) - many signals not executed"
            print(issue)
            self.report['issues'].append(issue)
            issues_found = True
        
        if not issues_found:
            print("✅ No critical issues detected")
    
    def _generate_recommendations(self, positions, signals):
        """Generate improvement recommendations"""
        print("\n💡 RECOMMENDATIONS")
        print("-" * 80)
        
        metrics = self.report['metrics']
        
        # Analyze by symbol
        symbol_performance = positions.groupby('symbol').agg({
            'return_pct': ['mean', 'count'],
            'profit_loss': 'sum'
        }).round(4)
        
        # Find best and worst performers
        symbol_performance.columns = ['avg_return', 'trades', 'total_profit']
        symbol_performance = symbol_performance[symbol_performance['trades'] >= 2]  # Min 2 trades
        
        if len(symbol_performance) > 0:
            best_symbols = symbol_performance.nlargest(3, 'avg_return')
            worst_symbols = symbol_performance.nsmallest(3, 'avg_return')
            
            if len(best_symbols) > 0:
                rec = f"✅ Best performers: {', '.join(best_symbols.index.tolist())} - Consider increasing exposure"
                print(rec)
                self.report['recommendations'].append(rec)
            
            if len(worst_symbols) > 0 and worst_symbols.iloc[0]['avg_return'] < -0.02:
                rec = f"⚠️ Worst performers: {', '.join(worst_symbols.index.tolist())} - Consider excluding"
                print(rec)
                self.report['recommendations'].append(rec)
        
        # Analyze holding periods
        positions['days_held'] = pd.to_datetime(positions['exit_date']) - pd.to_datetime(positions['entry_date'])
        positions['days_held'] = positions['days_held'].dt.days
        
        avg_days = positions['days_held'].mean()
        if avg_days < 18:
            rec = f"📊 Average holding: {avg_days:.1f} days - Consider shorter holding period"
            print(rec)
            self.report['recommendations'].append(rec)
        elif avg_days > 22:
            rec = f"📊 Average holding: {avg_days:.1f} days - Consider longer holding period"
            print(rec)
            self.report['recommendations'].append(rec)
        
        # Analyze RSI thresholds
        executed_signals = signals[signals['action_taken'] == 'EXECUTED']
        if len(executed_signals) > 0:
            avg_rsi = executed_signals['rsi'].mean()
            if avg_rsi < 25:
                rec = f"📊 Avg entry RSI: {avg_rsi:.1f} - Very oversold, consider RSI < 25 threshold"
                print(rec)
                self.report['recommendations'].append(rec)
            elif avg_rsi > 28:
                rec = f"📊 Avg entry RSI: {avg_rsi:.1f} - Less oversold, consider tighter RSI < 28 threshold"
                print(rec)
                self.report['recommendations'].append(rec)
    
    def _suggest_optimizations(self, positions, signals, performance):
        """Suggest specific optimizations"""
        print("\n🚀 OPTIMIZATION SUGGESTIONS")
        print("-" * 80)
        
        metrics = self.report['metrics']
        
        # Position sizing optimization
        if metrics['win_rate'] > 65 and metrics['avg_return'] > 2.5:
            opt = "💰 Strong performance - Consider increasing position size to 12-15%"
            print(opt)
            self.report['optimizations'].append(opt)
        elif metrics['win_rate'] < 58:
            opt = "⚠️ Lower win rate - Consider reducing position size to 7-8%"
            print(opt)
            self.report['optimizations'].append(opt)
        
        # Diversification optimization
        if metrics['signal_efficiency'] < 60:
            opt = "📊 Low signal efficiency - Consider increasing max_positions to 12-15"
            print(opt)
            self.report['optimizations'].append(opt)
        
        # Volatility filter optimization
        executed_signals = signals[signals['action_taken'] == 'EXECUTED']
        if len(executed_signals) > 0:
            avg_vol = executed_signals['volatility_20d'].mean()
            median_vol = executed_signals['volatility_median'].mean()
            
            if avg_vol < median_vol * 1.1:
                opt = f"📊 Low volatility entries - Consider tightening filter to 1.15x median"
                print(opt)
                self.report['optimizations'].append(opt)
        
        # Data freshness
        if len(performance) > 0:
            latest_date = pd.to_datetime(performance['date'].max())
            days_old = (datetime.now() - latest_date).days
            
            if days_old > 30:
                opt = f"⚠️ Data is {days_old} days old - Update training_data.csv for better signals"
                print(opt)
                self.report['optimizations'].append(opt)
        
        if len(self.report['optimizations']) == 0:
            print("✅ System is well-optimized - Continue monitoring")
    
    def _print_report(self):
        """Print summary report"""
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        metrics = self.report['metrics']
        
        # Overall health score
        health_score = 0
        if metrics['win_rate'] >= 60:
            health_score += 25
        if metrics['avg_return'] >= 2:
            health_score += 25
        if metrics['profit_factor'] >= 2:
            health_score += 25
        if len(self.report['issues']) == 0:
            health_score += 25
        
        print(f"\n🎯 System Health Score: {health_score}/100")
        
        if health_score >= 75:
            print("   Status: ✅ EXCELLENT - System performing well")
        elif health_score >= 50:
            print("   Status: ⚠️ GOOD - Minor improvements needed")
        else:
            print("   Status: ❌ NEEDS ATTENTION - Review recommendations")
        
        print(f"\n📊 Key Metrics:")
        print(f"   Win Rate: {metrics['win_rate']:.1f}% (Target: >60%)")
        print(f"   Avg Return: {metrics['avg_return']:.2f}% (Target: >2%)")
        print(f"   Profit Factor: {metrics['profit_factor']:.2f} (Target: >2.0)")
        
        print(f"\n🔍 Issues Found: {len(self.report['issues'])}")
        print(f"💡 Recommendations: {len(self.report['recommendations'])}")
        print(f"🚀 Optimizations: {len(self.report['optimizations'])}")
    
    def _save_report(self):
        """Save report to file"""
        report_dir = Path('logs')
        report_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = report_dir / f'improvement_report_{timestamp}.json'
        
        with open(report_file, 'w') as f:
            json.dump(self.report, f, indent=2)
        
        print(f"\n📄 Report saved: {report_file}")

def main():
    """Main execution"""
    analyzer = ContinuousImprovement()
    analyzer.analyze_performance()
    
    print("\n" + "=" * 80)
    print("✅ CONTINUOUS IMPROVEMENT ANALYSIS COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("  1. Review recommendations and implement improvements")
    print("  2. Run this script weekly to track progress")
    print("  3. Compare metrics over time to measure improvement")
    print("  4. Update strategy parameters based on insights")

if __name__ == "__main__":
    main()
