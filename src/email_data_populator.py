#!/usr/bin/env python3
"""
Email Data Populator
Dynamically populates email data from Alpaca API and database
"""
from typing import List, Dict
from database_schema import TradingDatabase
from news_causal_chains import _generate_news_based_chain


def populate_approval_email_data(
    proposed_trades: List[Dict],
    use_alpaca: bool = True
) -> Dict:
    """
    Populate all email data from Alpaca API and database
    
    Args:
        proposed_trades: List of proposed trades with symbol, shares, price, value
        use_alpaca: If True, fetch real-time data from Alpaca API (default: True)
    
    Returns:
        Dict with all data needed for email, populated in real-time
    """
    
    if use_alpaca:
        # Use Alpaca API for real-time data
        try:
            from alpaca_data_fetcher import fetch_alpaca_data_for_email
            print("🔄 Fetching real-time data from Alpaca API...")
            return fetch_alpaca_data_for_email(proposed_trades)
        except Exception as e:
            print(f"⚠️ Alpaca fetch failed, falling back to database: {e}")
            use_alpaca = False
    
    # Fallback to database if Alpaca not available
    db = TradingDatabase()
    
    # Get market data from database
    market_data = db.get_latest_market_data()
    
    # If no market data in DB, use sample data
    if not market_data:
        market_data = {
            "S&P 500": {"value": "4,783.45", "change": 23.45, "change_pct": 0.49},
            "NASDAQ": {"value": "15,095.14", "change": -15.23, "change_pct": -0.10},
            "DOW": {"value": "37,545.33", "change": 45.67, "change_pct": 0.12}
        }
    
    # Get current holdings from database
    current_holdings = db.get_current_holdings()
    
    # Get news about holdings from database
    holdings_news = db.get_holdings_news(limit=5)
    
    # Get or generate causal chains for each proposed trade
    for trade in proposed_trades:
        symbol = trade['symbol']
        
        # Try to get from database first
        causal_chain = db.get_causal_chain(symbol)
        
        # If not in database, generate and save
        if not causal_chain:
            causal_chain = _generate_news_based_chain(symbol)
            db.save_causal_chain(symbol, causal_chain)
        
        trade['causal_chain'] = causal_chain
    
    # Estimate portfolio value and cash from holdings if not provided
    portfolio_value = sum(h['shares'] * h.get('current_price', h['avg_price']) for h in current_holdings)
    cash = 10000.0  # Default, should be fetched from account
    
    return {
        'trades': proposed_trades,
        'portfolio_value': portfolio_value,
        'cash': cash,
        'market_data': market_data,
        'current_holdings': current_holdings,
        'holdings_news': holdings_news
    }


def save_market_data_to_db(market_data: Dict):
    """Save market data to database"""
    db = TradingDatabase()
    db.save_market_data(market_data)


def save_stock_news_to_db(symbol: str, title: str, summary: str, sentiment: str):
    """Save stock news to database"""
    db = TradingDatabase()
    db.save_stock_news(symbol, title, summary, sentiment)


def update_holdings_in_db(holdings: List[Dict]):
    """Update current holdings in database"""
    db = TradingDatabase()
    for holding in holdings:
        db.update_holding(
            symbol=holding['symbol'],
            shares=holding['shares'],
            avg_price=holding['avg_price'],
            current_price=holding.get('current_price', holding['avg_price'])
        )
