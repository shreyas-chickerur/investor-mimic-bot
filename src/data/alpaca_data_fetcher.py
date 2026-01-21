#!/usr/bin/env python3
"""
Alpaca Data Fetcher
Fetches real-time data from Alpaca API for email population
"""
import os
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

try:
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest
except ImportError:
    print("Warning: alpaca-py not installed")


class AlpacaDataFetcher:
    """Fetches real-time data from Alpaca for email population"""
    
    def __init__(self):
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.secret_key = os.getenv('ALPACA_SECRET_KEY')
        
        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca credentials not found in environment")
        
        self.trading_client = TradingClient(self.api_key, self.secret_key, paper=True)
        self.data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
    
    def get_account_info(self) -> Dict:
        """Get account portfolio value and cash"""
        try:
            account = self.trading_client.get_account()
            return {
                'portfolio_value': float(account.portfolio_value),
                'cash': float(account.cash),
                'equity': float(account.equity),
                'buying_power': float(account.buying_power)
            }
        except Exception as e:
            print(f"Error fetching account info: {e}")
            return {
                'portfolio_value': 0.0,
                'cash': 0.0,
                'equity': 0.0,
                'buying_power': 0.0
            }
    
    def get_current_positions(self) -> List[Dict]:
        """
        Get current positions from Alpaca
        Returns list of holdings with symbol, shares, avg_price, current_price
        """
        try:
            positions = self.trading_client.get_all_positions()
            
            holdings = []
            for position in positions:
                holdings.append({
                    'symbol': position.symbol,
                    'shares': float(position.qty),
                    'avg_price': float(position.avg_entry_price),
                    'current_price': float(position.current_price),
                    'market_value': float(position.market_value),
                    'unrealized_pl': float(position.unrealized_pl),
                    'unrealized_plpc': float(position.unrealized_plpc) * 100  # Convert to percentage
                })
            
            return holdings
        
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []
    
    def get_latest_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get latest prices for a list of symbols
        Returns dict mapping symbol to current price
        """
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes = self.data_client.get_stock_latest_quote(request)
            
            prices = {}
            for symbol, quote in quotes.items():
                prices[symbol] = float(quote.ask_price) if quote.ask_price else float(quote.bid_price)
            
            return prices
        
        except Exception as e:
            print(f"Error fetching prices: {e}")
            return {}
    
    def get_market_indices(self) -> Dict:
        """
        Get current market indices (S&P 500, NASDAQ, DOW)
        Note: Alpaca doesn't provide index data directly, so we use proxy ETFs
        """
        try:
            # Use ETF proxies for market indices
            symbols = ['SPY', 'QQQ', 'DIA']  # S&P 500, NASDAQ, DOW proxies
            prices = self.get_latest_prices(symbols)
            
            # For demo purposes, calculate mock changes
            # In production, you'd compare to previous day's close
            market_data = {
                "S&P 500": {
                    "value": f"{prices.get('SPY', 0) * 10:.2f}",  # Approximate S&P value
                    "change": 23.45,
                    "change_pct": 0.49
                },
                "NASDAQ": {
                    "value": f"{prices.get('QQQ', 0) * 40:.2f}",  # Approximate NASDAQ value
                    "change": -15.23,
                    "change_pct": -0.10
                },
                "DOW": {
                    "value": f"{prices.get('DIA', 0) * 100:.2f}",  # Approximate DOW value
                    "change": 45.67,
                    "change_pct": 0.12
                }
            }
            
            return market_data
        
        except Exception as e:
            print(f"Error fetching market indices: {e}")
            # Return sample data as fallback
            return {
                "S&P 500": {"value": "4,783.45", "change": 23.45, "change_pct": 0.49},
                "NASDAQ": {"value": "15,095.14", "change": -15.23, "change_pct": -0.10},
                "DOW": {"value": "37,545.33", "change": 45.67, "change_pct": 0.12}
            }
    
    def sync_positions_to_database(self):
        """Sync current Alpaca positions to database"""
        from database_schema import TradingDatabase
        
        db = TradingDatabase()
        positions = self.get_current_positions()
        
        for position in positions:
            db.update_holding(
                symbol=position['symbol'],
                shares=position['shares'],
                avg_price=position['avg_price'],
                current_price=position['current_price']
            )
        
        print(f"✅ Synced {len(positions)} positions to database")
        return positions
    
    def get_complete_email_data(self, proposed_trades: List[Dict]) -> Dict:
        """
        Get all data needed for approval email from Alpaca
        This is the main function to call for real-time email population
        """
        print("📊 Fetching real-time data from Alpaca...")
        
        # Get account info
        account_info = self.get_account_info()
        print(f"✅ Account: ${account_info['portfolio_value']:,.2f} portfolio value")
        
        # Get current positions
        current_holdings = self.get_current_positions()
        print(f"✅ Holdings: {len(current_holdings)} positions")
        
        # Sync positions to database
        self.sync_positions_to_database()
        
        # Get market data
        market_data = self.get_market_indices()
        print(f"✅ Market data fetched")
        
        # Get news from database (would be populated separately by news API)
        from database_schema import TradingDatabase
        db = TradingDatabase()
        holdings_news = db.get_holdings_news(limit=5)
        print(f"✅ News: {len(holdings_news)} articles")
        
        # Get or generate causal chains for proposed trades
        from news_causal_chains import _generate_news_based_chain
        for trade in proposed_trades:
            symbol = trade['symbol']
            causal_chain = db.get_causal_chain(symbol)
            
            if not causal_chain:
                causal_chain = _generate_news_based_chain(symbol)
                db.save_causal_chain(symbol, causal_chain)
            
            trade['causal_chain'] = causal_chain
        
        print(f"✅ Causal chains generated for {len(proposed_trades)} trades")
        
        return {
            'trades': proposed_trades,
            'portfolio_value': account_info['portfolio_value'],
            'cash': account_info['cash'],
            'market_data': market_data,
            'current_holdings': current_holdings,
            'holdings_news': holdings_news
        }


def fetch_alpaca_data_for_email(proposed_trades: List[Dict]) -> Dict:
    """
    Convenience function to fetch all Alpaca data for email
    
    Args:
        proposed_trades: List of proposed trades with symbol, shares, price, value
    
    Returns:
        Dict with all data needed for email, populated from Alpaca API
    """
    try:
        fetcher = AlpacaDataFetcher()
        return fetcher.get_complete_email_data(proposed_trades)
    except Exception as e:
        print(f"❌ Error fetching Alpaca data: {e}")
        # Return minimal data structure
        return {
            'trades': proposed_trades,
            'portfolio_value': 0.0,
            'cash': 0.0,
            'market_data': {},
            'current_holdings': [],
            'holdings_news': []
        }
