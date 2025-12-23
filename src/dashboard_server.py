#!/usr/bin/env python3
"""
Web Dashboard for Multi-Strategy Trading System
Real-time monitoring of all 5 strategies in browser
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, render_template_string, jsonify
from strategy_database import StrategyDatabase
from datetime import datetime
import sqlite3

app = Flask(__name__)
db = StrategyDatabase()

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Multi-Strategy Trading Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header h1 {
            color: #2d3748;
            font-size: 32px;
            margin-bottom: 10px;
        }
        .header .subtitle {
            color: #718096;
            font-size: 14px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .stat-label {
            color: #718096;
            font-size: 12px;
            text-transform: uppercase;
            margin-bottom: 8px;
            font-weight: 600;
        }
        .stat-value {
            color: #2d3748;
            font-size: 28px;
            font-weight: 700;
        }
        .stat-value.positive { color: #48bb78; }
        .stat-value.negative { color: #f56565; }
        .strategies-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px;
        }
        .strategy-card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .strategy-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #e2e8f0;
        }
        .strategy-name {
            font-size: 20px;
            font-weight: 700;
            color: #2d3748;
        }
        .strategy-status {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-active {
            background: #c6f6d5;
            color: #22543d;
        }
        .status-idle {
            background: #fed7d7;
            color: #742a2a;
        }
        .strategy-metrics {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        .metric {
            background: #f7fafc;
            padding: 12px;
            border-radius: 8px;
        }
        .metric-label {
            font-size: 11px;
            color: #718096;
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        .metric-value {
            font-size: 18px;
            font-weight: 700;
            color: #2d3748;
        }
        .trades-list {
            margin-top: 15px;
        }
        .trades-header {
            font-size: 14px;
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 10px;
        }
        .trade-item {
            background: #f7fafc;
            padding: 10px;
            border-radius: 6px;
            margin-bottom: 8px;
            font-size: 13px;
        }
        .trade-buy { border-left: 3px solid #48bb78; }
        .trade-sell { border-left: 3px solid #f56565; }
        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: white;
            border: none;
            padding: 15px 25px;
            border-radius: 50px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            cursor: pointer;
            font-weight: 600;
            color: #667eea;
            font-size: 14px;
        }
        .refresh-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0,0,0,0.2);
        }
        .no-data {
            color: #a0aec0;
            font-style: italic;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Multi-Strategy Trading Dashboard</h1>
            <div class="subtitle">Real-time monitoring • Last updated: <span id="last-update"></span></div>
        </div>

        <div class="stats-grid" id="overall-stats"></div>
        <div class="strategies-grid" id="strategies"></div>
    </div>

    <button class="refresh-btn" onclick="loadData()">🔄 Refresh</button>

    <script>
        function loadData() {
            fetch('/api/dashboard')
                .then(r => r.json())
                .then(data => {
                    renderOverallStats(data.overall);
                    renderStrategies(data.strategies);
                    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                });
        }

        function renderOverallStats(stats) {
            const html = `
                <div class="stat-card">
                    <div class="stat-label">Total Capital</div>
                    <div class="stat-value">$${stats.total_capital.toLocaleString()}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Active Strategies</div>
                    <div class="stat-value">${stats.active_strategies}/5</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Trades</div>
                    <div class="stat-value">${stats.total_trades}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Avg Return</div>
                    <div class="stat-value ${stats.avg_return >= 0 ? 'positive' : 'negative'}">
                        ${stats.avg_return >= 0 ? '+' : ''}${stats.avg_return.toFixed(2)}%
                    </div>
                </div>
            `;
            document.getElementById('overall-stats').innerHTML = html;
        }

        function renderStrategies(strategies) {
            const html = strategies.map(s => `
                <div class="strategy-card">
                    <div class="strategy-header">
                        <div class="strategy-name">${s.name}</div>
                        <div class="strategy-status ${s.is_active ? 'status-active' : 'status-idle'}">
                            ${s.is_active ? '✅ Active' : '⏸️ Idle'}
                        </div>
                    </div>
                    
                    <div class="strategy-metrics">
                        <div class="metric">
                            <div class="metric-label">Capital</div>
                            <div class="metric-value">$${s.capital.toLocaleString()}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Return</div>
                            <div class="metric-value ${s.return_pct >= 0 ? 'positive' : 'negative'}">
                                ${s.return_pct >= 0 ? '+' : ''}${s.return_pct.toFixed(2)}%
                            </div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Positions</div>
                            <div class="metric-value">${s.num_positions}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Trades</div>
                            <div class="metric-value">${s.num_trades}</div>
                        </div>
                    </div>

                    <div class="trades-list">
                        <div class="trades-header">Recent Trades</div>
                        ${s.recent_trades.length > 0 ? s.recent_trades.map(t => `
                            <div class="trade-item trade-${t.action.toLowerCase()}">
                                <strong>${t.action}</strong> ${t.shares} ${t.symbol} @ $${t.price.toFixed(2)}
                                <div style="font-size: 11px; color: #718096; margin-top: 4px;">
                                    ${new Date(t.executed_at).toLocaleString()}
                                </div>
                            </div>
                        `).join('') : '<div class="no-data">No trades yet</div>'}
                    </div>
                </div>
            `).join('');
            document.getElementById('strategies').innerHTML = html;
        }

        // Load data on page load and refresh every 30 seconds
        loadData();
        setInterval(loadData, 30000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/dashboard')
def api_dashboard():
    """API endpoint for dashboard data"""
    strategies = db.get_all_strategies()
    
    overall_stats = {
        'total_capital': 0,
        'active_strategies': 0,
        'total_trades': 0,
        'avg_return': 0
    }
    
    strategy_data = []
    total_return = 0
    
    for strat in strategies:
        perf = db.get_latest_performance(strat['id'])
        trades = db.get_strategy_trades(strat['id'])
        
        capital = strat['capital_allocation']
        overall_stats['total_capital'] += capital
        
        if perf:
            return_pct = perf['total_return_pct']
            num_positions = perf['num_positions']
            total_return += (capital * return_pct / 100)
        else:
            return_pct = 0.0
            num_positions = 0
        
        num_trades = len(trades)
        overall_stats['total_trades'] += num_trades
        
        is_active = num_positions > 0 or num_trades > 0
        if is_active:
            overall_stats['active_strategies'] += 1
        
        strategy_data.append({
            'name': strat['name'],
            'capital': capital,
            'return_pct': return_pct,
            'num_positions': num_positions,
            'num_trades': num_trades,
            'is_active': is_active,
            'recent_trades': [
                {
                    'symbol': t['symbol'],
                    'action': t['action'],
                    'shares': t['shares'],
                    'price': t['price'],
                    'executed_at': t['executed_at']
                }
                for t in trades[:3]
            ]
        })
    
    if overall_stats['total_capital'] > 0:
        overall_stats['avg_return'] = (total_return / overall_stats['total_capital']) * 100
    
    return jsonify({
        'overall': overall_stats,
        'strategies': strategy_data
    })

def main():
    """Start the dashboard server"""
    print("=" * 80)
    print("🚀 MULTI-STRATEGY DASHBOARD SERVER")
    print("=" * 80)
    print("\n📊 Dashboard URL: http://localhost:5000")
    print("🔄 Auto-refreshes every 30 seconds")
    print("\nPress Ctrl+C to stop\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    main()
