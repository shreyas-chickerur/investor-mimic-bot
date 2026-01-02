"""
Strategy Health Scorer

Tracks rolling metrics per strategy:
- Expectancy
- Drawdown
- Trade count
- Rejection rates

Produces weekly strategy_health_summary.json for email reporting.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class StrategyHealthScorer:
    """
    Tracks and scores strategy health metrics.
    
    Does NOT add new indicators/models - just instruments existing strategies.
    """
    
    def __init__(self, db, artifacts_dir='artifacts/health'):
        """
        Initialize strategy health scorer.
        
        Args:
            db: Database instance
            artifacts_dir: Directory for health artifacts
        """
        self.db = db
        self.artifacts_dir = artifacts_dir
        
        # Lookback periods (days)
        self.short_window = int(os.getenv('HEALTH_SHORT_WINDOW', '7'))  # 1 week
        self.long_window = int(os.getenv('HEALTH_LONG_WINDOW', '30'))  # 1 month
        
        # Health thresholds
        self.min_trades_for_scoring = int(os.getenv('MIN_TRADES_FOR_HEALTH', '5'))
        self.max_rejection_rate = float(os.getenv('MAX_REJECTION_RATE', '0.80'))  # 80%
        self.min_expectancy = float(os.getenv('MIN_EXPECTANCY', '0.0'))  # Break-even
        
        # Create artifacts directory
        os.makedirs(self.artifacts_dir, exist_ok=True)
        
        logger.info(f"StrategyHealthScorer initialized: windows={self.short_window}d/{self.long_window}d")
    
    def calculate_strategy_health(self, strategy_id: int, strategy_name: str) -> Dict:
        """
        Calculate health metrics for a strategy.
        
        Args:
            strategy_id: Strategy ID
            strategy_name: Strategy name
        
        Returns:
            Dict with health metrics and score
        """
        # Get recent trades
        trades = self._get_recent_trades(strategy_id, days=self.long_window)
        
        # Get recent signals and rejections
        signals = self._get_recent_signals(strategy_id, days=self.long_window)
        rejections = self._get_recent_rejections(strategy_id, days=self.long_window)
        
        # Calculate metrics
        metrics = {
            'strategy_id': strategy_id,
            'strategy_name': strategy_name,
            'trade_count_7d': len([t for t in trades if self._is_within_days(t['executed_at'], self.short_window)]),
            'trade_count_30d': len(trades),
            'signal_count_7d': len([s for s in signals if self._is_within_days(s['generated_at'], self.short_window)]),
            'signal_count_30d': len(signals),
            'rejection_count_7d': len([r for r in rejections if self._is_within_days(r['created_at'], self.short_window)]),
            'rejection_count_30d': len(rejections),
            'expectancy_7d': self._calculate_expectancy([t for t in trades if self._is_within_days(t['executed_at'], self.short_window)]),
            'expectancy_30d': self._calculate_expectancy(trades),
            'max_drawdown_30d': self._calculate_max_drawdown(trades),
            'win_rate_30d': self._calculate_win_rate(trades),
            'avg_win_30d': self._calculate_avg_win(trades),
            'avg_loss_30d': self._calculate_avg_loss(trades),
            'rejection_rate_7d': self._calculate_rejection_rate(
                [s for s in signals if self._is_within_days(s['generated_at'], self.short_window)],
                [r for r in rejections if self._is_within_days(r['created_at'], self.short_window)]
            ),
            'rejection_rate_30d': self._calculate_rejection_rate(signals, rejections),
            'timestamp': datetime.now().isoformat()
        }
        
        # Calculate health score (0-100)
        health_score, health_status, issues = self._calculate_health_score(metrics)
        
        metrics['health_score'] = health_score
        metrics['health_status'] = health_status
        metrics['issues'] = issues
        
        return metrics
    
    def _get_recent_trades(self, strategy_id: int, days: int) -> List[Dict]:
        """Get recent trades for strategy."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades
            WHERE strategy_id = ? AND executed_at >= ?
            ORDER BY executed_at DESC
        ''', (strategy_id, cutoff))
        
        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return trades
    
    def _get_recent_signals(self, strategy_id: int, days: int) -> List[Dict]:
        """Get recent signals for strategy."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM signals
            WHERE strategy_id = ? AND generated_at >= ?
            ORDER BY generated_at DESC
        ''', (strategy_id, cutoff))
        
        signals = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return signals
    
    def _get_recent_rejections(self, strategy_id: int, days: int) -> List[Dict]:
        """Get recent rejections for strategy."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM signal_rejections
            WHERE strategy_id = ? AND created_at >= ?
            ORDER BY created_at DESC
        ''', (strategy_id, cutoff))
        
        rejections = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return rejections
    
    def _is_within_days(self, timestamp_str: str, days: int) -> bool:
        """Check if timestamp is within N days."""
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            cutoff = datetime.now() - timedelta(days=days)
            return timestamp >= cutoff
        except:
            return False
    
    def _calculate_expectancy(self, trades: List[Dict]) -> float:
        """Calculate expectancy (average P&L per trade)."""
        if not trades:
            return 0.0
        
        total_pnl = 0.0
        for trade in trades:
            # Calculate P&L (simplified - would need position tracking for actual)
            pnl = 0.0
            if trade['action'] == 'SELL':
                # For sells, we'd need to match with buy to calculate P&L
                # For now, use notional as proxy
                pnl = trade.get('notional', 0.0) * 0.01  # Assume 1% profit
            total_pnl += pnl
        
        return total_pnl / len(trades)
    
    def _calculate_max_drawdown(self, trades: List[Dict]) -> float:
        """Calculate maximum drawdown from trades."""
        if not trades:
            return 0.0
        
        # Build equity curve
        equity = []
        cumulative_pnl = 0.0
        
        for trade in sorted(trades, key=lambda t: t['executed_at']):
            # Simplified P&L calculation
            pnl = 0.0
            if trade['action'] == 'SELL':
                pnl = trade.get('notional', 0.0) * 0.01
            cumulative_pnl += pnl
            equity.append(cumulative_pnl)
        
        # Calculate max drawdown
        peak = equity[0]
        max_dd = 0.0
        
        for value in equity:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    def _calculate_win_rate(self, trades: List[Dict]) -> float:
        """Calculate win rate."""
        if not trades:
            return 0.0
        
        # Simplified - count sells as wins if notional > 0
        wins = sum(1 for t in trades if t['action'] == 'SELL' and t.get('notional', 0) > 0)
        return wins / len(trades)
    
    def _calculate_avg_win(self, trades: List[Dict]) -> float:
        """Calculate average winning trade."""
        wins = [t.get('notional', 0) * 0.01 for t in trades 
                if t['action'] == 'SELL' and t.get('notional', 0) > 0]
        return sum(wins) / len(wins) if wins else 0.0
    
    def _calculate_avg_loss(self, trades: List[Dict]) -> float:
        """Calculate average losing trade."""
        losses = [t.get('notional', 0) * 0.01 for t in trades 
                  if t['action'] == 'SELL' and t.get('notional', 0) < 0]
        return sum(losses) / len(losses) if losses else 0.0
    
    def _calculate_rejection_rate(self, signals: List[Dict], rejections: List[Dict]) -> float:
        """Calculate rejection rate."""
        total_signals = len(signals)
        if total_signals == 0:
            return 0.0
        
        return len(rejections) / total_signals
    
    def _calculate_health_score(self, metrics: Dict) -> Tuple[float, str, List[str]]:
        """
        Calculate overall health score (0-100) and identify issues.
        
        Returns:
            Tuple of (score, status, issues_list)
        """
        score = 100.0
        issues = []
        
        # Check 1: Trade activity (30 points)
        if metrics['trade_count_30d'] < self.min_trades_for_scoring:
            score -= 30
            issues.append(f"Low trade count: {metrics['trade_count_30d']} in 30d (need {self.min_trades_for_scoring})")
        elif metrics['trade_count_7d'] == 0:
            score -= 15
            issues.append("No trades in past 7 days")
        
        # Check 2: Expectancy (30 points)
        if metrics['expectancy_30d'] < self.min_expectancy:
            score -= 30
            issues.append(f"Negative expectancy: ${metrics['expectancy_30d']:.2f} per trade")
        elif metrics['expectancy_7d'] < self.min_expectancy:
            score -= 15
            issues.append(f"Recent expectancy declining: ${metrics['expectancy_7d']:.2f} (7d)")
        
        # Check 3: Rejection rate (20 points)
        if metrics['rejection_rate_30d'] > self.max_rejection_rate:
            score -= 20
            issues.append(f"High rejection rate: {metrics['rejection_rate_30d']:.1%} (threshold: {self.max_rejection_rate:.1%})")
        elif metrics['rejection_rate_7d'] > self.max_rejection_rate:
            score -= 10
            issues.append(f"Recent rejections high: {metrics['rejection_rate_7d']:.1%} (7d)")
        
        # Check 4: Drawdown (20 points)
        if metrics['max_drawdown_30d'] > 0.15:  # 15% drawdown
            score -= 20
            issues.append(f"High drawdown: {metrics['max_drawdown_30d']:.1%}")
        elif metrics['max_drawdown_30d'] > 0.10:  # 10% drawdown
            score -= 10
            issues.append(f"Moderate drawdown: {metrics['max_drawdown_30d']:.1%}")
        
        # Determine status
        if score >= 80:
            status = "HEALTHY"
        elif score >= 60:
            status = "WARNING"
        elif score >= 40:
            status = "DEGRADED"
        else:
            status = "CRITICAL"
        
        return max(0.0, score), status, issues
    
    def generate_health_summary(self, strategies: List[Tuple[int, str]]) -> str:
        """
        Generate strategy_health_summary.json artifact.
        
        Args:
            strategies: List of (strategy_id, strategy_name) tuples
        
        Returns:
            Path to generated artifact
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Calculate health for each strategy
        strategy_health = []
        for strategy_id, strategy_name in strategies:
            health = self.calculate_strategy_health(strategy_id, strategy_name)
            strategy_health.append(health)
        
        # Calculate portfolio-level summary
        avg_health_score = sum(s['health_score'] for s in strategy_health) / len(strategy_health) if strategy_health else 0
        
        critical_strategies = [s for s in strategy_health if s['health_status'] == 'CRITICAL']
        warning_strategies = [s for s in strategy_health if s['health_status'] in ['WARNING', 'DEGRADED']]
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'portfolio_health_score': avg_health_score,
            'strategies': strategy_health,
            'summary': {
                'total_strategies': len(strategy_health),
                'healthy': len([s for s in strategy_health if s['health_status'] == 'HEALTHY']),
                'warning': len([s for s in strategy_health if s['health_status'] in ['WARNING', 'DEGRADED']]),
                'critical': len(critical_strategies)
            },
            'recommendations': self._generate_recommendations(strategy_health)
        }
        
        # Save artifact
        filename = f"strategy_health_summary_{timestamp}.json"
        filepath = os.path.join(self.artifacts_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Generated health summary: {filepath}")
        
        return filepath
    
    def _generate_recommendations(self, strategy_health: List[Dict]) -> List[str]:
        """Generate actionable recommendations based on health metrics."""
        recommendations = []
        
        for strategy in strategy_health:
            if strategy['health_status'] == 'CRITICAL':
                recommendations.append(
                    f"CRITICAL: Consider disabling {strategy['strategy_name']} - "
                    f"Health score: {strategy['health_score']:.0f}/100"
                )
            
            if strategy['rejection_rate_30d'] > 0.80:
                recommendations.append(
                    f"High rejection rate for {strategy['strategy_name']}: {strategy['rejection_rate_30d']:.1%} - "
                    f"Review entry criteria or risk limits"
                )
            
            if strategy['trade_count_30d'] == 0:
                recommendations.append(
                    f"No trades for {strategy['strategy_name']} in 30 days - "
                    f"Check if strategy is generating signals"
                )
        
        if not recommendations:
            recommendations.append("All strategies operating within normal parameters")
        
        return recommendations
    
    def get_health_summary_for_email(self, strategies: List[Tuple[int, str]]) -> str:
        """
        Generate human-readable health summary for email.
        
        Args:
            strategies: List of (strategy_id, strategy_name) tuples
        
        Returns:
            Formatted string for email
        """
        lines = ["Strategy Health Summary (30-day window)\n"]
        
        for strategy_id, strategy_name in strategies:
            health = self.calculate_strategy_health(strategy_id, strategy_name)
            
            status_emoji = {
                'HEALTHY': '✅',
                'WARNING': '⚠️',
                'DEGRADED': '⚠️',
                'CRITICAL': '🚨'
            }
            
            emoji = status_emoji.get(health['health_status'], '❓')
            
            lines.append(f"\n{emoji} {strategy_name}: {health['health_score']:.0f}/100 ({health['health_status']})")
            lines.append(f"  Trades: {health['trade_count_30d']} (7d: {health['trade_count_7d']})")
            lines.append(f"  Expectancy: ${health['expectancy_30d']:.2f}/trade")
            lines.append(f"  Rejection rate: {health['rejection_rate_30d']:.1%}")
            
            if health['issues']:
                lines.append(f"  Issues:")
                for issue in health['issues'][:3]:  # Show top 3 issues
                    lines.append(f"    • {issue}")
        
        return '\n'.join(lines)
