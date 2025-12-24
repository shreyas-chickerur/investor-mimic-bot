#!/usr/bin/env python3
"""
Phase 5 Live Monitoring Dashboard

Real-time strategy performance monitoring with historical analysis
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from flask import Flask, render_template, jsonify
import sqlite3
import json
from datetime import datetime, timedelta
import pandas as pd

app = Flask(__name__)

DB_PATH = Path(__file__).parent.parent / 'trading.db'
ARTIFACTS_PATH = Path(__file__).parent.parent / 'artifacts' / 'json'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_strategy_performance():
    """Get performance metrics for all strategies"""
    conn = get_db_connection()
    
    # Get all strategies
    strategies = conn.execute('''
        SELECT id, name, description, initial_capital
        FROM strategies
        ORDER BY id
    ''').fetchall()
    
    performance = []
    for strategy in strategies:
        # Get trades for this strategy
        trades = conn.execute('''
            SELECT * FROM trades
            WHERE strategy_id = ?
            ORDER BY executed_at DESC
        ''', (strategy['id'],)).fetchall()
        
        # Calculate metrics
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t['pnl'] and t['pnl'] > 0)
        losing_trades = sum(1 for t in trades if t['pnl'] and t['pnl'] < 0)
        total_pnl = sum(t['pnl'] for t in trades if t['pnl'])
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Get recent trades (last 7 days)
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        recent_trades = [t for t in trades if t['executed_at'] >= seven_days_ago]
        recent_pnl = sum(t['pnl'] for t in recent_trades if t['pnl'])
        
        performance.append({
            'name': strategy['name'],
            'total_trades': total_trades,
            'win_rate': round(win_rate, 1),
            'total_pnl': round(total_pnl, 2),
            'recent_pnl_7d': round(recent_pnl, 2),
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'initial_capital': strategy['initial_capital']
        })
    
    conn.close()
    return performance

def get_daily_artifacts():
    """Get all daily artifacts"""
    artifacts = []
    
    if not ARTIFACTS_PATH.exists():
        return artifacts
    
    for artifact_file in sorted(ARTIFACTS_PATH.glob('*.json'), reverse=True):
        try:
            with open(artifact_file) as f:
                data = json.load(f)
            
            artifacts.append({
                'date': data.get('date'),
                'reconciliation': data.get('system_health', {}).get('reconciliation_status', 'UNKNOWN'),
                'trades': len(data.get('trades', [])),
                'signals': sum(len(s.get('signals', [])) for s in data.get('signals', {}).values()),
                'regime': data.get('regime', {}).get('type', 'unknown')
            })
        except Exception as e:
            print(f"Error loading {artifact_file}: {e}")
    
    return artifacts[:30]  # Last 30 days

def get_performance_chart_data():
    """Get data for performance charts"""
    conn = get_db_connection()
    
    # Get daily P&L by strategy
    strategies = conn.execute('SELECT id, name FROM strategies').fetchall()
    
    chart_data = {}
    for strategy in strategies:
        trades = conn.execute('''
            SELECT DATE(executed_at) as date, SUM(pnl) as daily_pnl
            FROM trades
            WHERE strategy_id = ? AND pnl IS NOT NULL
            GROUP BY DATE(executed_at)
            ORDER BY date
        ''', (strategy['id'],)).fetchall()
        
        chart_data[strategy['name']] = {
            'dates': [t['date'] for t in trades],
            'pnl': [float(t['daily_pnl']) for t in trades]
        }
    
    conn.close()
    return chart_data

@app.route('/')
def index():
    """Main dashboard page"""
    performance = get_strategy_performance()
    artifacts = get_daily_artifacts()
    
    return render_template('dashboard.html', 
                         performance=performance,
                         artifacts=artifacts,
                         last_update=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/api/performance')
def api_performance():
    """API endpoint for performance data"""
    return jsonify(get_strategy_performance())

@app.route('/api/chart-data')
def api_chart_data():
    """API endpoint for chart data"""
    return jsonify(get_performance_chart_data())

@app.route('/api/artifacts')
def api_artifacts():
    """API endpoint for artifacts"""
    return jsonify(get_daily_artifacts())

if __name__ == '__main__':
    print("="*80)
    print("PHASE 5 MONITORING DASHBOARD")
    print("="*80)
    print(f"\nDatabase: {DB_PATH}")
    print(f"Artifacts: {ARTIFACTS_PATH}")
    print("\nStarting dashboard at http://localhost:8080")
    print("Press Ctrl+C to stop\n")
    
    app.run(debug=False, host='0.0.0.0', port=8080)
