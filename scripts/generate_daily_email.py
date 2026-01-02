#!/usr/bin/env python3
"""
Generate Daily Email Digest

Reads the daily artifact JSON and generates a properly formatted HTML email
using the EmailNotifier class format.
"""
import sys
import json
from pathlib import Path
from datetime import datetime
import sqlite3
from collections import defaultdict
import glob

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

def get_drawdown_status(db_path='trading.db'):
    """Get current drawdown stop status"""
    try:
        conn = sqlite3.connect(db_path)
        result = conn.execute("SELECT value FROM system_state WHERE key='drawdown_stop_state'").fetchone()
        conn.close()
        
        if result:
            state_data = json.loads(result[0])
            return state_data
    except:
        pass
    return {'state': 'NORMAL', 'drawdown': 0.0}

def get_latest_artifact(artifact_type):
    """Get latest artifact of given type"""
    patterns = {
        'data_quality': 'artifacts/data_quality/data_quality_report_*.json',
        'funnel': 'artifacts/funnel/signal_funnel_*.json',
        'health': 'artifacts/health/strategy_health_summary_*.json',
        'why_no_trade': 'artifacts/funnel/why_no_trade_summary_*.json'
    }
    
    pattern = patterns.get(artifact_type)
    if not pattern:
        return None
    
    files = glob.glob(pattern)
    if not files:
        return None
    
    latest = max(files, key=lambda x: Path(x).stat().st_mtime)
    try:
        with open(latest) as f:
            return json.load(f)
    except:
        return None

def get_strategy_performance_today(db_path='trading.db'):
    """Get today's strategy performance from database"""
    if db_path is None:
        return []
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    query = '''
        SELECT 
            s.name as strategy,
            COUNT(*) as trades,
            SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN t.pnl < 0 THEN 1 ELSE 0 END) as losses,
            SUM(t.pnl) as total_pnl,
            AVG(t.pnl) as avg_pnl
        FROM trades t
        JOIN strategies s ON t.strategy_id = s.id
        WHERE DATE(t.executed_at) = DATE('now')
        AND t.pnl IS NOT NULL
        GROUP BY s.name
        ORDER BY total_pnl DESC
    '''
    
    results = conn.execute(query).fetchall()
    conn.close()
    
    return [dict(row) for row in results]

def generate_safety_features_html(db_path='trading.db'):
    """Generate HTML section for safety features status"""
    html = "<div style='background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;'>"
    html += "<h3 style='color: #2c5282; margin: 0 0 15px 0; font-size: 18px;'>🛡️ Safety Systems Status</h3>"
    
    # Drawdown status
    drawdown_state = get_drawdown_status(db_path)
    state = drawdown_state.get('state', 'NORMAL')
    drawdown_pct = drawdown_state.get('drawdown', 0.0) * 100
    
    if state == 'NORMAL':
        status_color = '#28a745'
        status_icon = '✅'
        status_text = f'Normal Operation (Drawdown: {drawdown_pct:.1f}%)'
    elif state == 'RAMPUP':
        status_color = '#ff9800'
        status_icon = '⚠️'
        status_text = f'Rampup Mode - 50% Sizing (Drawdown: {drawdown_pct:.1f}%)'
    elif state == 'HALT':
        status_color = '#dc3545'
        status_icon = '🛑'
        status_text = f'HALT - Cooldown Active (Drawdown: {drawdown_pct:.1f}%)'
    else:
        status_color = '#dc3545'
        status_icon = '🚨'
        status_text = f'PANIC MODE (Drawdown: {drawdown_pct:.1f}%)'
    
    html += f"<div style='margin-bottom: 10px;'>"
    html += f"<strong style='color: {status_color};'>{status_icon} Drawdown Stop:</strong> "
    html += f"<span style='color: #333;'>{status_text}</span>"
    html += "</div>"
    
    # Data quality
    data_quality = get_latest_artifact('data_quality')
    if data_quality:
        blocked_count = len(data_quality.get('blocked_symbols', []))
        total_symbols = data_quality.get('symbols_checked', 0)
        if blocked_count > 0:
            html += f"<div style='margin-bottom: 10px;'>"
            html += f"<strong style='color: #ff9800;'>⚠️ Data Quality:</strong> "
            html += f"<span style='color: #333;'>{blocked_count}/{total_symbols} symbols blocked</span>"
            html += "</div>"
        else:
            html += f"<div style='margin-bottom: 10px;'>"
            html += f"<strong style='color: #28a745;'>✅ Data Quality:</strong> "
            html += f"<span style='color: #333;'>All {total_symbols} symbols passed</span>"
            html += "</div>"
    
    # Signal funnel summary
    funnel = get_latest_artifact('funnel')
    if funnel:
        funnel_data = funnel.get('funnel', {})
        raw = funnel_data.get('raw_signals', 0)
        executed = funnel_data.get('executed', 0)
        conversion = (executed / raw * 100) if raw > 0 else 0
        
        html += f"<div style='margin-bottom: 10px;'>"
        html += f"<strong style='color: #2c5282;'>📊 Signal Funnel:</strong> "
        html += f"<span style='color: #333;'>{raw} raw → {executed} executed ({conversion:.1f}% conversion)</span>"
        html += "</div>"
    
    # Why no trade
    why_no_trade = get_latest_artifact('why_no_trade')
    if why_no_trade:
        html += f"<div style='margin-bottom: 10px; padding: 10px; background: #fff3cd; border-radius: 4px;'>"
        html += f"<strong style='color: #856404;'>ℹ️ No Trades Today:</strong> "
        top_reason = why_no_trade.get('top_blocker', {}).get('stage', 'Unknown')
        html += f"<span style='color: #856404;'>Primary blocker: {top_reason}</span>"
        html += "</div>"
    
    html += "</div>"
    return html

def generate_strategy_health_html():
    """Generate HTML section for strategy health scores"""
    health_data = get_latest_artifact('health')
    if not health_data:
        return ""
    
    html = "<div style='margin-bottom: 30px;'>"
    html += "<h2 style='color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px; font-size: 20px; font-weight: 600;'>"
    html += "Strategy Health Scores"
    html += "</h2>"
    
    strategies = health_data.get('strategies', [])
    if strategies:
        html += "<table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>"
        html += "<tr style='background: #f8f9fa; border-bottom: 2px solid #dee2e6;'>"
        html += "<th style='padding: 10px; text-align: left;'>Strategy</th>"
        html += "<th style='padding: 10px; text-align: center;'>Health Score</th>"
        html += "<th style='padding: 10px; text-align: center;'>Status</th>"
        html += "<th style='padding: 10px; text-align: left;'>Issues</th>"
        html += "</tr>"
        
        for strat in strategies:
            score = strat.get('health_score', 0)
            status = strat.get('health_status', 'UNKNOWN')
            issues = strat.get('issues', [])
            
            # Color coding
            if status == 'HEALTHY':
                status_color = '#28a745'
                status_icon = '✅'
            elif status == 'WARNING':
                status_color = '#ff9800'
                status_icon = '⚠️'
            elif status == 'DEGRADED':
                status_color = '#ff6b35'
                status_icon = '⚠️'
            else:
                status_color = '#dc3545'
                status_icon = '🚨'
            
            html += f"<tr style='border-bottom: 1px solid #dee2e6;'>"
            html += f"<td style='padding: 10px;'>{strat.get('strategy_name', 'Unknown')}</td>"
            html += f"<td style='padding: 10px; text-align: center; font-weight: bold;'>{score}/100</td>"
            html += f"<td style='padding: 10px; text-align: center; color: {status_color}; font-weight: bold;'>{status_icon} {status}</td>"
            html += f"<td style='padding: 10px; font-size: 12px; color: #666;'>{', '.join(issues[:2]) if issues else 'None'}</td>"
            html += "</tr>"
        
        html += "</table>"
        
        # Add portfolio health score
        portfolio_score = health_data.get('portfolio_health_score', 0)
        html += f"<div style='margin-top: 15px; padding: 15px; background: #f8f9fa; border-radius: 8px;'>"
        html += f"<strong style='color: #2c5282;'>Portfolio Health Score:</strong> "
        html += f"<span style='font-size: 24px; font-weight: bold; color: #2c5282;'>{portfolio_score}/100</span>"
        html += "</div>"
    
    html += "</div>"
    return html

def generate_actionable_insights(trades, positions, strategy_perf, recon_status, regime):
    """Generate actionable insights section with what's working, what isn't, and recommendations"""
    insights = []
    warnings = []
    actions = []
    
    # Check if system is executing trades
    if len(trades) == 0:
        warnings.append("⚠️ <strong>No trades executed today</strong>")
        actions.append("Check if strategies are generating signals (view GitHub Actions logs)")
        actions.append("Verify market was open (check for holidays/weekends)")
        actions.append("Review if risk filters are too strict (correlation, portfolio heat)")
    else:
        insights.append(f"✅ <strong>{len(trades)} trades executed</strong> - System is active")
    
    # Check reconciliation
    if 'FAIL' in recon_status:
        warnings.append("❌ <strong>Broker reconciliation failed</strong>")
        actions.append("<strong>URGENT:</strong> Check Alpaca positions vs local database")
        actions.append("Review discrepancies in GitHub Actions logs")
    elif 'PASS' in recon_status:
        insights.append("✅ <strong>Broker reconciliation passed</strong> - Positions in sync")
    
    # Check strategy performance
    if strategy_perf:
        profitable = [s for s in strategy_perf if s['total_pnl'] > 0]
        losing = [s for s in strategy_perf if s['total_pnl'] < 0]
        
        if profitable:
            top = profitable[0]
            insights.append(f"✅ <strong>Top performer:</strong> {top['strategy']} (${top['total_pnl']:+.2f})")
        
        if losing:
            worst = losing[-1]
            warnings.append(f"⚠️ <strong>Underperformer:</strong> {worst['strategy']} (${worst['total_pnl']:+.2f})")
            if worst['trades'] >= 5:  # Only suggest action if enough data
                actions.append(f"Consider reviewing {worst['strategy']} parameters or allocation")
    
    # Check regime
    if regime == 'CRISIS':
        warnings.append("⚠️ <strong>Crisis regime detected</strong> - Portfolio heat reduced to 20%")
        actions.append("Monitor positions closely for stop losses")
        actions.append("Expect reduced trade frequency due to risk controls")
    elif regime == 'HIGH_VOL':
        insights.append("ℹ️ <strong>High volatility regime</strong> - Portfolio heat at 25%")
    
    # Check positions
    if len(positions) == 0 and len(trades) > 0:
        insights.append("ℹ️ All trades closed - No overnight exposure")
    elif len(positions) > 0:
        insights.append(f"ℹ️ <strong>{len(positions)} open positions</strong> - Monitor for stop losses")
    
    # Build HTML
    html = "<div style='background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;'>"
    
    if insights:
        html += "<div style='margin-bottom: 15px;'>"
        html += "<h3 style='color: #28a745; margin: 0 0 10px 0; font-size: 16px;'>✅ What's Working</h3>"
        for insight in insights:
            html += f"<div style='margin: 5px 0; color: #333;'>{insight}</div>"
        html += "</div>"
    
    if warnings:
        html += "<div style='margin-bottom: 15px;'>"
        html += "<h3 style='color: #ff9800; margin: 0 0 10px 0; font-size: 16px;'>⚠️ What Needs Attention</h3>"
        for warning in warnings:
            html += f"<div style='margin: 5px 0; color: #333;'>{warning}</div>"
        html += "</div>"
    
    if actions:
        html += "<div>"
        html += "<h3 style='color: #2c5282; margin: 0 0 10px 0; font-size: 16px;'>🎯 Recommended Actions</h3>"
        html += "<ol style='margin: 0; padding-left: 20px; color: #333;'>"
        for action in actions:
            html += f"<li style='margin: 5px 0;'>{action}</li>"
        html += "</ol>"
        html += "</div>"
    
    if not insights and not warnings and not actions:
        html += "<p style='color: #666; font-style: italic;'>No specific insights available - system operating normally</p>"
    
    html += "</div>"
    return html

def generate_email_body(artifact_path: str, db_path='trading.db', include_visuals=False) -> str:
    """Generate HTML email body from artifact JSON
    
    Args:
        artifact_path: Path to daily artifact JSON (or None if no artifact exists)
        db_path: Path to trading database
        include_visuals: If True, embed strategy performance charts (Mon/Wed/Fri)
    """
    
    # Load artifact data if available, otherwise use empty structures
    if artifact_path and Path(artifact_path).exists():
        with open(artifact_path) as f:
            data = json.load(f)
    else:
        data = {}
    
    # Extract data from artifact
    trades_data = data.get('trades', {})
    positions_data = data.get('positions', {})
    risk_data = data.get('risk', {})
    regime_data = data.get('regime', {})
    system_health = data.get('system_health', {})
    
    # Get trades list (handle both formats)
    placed_trades = trades_data.get('placed', []) if isinstance(trades_data, dict) else trades_data
    filled_trades = trades_data.get('filled', []) if isinstance(trades_data, dict) else []
    trades = filled_trades or placed_trades
    
    # Get positions list
    open_positions = positions_data.get('open', []) if isinstance(positions_data, dict) else positions_data
    
    # Extract metrics
    portfolio_value = risk_data.get('portfolio_value', 100000)
    cash = risk_data.get('cash', 0)
    daily_pnl = risk_data.get('daily_pnl', 0)
    portfolio_heat = risk_data.get('portfolio_heat', 0)
    
    # Reconciliation status
    recon_status = system_health.get('reconciliation_status', 'UNKNOWN')
    recon_emoji = '✅' if 'PASS' in recon_status else '❌'
    
    # Market regime
    regime_class = regime_data.get('classification', 'unknown').upper()
    vix = regime_data.get('vix', 'N/A')
    
    # Count trades by action
    buys = [t for t in trades if t.get('action') == 'BUY']
    sells = [t for t in trades if t.get('action') == 'SELL']
    
    # Get strategy performance
    strategy_perf = get_strategy_performance_today(db_path)
    
    # Build trades table
    trades_html = ""
    if trades:
        trades_html = "<table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>"
        trades_html += "<tr style='background: #f8f9fa; border-bottom: 2px solid #dee2e6;'>"
        trades_html += "<th style='padding: 10px; text-align: left;'>Action</th>"
        trades_html += "<th style='padding: 10px; text-align: left;'>Symbol</th>"
        trades_html += "<th style='padding: 10px; text-align: right;'>Shares</th>"
        trades_html += "<th style='padding: 10px; text-align: right;'>Price</th>"
        trades_html += "<th style='padding: 10px; text-align: left;'>Strategy</th>"
        trades_html += "</tr>"
        
        for trade in trades:
            action_color = '#28a745' if trade.get('action') == 'BUY' else '#dc3545'
            trades_html += f"<tr style='border-bottom: 1px solid #dee2e6;'>"
            trades_html += f"<td style='padding: 10px; color: {action_color}; font-weight: bold;'>{trade.get('action', 'N/A')}</td>"
            trades_html += f"<td style='padding: 10px;'>{trade.get('symbol', 'N/A')}</td>"
            trades_html += f"<td style='padding: 10px; text-align: right;'>{trade.get('shares', 0)}</td>"
            trades_html += f"<td style='padding: 10px; text-align: right;'>${trade.get('price', 0):.2f}</td>"
            trades_html += f"<td style='padding: 10px;'>{trade.get('strategy', 'N/A')}</td>"
            trades_html += "</tr>"
        
        trades_html += "</table>"
    else:
        trades_html = "<p style='color: #666; font-style: italic;'>No trades executed today</p>"
    
    # Build positions table
    positions_html = ""
    if open_positions:
        positions_html = "<table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>"
        positions_html += "<tr style='background: #f8f9fa; border-bottom: 2px solid #dee2e6;'>"
        positions_html += "<th style='padding: 10px; text-align: left;'>Symbol</th>"
        positions_html += "<th style='padding: 10px; text-align: right;'>Shares</th>"
        positions_html += "<th style='padding: 10px; text-align: right;'>Entry Price</th>"
        positions_html += "<th style='padding: 10px; text-align: right;'>Current Price</th>"
        positions_html += "<th style='padding: 10px; text-align: right;'>P&L</th>"
        positions_html += "</tr>"
        
        for pos in open_positions[:10]:
            entry_price = pos.get('entry_price', 0)
            current_price = pos.get('current_price', entry_price)
            shares = pos.get('shares', 0)
            pnl = (current_price - entry_price) * shares
            pnl_color = '#28a745' if pnl >= 0 else '#dc3545'
            
            positions_html += f"<tr style='border-bottom: 1px solid #dee2e6;'>"
            positions_html += f"<td style='padding: 10px;'>{pos.get('symbol', 'N/A')}</td>"
            positions_html += f"<td style='padding: 10px; text-align: right;'>{shares}</td>"
            positions_html += f"<td style='padding: 10px; text-align: right;'>${entry_price:.2f}</td>"
            positions_html += f"<td style='padding: 10px; text-align: right;'>${current_price:.2f}</td>"
            positions_html += f"<td style='padding: 10px; text-align: right; color: {pnl_color}; font-weight: bold;'>${pnl:+.2f}</td>"
            positions_html += "</tr>"
        
        positions_html += "</table>"
    else:
        positions_html = "<p style='color: #666; font-style: italic;'>No open positions</p>"
    
    # Load strategy chart if visuals are enabled
    strategy_chart_html = ""
    if include_visuals:
        try:
            chart_path = Path('/tmp/strategy_chart.html')
            if chart_path.exists():
                with open(chart_path) as f:
                    strategy_chart_html = f.read()
        except Exception as e:
            print(f"Warning: Could not load strategy chart: {e}")
    
    # Generate safety features section
    safety_html = generate_safety_features_html(db_path)
    
    # Generate strategy health section
    health_html = generate_strategy_health_html()
    
    # Generate actionable insights
    insights_html = generate_actionable_insights(trades, open_positions, strategy_perf, recon_status, regime_class)
    
    # Build strategy performance table
    strategy_html = ""
    if strategy_perf:
        strategy_html = "<table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>"
        strategy_html += "<tr style='background: #f8f9fa; border-bottom: 2px solid #dee2e6;'>"
        strategy_html += "<th style='padding: 10px; text-align: left;'>Strategy</th>"
        strategy_html += "<th style='padding: 10px; text-align: right;'>Trades</th>"
        strategy_html += "<th style='padding: 10px; text-align: right;'>Win Rate</th>"
        strategy_html += "<th style='padding: 10px; text-align: right;'>Avg P&L</th>"
        strategy_html += "<th style='padding: 10px; text-align: right;'>Total P&L</th>"
        strategy_html += "</tr>"
        
        for i, strat in enumerate(strategy_perf):
            win_rate = (strat['wins'] / strat['trades'] * 100) if strat['trades'] > 0 else 0
            pnl_color = '#28a745' if strat['total_pnl'] >= 0 else '#dc3545'
            
            # Highlight top performer
            bg_color = '#e8f5e9' if i == 0 and strat['total_pnl'] > 0 else 'white'
            
            strategy_html += f"<tr style='border-bottom: 1px solid #dee2e6; background: {bg_color};'>"
            strategy_html += f"<td style='padding: 10px; font-weight: {'bold' if i == 0 else 'normal'};'>{strat['strategy']}</td>"
            strategy_html += f"<td style='padding: 10px; text-align: right;'>{strat['trades']}</td>"
            strategy_html += f"<td style='padding: 10px; text-align: right;'>{win_rate:.1f}%</td>"
            strategy_html += f"<td style='padding: 10px; text-align: right;'>${strat['avg_pnl']:.2f}</td>"
            strategy_html += f"<td style='padding: 10px; text-align: right; color: {pnl_color}; font-weight: bold;'>${strat['total_pnl']:+.2f}</td>"
            strategy_html += "</tr>"
        
        strategy_html += "</table>"
    else:
        strategy_html = "<p style='color: #666; font-style: italic;'>No strategy data available</p>"
    
    # Build complete HTML email
    pnl_color = '#10b981' if daily_pnl >= 0 else '#dc3545'
    pnl_sign = '+' if daily_pnl >= 0 else ''
    
    html = f"""
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 900px; margin: 0 auto; background: #f5f5f5;">
    <!-- Header with blue gradient -->
    <div style="background: linear-gradient(135deg, #2c5282 0%, #4A90E2 100%); color: white; padding: 40px 30px; border-radius: 8px 8px 0 0;">
        <div style="color: #FFA500; font-size: 14px; font-weight: 700; letter-spacing: 2px; margin-bottom: 10px;">DAILY TRADING DIGEST</div>
        <h1 style="margin: 0; font-size: 32px; font-weight: 600;">Execution Complete</h1>
        <p style="margin: 8px 0 0 0; opacity: 0.95; font-size: 16px;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
    </div>
    
    <!-- Orange status bar -->
    <div style="background: #FF6B35; color: white; padding: 20px 30px; font-size: 15px;">
        <div style="margin-bottom: 5px;">{recon_emoji} <strong>Reconciliation: {recon_status}</strong></div>
        <div>{len(trades)} trades executed • Market regime: {regime_class} (VIX: {vix})</div>
    </div>
    
    <div style="padding: 30px; background: white;">
        <!-- Safety Features Status -->
        {safety_html}
        
        <!-- Actionable Insights -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #2c5282; font-size: 24px; margin-bottom: 15px; font-weight: 600;">📊 Daily Insights</h2>
            {insights_html}
        </div>
        
        <!-- Today's Summary Header -->
        <h2 style="color: #2c5282; font-size: 24px; margin-bottom: 25px; font-weight: 600;">Today's Summary</h2>
        
        <!-- Portfolio Overview Cards -->
        <div style="margin-bottom: 30px;">
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4A90E2;">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">PORTFOLIO</div>
                <div style="font-size: 36px; font-weight: 700; color: #2c5282;">${portfolio_value:,.0f}</div>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4A90E2;">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">CASH AVAILABLE</div>
                <div style="font-size: 36px; font-weight: 700; color: #2c5282;">${cash:,.0f}</div>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4A90E2;">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">PORTFOLIO HEAT</div>
                <div style="font-size: 36px; font-weight: 700; color: #2c5282;">{portfolio_heat:.1f}%</div>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; border-left: 4px solid {pnl_color};">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">DAILY P&L</div>
                <div style="font-size: 36px; font-weight: 700; color: {pnl_color};">{pnl_sign}${daily_pnl:.2f}</div>
            </div>
        </div>
        
        <!-- Trade Summary -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px; font-size: 20px; font-weight: 600;">
                Trades Executed ({len(trades)})
            </h2>
            <div style="margin: 15px 0;">
                <span style="background: #4A90E2; color: white; padding: 8px 16px; border-radius: 20px; margin-right: 10px; font-weight: 600; font-size: 14px;">
                    {len(buys)} Buys
                </span>
                <span style="background: #FF6B35; color: white; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 14px;">
                    {len(sells)} Sells
                </span>
            </div>
            {trades_html}
        </div>
        
        <!-- Strategy Performance -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px; font-size: 20px; font-weight: 600;">
                Strategy Performance (Today)
            </h2>
            {strategy_html}
        </div>
        
        <!-- Strategy Health Scores (Weekly) -->
        {health_html}
        
        <!-- Strategy Performance Charts (Mon/Wed/Fri only) -->
        {f'''
        <div style="margin-bottom: 30px;">
            <h2 style="color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px; font-size: 20px; font-weight: 600;">
                Weekly Strategy Analysis
            </h2>
            <p style="color: #6b7280; margin-bottom: 15px;">7-day cumulative performance and 30-day win rate comparison</p>
            {strategy_chart_html}
        </div>
        ''' if include_visuals and strategy_chart_html else ''}
        
        <!-- Current Positions -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px; font-size: 20px; font-weight: 600;">
                Current Positions ({len(open_positions)})
            </h2>
            {positions_html}
        </div>
        
        <!-- Footer -->
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 12px;">
            <p>View detailed logs and artifacts in GitHub Actions</p>
            <p style="margin-top: 10px;">This is an automated message from your trading system.</p>
        </div>
    </div>
</body>
</html>
"""
    
    return html

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate daily email digest')
    parser.add_argument('--include-visuals', action='store_true', 
                       help='Include strategy performance charts (Mon/Wed/Fri)')
    args = parser.parse_args()
    
    # Get today's artifact path
    date = datetime.now().strftime('%Y-%m-%d')
    artifact_path = Path(f'artifacts/json/{date}.json')
    
    if not artifact_path.exists():
        print(f"⚠️  No artifact found for {date}, generating email with database data only")
        # Generate email without artifact (will use database data)
        html = generate_email_body(None, db_path='trading.db', 
                                  include_visuals=args.include_visuals)
    else:
        # Generate email with artifact
        html = generate_email_body(str(artifact_path), db_path='trading.db', 
                                  include_visuals=args.include_visuals)
    
    # Save to file for workflow to use
    output_path = '/tmp/daily_email.html'
    with open(output_path, 'w') as f:
        f.write(html)
    
    visual_status = "with visuals" if args.include_visuals else "standard"
    print(f"✅ Email HTML generated ({visual_status}): {output_path}")
    sys.exit(0)
