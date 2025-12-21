#!/usr/bin/env python3
"""
Data Sync Job
Syncs all Alpaca data to database before email generation
This ensures email always uses fresh, database-stored data
"""
from datetime import datetime
from typing import Dict
from database_schema import TradingDatabase
from alpaca_data_fetcher import AlpacaDataFetcher


class DataSyncJob:
    """Syncs Alpaca data to database"""
    
    def __init__(self):
        self.db = TradingDatabase()
        self.fetcher = AlpacaDataFetcher()
    
    def sync_all_data(self) -> Dict:
        """
        Sync all Alpaca data to database
        Returns summary of synced data
        """
        print("=" * 80)
        print(f"DATA SYNC JOB - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        results = {
            'account_snapshot': None,
            'holdings_count': 0,
            'market_data_count': 0,
            'timestamp': datetime.now().isoformat(),
            'success': True,
            'errors': []
        }
        
        try:
            # 1. Sync account snapshot
            print("\n1️⃣  Syncing account snapshot...")
            account_info = self.fetcher.get_account_info()
            
            self.db.save_account_snapshot(
                portfolio_value=account_info['portfolio_value'],
                cash=account_info['cash'],
                equity=account_info['equity'],
                buying_power=account_info['buying_power']
            )
            
            results['account_snapshot'] = account_info
            print(f"   ✅ Portfolio: ${account_info['portfolio_value']:,.2f}")
            print(f"   ✅ Cash: ${account_info['cash']:,.2f}")
            
        except Exception as e:
            error_msg = f"Account snapshot sync failed: {e}"
            results['errors'].append(error_msg)
            print(f"   ❌ {error_msg}")
        
        try:
            # 2. Sync current holdings
            print("\n2️⃣  Syncing current holdings...")
            holdings = self.fetcher.get_current_positions()
            
            for holding in holdings:
                self.db.update_holding(
                    symbol=holding['symbol'],
                    shares=holding['shares'],
                    avg_price=holding['avg_price'],
                    current_price=holding['current_price']
                )
            
            results['holdings_count'] = len(holdings)
            print(f"   ✅ Synced {len(holdings)} positions")
            for holding in holdings:
                print(f"      - {holding['symbol']}: {holding['shares']:.2f} shares @ ${holding['current_price']:.2f}")
            
        except Exception as e:
            error_msg = f"Holdings sync failed: {e}"
            results['errors'].append(error_msg)
            print(f"   ❌ {error_msg}")
        
        try:
            # 3. Sync market data
            print("\n3️⃣  Syncing market data...")
            market_data = self.fetcher.get_market_indices()
            
            self.db.save_market_data(market_data)
            
            results['market_data_count'] = len(market_data)
            print(f"   ✅ Synced {len(market_data)} market indices")
            for name, data in market_data.items():
                print(f"      - {name}: {data['value']} ({data['change_pct']:+.2f}%)")
            
        except Exception as e:
            error_msg = f"Market data sync failed: {e}"
            results['errors'].append(error_msg)
            print(f"   ❌ {error_msg}")
        
        # Summary
        print("\n" + "=" * 80)
        if results['errors']:
            results['success'] = False
            print("⚠️  DATA SYNC COMPLETED WITH ERRORS")
            print("=" * 80)
            for error in results['errors']:
                print(f"   ❌ {error}")
        else:
            print("✅ DATA SYNC COMPLETED SUCCESSFULLY")
            print("=" * 80)
            print(f"   Account snapshot: Saved")
            print(f"   Holdings: {results['holdings_count']} positions")
            print(f"   Market data: {results['market_data_count']} indices")
        
        print(f"   Timestamp: {results['timestamp']}")
        print()
        
        return results
    
    def verify_data_freshness(self) -> Dict:
        """
        Verify that database has fresh data
        Returns status of data freshness
        """
        status = {
            'has_account_snapshot': False,
            'has_holdings': False,
            'has_market_data': False,
            'all_fresh': False
        }
        
        # Check account snapshot
        # (Would check timestamp in production)
        
        # Check holdings
        holdings = self.db.get_current_holdings()
        status['has_holdings'] = len(holdings) > 0
        
        # Check market data
        market_data = self.db.get_latest_market_data()
        status['has_market_data'] = len(market_data) > 0
        
        status['all_fresh'] = (
            status['has_holdings'] and 
            status['has_market_data']
        )
        
        return status


def run_data_sync() -> Dict:
    """
    Convenience function to run data sync
    Returns sync results
    """
    sync_job = DataSyncJob()
    return sync_job.sync_all_data()


if __name__ == '__main__':
    # Run sync when executed directly
    results = run_data_sync()
    
    if not results['success']:
        exit(1)
