#!/usr/bin/env python3
"""
Strategy Dashboard
Admin interface to compare and monitor all strategies
"""
from flask import Flask, render_template_string, jsonify
from strategy_database import StrategyDatabase
from datetime import datetime

app = Flask(__name__)
db = StrategyDatabase()

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Strategy Performance Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            background: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .header h1 {
            color: #2d3748;
            font-size: 32px;
            margin-bottom: 10px;
        }
        .header p {
            color: #718096;
            font-size: 16px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .stat-label {
            color: #718096;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .stat-value {
            color: #2d3748;
            font-size: 28px;
            font-weight: 700;
        }
        .stat-change {
            font-size: 14px;
            margin-top: 4px;
        }
        .positive { color: #48bb78; }
        .negative { color: #f56565; }
        .comparison-table {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .comparison-table h2 {
            color: #2d3748;
            margin-bottom: 20px;
            font-size: 24px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th {
            background: #f7fafc;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #4a5568;
            font-size: 13px;
            text-transform: uppercase;
        }
        td {
            padding: 16px 12px;
            border-bottom: 1px solid #e2e8f0;
            color: #2d3748;
        }
        tr:hover {
            background: #f7fafc;
        }
        .rank {
            display: inline-block;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            text-align: center;
            line-height: 32px;
            font-weight: 700;
            color: white;
        }
        .rank-1 { background: #ffd700; }
        .rank-2 { background: #c0c0c0; }
        .rank-3 { background: #cd7f32; }
        .rank-other { background: #cbd5e0; }
        .chart-container {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .refresh-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            font-size: 14px;
        }
        .refresh-btn:hover {
            background: #5a67d8;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Multi-Strategy Performance Dashboard</h1>
            <p>Real-time comparison of 5 concurrent trading strategies</p>
            <button class="refresh-btn" onclick="location.reload()">🔄 Refresh Data</button>
        </div>

        <div class="stats-grid" id="statsGrid">
            <!-- Stats will be populated by JavaScript -->
        </div>

        <div class="comparison-table">
            <h2>Strategy Rankings</h2>
            <table id="rankingsTable">
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>Strategy</th>
                        <th>Portfolio Value</th>
                        <th>Return %</th>
                        <th>Positions</th>
                        <th>Total Trades</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="rankingsBody">
                    <!-- Rankings will be populated by JavaScript -->
                </tbody>
            </table>
        </div>

        <div class="chart-container">
            <h2 style="margin-bottom: 20px; color: #2d3748;">Performance Comparison</h2>
            <canvas id="performanceChart"></canvas>
        </div>
    </div>

    <script>
        async function loadData() {
            const response = await fetch('/api/rankings');
            const data = await response.json();
            
            // Update stats
            const statsGrid = document.getElementById('statsGrid');
            statsGrid.innerHTML = `
                <div class="stat-card">
                    <div class="stat-label">Best Performer</div>
                    <div class="stat-value">${data.rankings[0]?.name || 'N/A'}</div>
                    <div class="stat-change positive">+${data.rankings[0]?.return_pct?.toFixed(2) || '0.00'}%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Capital</div>
                    <div class="stat-value">$${(data.rankings.reduce((sum, s) => sum + (s.portfolio_value || 0), 0)).toLocaleString('en-US', {maximumFractionDigits: 0})}</div>
                    <div class="stat-change">Across 5 strategies</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Trades</div>
                    <div class="stat-value">${data.rankings.reduce((sum, s) => sum + (s.total_trades || 0), 0)}</div>
                    <div class="stat-change">All strategies combined</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Active Positions</div>
                    <div class="stat-value">${data.rankings.reduce((sum, s) => sum + (s.num_positions || 0), 0)}</div>
                    <div class="stat-change">Currently held</div>
                </div>
            `;
            
            // Update rankings table
            const rankingsBody = document.getElementById('rankingsBody');
            rankingsBody.innerHTML = data.rankings.map((strategy, index) => {
                const rankClass = index === 0 ? 'rank-1' : index === 1 ? 'rank-2' : index === 2 ? 'rank-3' : 'rank-other';
                const returnClass = strategy.return_pct >= 0 ? 'positive' : 'negative';
                
                return `
                    <tr>
                        <td><span class="rank ${rankClass}">${index + 1}</span></td>
                        <td><strong>${strategy.name}</strong></td>
                        <td>$${strategy.portfolio_value?.toLocaleString('en-US', {maximumFractionDigits: 0}) || '0'}</td>
                        <td class="${returnClass}">${strategy.return_pct >= 0 ? '+' : ''}${strategy.return_pct?.toFixed(2) || '0.00'}%</td>
                        <td>${strategy.num_positions || 0}</td>
                        <td>${strategy.total_trades || 0}</td>
                        <td><span style="color: #48bb78;">● Active</span></td>
                    </tr>
                `;
            }).join('');
            
            // Update chart
            const ctx = document.getElementById('performanceChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.rankings.map(s => s.name),
                    datasets: [{
                        label: 'Return %',
                        data: data.rankings.map(s => s.return_pct || 0),
                        backgroundColor: data.rankings.map((s, i) => 
                            i === 0 ? '#ffd700' : i === 1 ? '#c0c0c0' : i === 2 ? '#cd7f32' : '#cbd5e0'
                        ),
                        borderRadius: 8,
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Return %'
                            }
                        }
                    }
                }
            });
        }
        
        loadData();
        
        // Auto-refresh every 60 seconds
        setInterval(loadData, 60000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/rankings')
def get_rankings():
    """API endpoint for strategy rankings"""
    rankings = db.get_comparison_data()
    return jsonify({'rankings': rankings})

@app.route('/api/strategy/<int:strategy_id>')
def get_strategy_detail(strategy_id):
    """API endpoint for strategy details"""
    performance = db.get_strategy_performance(strategy_id, days=30)
    trades = db.get_strategy_trades(strategy_id, limit=50)
    return jsonify({
        'performance': performance,
        'trades': trades
    })

def run_dashboard(host='0.0.0.0', port=5000):
    """Run the dashboard server"""
    print("="*80)
    print("STRATEGY DASHBOARD")
    print("="*80)
    print(f"\n🚀 Starting dashboard on http://{host}:{port}")
    print(f"📊 Open http://localhost:{port} in your browser")
    print("\n⚠️  Keep this server running to view the dashboard")
    print("   Press Ctrl+C to stop\n")
    
    app.run(host=host, port=port, debug=False)

if __name__ == '__main__':
    run_dashboard()
