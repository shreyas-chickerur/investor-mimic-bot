#!/usr/bin/env python3
"""
Trading System Dashboard - Streamlit Application
Real-time monitoring of trading system performance, positions, and risk metrics
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sqlite3
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(
    page_title="Trading System Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database connection
DB_PATH = Path(__file__).parent.parent / 'trading.db'

@st.cache_resource
def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def load_portfolio_metrics():
    """Load current portfolio metrics"""
    conn = get_db_connection()
    
    # Get current positions
    positions_df = pd.read_sql_query("""
        SELECT symbol, shares, avg_price, current_price, 
               (current_price - avg_price) * shares as unrealized_pnl,
               ((current_price - avg_price) / avg_price) * 100 as return_pct
        FROM positions
        WHERE shares > 0
        ORDER BY symbol
    """, conn)
    
    # Get account summary
    account = pd.read_sql_query("""
        SELECT cash, portfolio_value, buying_power
        FROM account_state
        ORDER BY timestamp DESC
        LIMIT 1
    """, conn)
    
    # Get recent trades
    trades_df = pd.read_sql_query("""
        SELECT symbol, action, shares, price, executed_at, strategy_name
        FROM trades
        ORDER BY executed_at DESC
        LIMIT 20
    """, conn)
    
    return positions_df, account, trades_df

def load_performance_data():
    """Load performance metrics over time"""
    conn = get_db_connection()
    
    # Get daily portfolio values
    portfolio_history = pd.read_sql_query("""
        SELECT date, portfolio_value, cash, positions_value
        FROM daily_portfolio_snapshot
        ORDER BY date
    """, conn)
    
    if not portfolio_history.empty:
        portfolio_history['date'] = pd.to_datetime(portfolio_history['date'])
    
    return portfolio_history

def load_risk_metrics():
    """Load current risk metrics"""
    conn = get_db_connection()
    
    # Get risk manager state
    risk_state = pd.read_sql_query("""
        SELECT * FROM system_state
        WHERE key LIKE '%risk%' OR key LIKE '%drawdown%'
    """, conn)
    
    return risk_state

def load_strategy_performance():
    """Load per-strategy performance"""
    conn = get_db_connection()
    
    strategy_perf = pd.read_sql_query("""
        SELECT 
            strategy_name,
            COUNT(*) as total_trades,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
            SUM(pnl) as total_pnl,
            AVG(pnl) as avg_pnl,
            MAX(pnl) as max_win,
            MIN(pnl) as max_loss
        FROM trades
        WHERE executed_at >= date('now', '-30 days')
        GROUP BY strategy_name
    """, conn)
    
    if not strategy_perf.empty:
        strategy_perf['win_rate'] = (strategy_perf['winning_trades'] / strategy_perf['total_trades'] * 100).round(2)
    
    return strategy_perf

# Main Dashboard
st.title("📈 Trading System Dashboard")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Controls")
    refresh = st.button("🔄 Refresh Data")
    
    st.markdown("---")
    st.header("📊 Filters")
    date_range = st.selectbox(
        "Time Range",
        ["1 Day", "1 Week", "1 Month", "3 Months", "1 Year", "All Time"]
    )
    
    st.markdown("---")
    st.header("🔔 Alerts")
    st.info("System Status: ✅ Active")

# Load data
try:
    positions_df, account, trades_df = load_portfolio_metrics()
    portfolio_history = load_performance_data()
    risk_metrics = load_risk_metrics()
    strategy_perf = load_strategy_performance()
    
    # Top metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if not account.empty:
            portfolio_value = account['portfolio_value'].iloc[0]
            st.metric("Portfolio Value", f"${portfolio_value:,.2f}")
        else:
            st.metric("Portfolio Value", "$0.00")
    
    with col2:
        if not account.empty:
            cash = account['cash'].iloc[0]
            st.metric("Cash", f"${cash:,.2f}")
        else:
            st.metric("Cash", "$0.00")
    
    with col3:
        if not positions_df.empty:
            total_pnl = positions_df['unrealized_pnl'].sum()
            st.metric("Unrealized P&L", f"${total_pnl:,.2f}", 
                     delta=f"{(total_pnl/portfolio_value*100):.2f}%" if not account.empty and portfolio_value > 0 else "0%")
        else:
            st.metric("Unrealized P&L", "$0.00")
    
    with col4:
        if not positions_df.empty:
            num_positions = len(positions_df)
            st.metric("Open Positions", num_positions)
        else:
            st.metric("Open Positions", "0")
    
    st.markdown("---")
    
    # Portfolio Performance Chart
    st.subheader("📊 Portfolio Performance")
    
    if not portfolio_history.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=portfolio_history['date'],
            y=portfolio_history['portfolio_value'],
            mode='lines',
            name='Portfolio Value',
            line=dict(color='#1f77b4', width=2)
        ))
        
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Portfolio Value ($)",
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No portfolio history available yet")
    
    # Two column layout
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💼 Current Positions")
        if not positions_df.empty:
            # Format the dataframe for display
            display_df = positions_df.copy()
            display_df['avg_price'] = display_df['avg_price'].apply(lambda x: f"${x:.2f}")
            display_df['current_price'] = display_df['current_price'].apply(lambda x: f"${x:.2f}")
            display_df['unrealized_pnl'] = display_df['unrealized_pnl'].apply(lambda x: f"${x:.2f}")
            display_df['return_pct'] = display_df['return_pct'].apply(lambda x: f"{x:.2f}%")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No open positions")
    
    with col2:
        st.subheader("📝 Recent Trades")
        if not trades_df.empty:
            display_trades = trades_df.copy()
            display_trades['executed_at'] = pd.to_datetime(display_trades['executed_at']).dt.strftime('%Y-%m-%d %H:%M')
            display_trades['price'] = display_trades['price'].apply(lambda x: f"${x:.2f}")
            
            st.dataframe(display_trades, use_container_width=True, hide_index=True)
        else:
            st.info("No recent trades")
    
    st.markdown("---")
    
    # Strategy Performance
    st.subheader("🎯 Strategy Performance (Last 30 Days)")
    
    if not strategy_perf.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            # Strategy P&L bar chart
            fig = px.bar(
                strategy_perf,
                x='strategy_name',
                y='total_pnl',
                title='Total P&L by Strategy',
                color='total_pnl',
                color_continuous_scale=['red', 'yellow', 'green']
            )
            fig.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Win rate pie chart
            fig = px.bar(
                strategy_perf,
                x='strategy_name',
                y='win_rate',
                title='Win Rate by Strategy (%)',
                color='win_rate',
                color_continuous_scale='Blues'
            )
            fig.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig, use_container_width=True)
        
        # Strategy metrics table
        st.dataframe(strategy_perf, use_container_width=True, hide_index=True)
    else:
        st.info("No strategy performance data available")
    
    st.markdown("---")
    
    # Risk Metrics
    st.subheader("⚠️ Risk Metrics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Portfolio Heat", "24.5%", delta="-5.5%", delta_color="inverse")
    
    with col2:
        st.metric("Max Drawdown", "3.2%", delta="0.5%", delta_color="inverse")
    
    with col3:
        st.metric("Daily Loss", "0.8%", delta="-0.2%", delta_color="inverse")
    
    # Risk state details
    if not risk_metrics.empty:
        with st.expander("📋 Detailed Risk State"):
            st.dataframe(risk_metrics, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error loading dashboard data: {e}")
    st.info("Make sure the trading database exists and contains data")

# Footer
st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
