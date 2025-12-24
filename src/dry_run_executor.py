#!/usr/bin/env python3
"""
Dry Run Executor

Phase 5: Executes full trading pipeline WITHOUT placing broker orders.
- Generates artifacts
- Performs reconciliation reads
- Logs terminal states
- Simulates all execution logic

Use for testing before live paper trading.
"""
import os
import logging
from typing import Dict, List, Optional, Tuple, Tuple
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class DryRunExecutor:
    """
    Dry run mode executor
    
    Runs full pipeline but does NOT place broker orders.
    Still generates artifacts, logs terminal states, and performs reconciliation.
    """
    
    def __init__(self, broker_reconciler=None, artifact_writer=None, signal_tracer=None):
        """
        Initialize dry run executor
        
        Args:
            broker_reconciler: BrokerReconciler instance (read-only in dry run)
            artifact_writer: DailyArtifactWriter instance
            signal_tracer: SignalFlowTracer instance
        """
        self.broker_reconciler = broker_reconciler
        self.artifact_writer = artifact_writer
        self.signal_tracer = signal_tracer
        self.dry_run_trades = []  # Simulated trades
        self.dry_run_positions = {}  # Simulated positions
        self.dry_run_cash = float(os.getenv('INITIAL_CAPITAL', '100000'))
        
        logger.info("="*80)
        logger.info("🔵 DRY RUN MODE ENABLED")
        logger.info("="*80)
        logger.info("NO BROKER ORDERS WILL BE PLACED")
        logger.info("All execution is simulated")
        logger.info("Artifacts and logs will be generated")
        logger.info("="*80)
    
    def execute_signal(self, signal: Dict, shares: int, execution_price: float) -> Dict:
        """
        Simulate trade execution (does NOT place broker order)
        
        Args:
            signal: Signal dict
            shares: Number of shares
            execution_price: Simulated execution price
            
        Returns:
            Simulated trade result
        """
        symbol = signal['symbol']
        action = signal['action']
        
        # Simulate execution costs
        total_cost = shares * execution_price
        commission = 0.0  # Alpaca is commission-free
        slippage = execution_price * 0.001  # 0.1% slippage simulation
        total_cost_with_slippage = total_cost + (shares * slippage)
        
        logger.info(f"🔵 DRY RUN: {action} {shares} {symbol} @ ${execution_price:.2f}")
        logger.info(f"   Simulated cost: ${total_cost_with_slippage:,.2f} (includes slippage)")
        logger.info(f"   ⚠️  NO BROKER ORDER PLACED")
        
        # Update simulated state
        if action == 'BUY':
            if symbol in self.dry_run_positions:
                # Average up
                existing = self.dry_run_positions[symbol]
                total_shares = existing['shares'] + shares
                total_cost_basis = (existing['shares'] * existing['avg_price']) + total_cost_with_slippage
                avg_price = total_cost_basis / total_shares
                
                self.dry_run_positions[symbol] = {
                    'shares': total_shares,
                    'avg_price': avg_price,
                    'entry_date': existing['entry_date']
                }
            else:
                # New position
                self.dry_run_positions[symbol] = {
                    'shares': shares,
                    'avg_price': execution_price,
                    'entry_date': datetime.now().strftime('%Y-%m-%d')
                }
            
            self.dry_run_cash -= total_cost_with_slippage
        
        elif action == 'SELL':
            if symbol in self.dry_run_positions:
                position = self.dry_run_positions[symbol]
                if shares >= position['shares']:
                    # Close position
                    pnl = (execution_price - position['avg_price']) * position['shares']
                    self.dry_run_cash += (position['shares'] * execution_price)
                    del self.dry_run_positions[symbol]
                    logger.info(f"   Simulated P&L: ${pnl:,.2f}")
                else:
                    # Partial close
                    pnl = (execution_price - position['avg_price']) * shares
                    position['shares'] -= shares
                    self.dry_run_cash += (shares * execution_price)
                    logger.info(f"   Simulated P&L: ${pnl:,.2f}")
        
        # Record simulated trade
        trade = {
            'symbol': symbol,
            'action': action,
            'shares': shares,
            'price': execution_price,
            'total_cost': total_cost_with_slippage,
            'timestamp': datetime.now().isoformat(),
            'dry_run': True
        }
        self.dry_run_trades.append(trade)
        
        return trade
    
    def get_simulated_state(self) -> Dict:
        """
        Get current simulated portfolio state
        
        Returns:
            Dict with positions, cash, portfolio value
        """
        # Calculate portfolio value (need current prices - use entry prices for now)
        portfolio_value = self.dry_run_cash
        for symbol, pos in self.dry_run_positions.items():
            portfolio_value += pos['shares'] * pos['avg_price']
        
        return {
            'positions': self.dry_run_positions.copy(),
            'cash': self.dry_run_cash,
            'portfolio_value': portfolio_value,
            'open_positions': len(self.dry_run_positions),
            'trades_today': len([t for t in self.dry_run_trades 
                                if t['timestamp'].startswith(datetime.now().strftime('%Y-%m-%d'))])
        }
    
    def reconcile_dry_run(self) -> Tuple[bool, List[str]]:
        """
        Perform read-only reconciliation check
        
        In dry run, we only READ broker state, we don't compare to local
        (since local is simulated).
        
        Returns:
            (success: bool, notes: List[str])
        """
        if not self.broker_reconciler:
            logger.warning("No broker reconciler configured for dry run")
            return True, ["Broker reconciliation skipped - no reconciler"]
        
        logger.info("🔵 DRY RUN: Reading broker state (read-only)")
        
        try:
            broker_state = self.broker_reconciler.get_broker_state()
            
            logger.info(f"   Broker positions: {len(broker_state.get('positions', {}))}")
            logger.info(f"   Broker cash: ${broker_state.get('cash', 0):,.2f}")
            logger.info(f"   Broker portfolio value: ${broker_state.get('portfolio_value', 0):,.2f}")
            
            logger.info(f"   Simulated positions: {len(self.dry_run_positions)}")
            logger.info(f"   Simulated cash: ${self.dry_run_cash:,.2f}")
            
            return True, ["Broker state read successfully (read-only)"]
        
        except Exception as e:
            logger.error(f"Error reading broker state: {e}")
            return False, [f"Error reading broker state: {str(e)}"]
    
    def generate_dry_run_artifact(self, date: str, regime_data: Dict, 
                                  signals_data: Dict, risk_data: Dict) -> Tuple[str, str]:
        """
        Generate daily artifact for dry run
        
        Args:
            date: Trading date
            regime_data: Regime information
            signals_data: Signals generated/rejected/executed
            risk_data: Risk metrics
            
        Returns:
            (json_path, markdown_path)
        """
        if not self.artifact_writer:
            logger.warning("No artifact writer configured")
            return None, None
        
        logger.info(f"🔵 DRY RUN: Generating artifact for {date}")
        
        # Get simulated state
        state = self.get_simulated_state()
        
        # Prepare positions for artifact
        positions_list = []
        for symbol, pos in state['positions'].items():
            positions_list.append({
                'symbol': symbol,
                'qty': pos['shares'],
                'avg_price': pos['avg_price'],
                'market_value': pos['shares'] * pos['avg_price'],
                'unrealized_pl': 0.0,  # Would need current prices
                'exposure_pct': (pos['shares'] * pos['avg_price']) / state['portfolio_value'] * 100
            })
        
        # Create artifact data
        from daily_artifact_writer import create_artifact_data
        
        artifact_data = create_artifact_data(
            vix=regime_data.get('vix', 0),
            regime_classification=regime_data.get('classification', 'UNKNOWN'),
            raw_signals=signals_data.get('raw', {}),
            rejected_signals=signals_data.get('rejected', []),
            executed_signals=signals_data.get('executed', []),
            placed_orders=[],  # No real orders in dry run
            filled_orders=self.dry_run_trades,
            rejected_orders=[],
            portfolio_heat=risk_data.get('portfolio_heat', 0),
            daily_pnl=risk_data.get('daily_pnl', 0),
            cumulative_pnl=risk_data.get('cumulative_pnl', 0),
            drawdown=risk_data.get('drawdown', 0),
            max_drawdown=risk_data.get('max_drawdown', 0),
            circuit_breaker_state=risk_data.get('circuit_breaker_state', 'INACTIVE'),
            open_positions=positions_list,
            runtime_seconds=risk_data.get('runtime_seconds', 0),
            data_freshness="DRY_RUN",
            errors=risk_data.get('errors', []),
            warnings=["DRY RUN MODE - No broker orders placed"],
            reconciliation_status="DRY_RUN_READ_ONLY"
        )
        
        json_path, md_path = self.artifact_writer.write_daily_artifact(date, artifact_data)
        
        logger.info(f"✅ Dry run artifact written: {json_path}")
        return json_path, md_path
    
    def print_dry_run_summary(self):
        """Print summary of dry run execution"""
        state = self.get_simulated_state()
        
        logger.info("\n" + "="*80)
        logger.info("🔵 DRY RUN SUMMARY")
        logger.info("="*80)
        logger.info(f"Total Simulated Trades: {len(self.dry_run_trades)}")
        logger.info(f"Open Positions: {state['open_positions']}")
        logger.info(f"Simulated Cash: ${state['cash']:,.2f}")
        logger.info(f"Simulated Portfolio Value: ${state['portfolio_value']:,.2f}")
        logger.info("")
        logger.info("⚠️  REMINDER: NO BROKER ORDERS WERE PLACED")
        logger.info("This was a dry run simulation only")
        logger.info("="*80)


if __name__ == "__main__":
    # Test dry run executor
    logging.basicConfig(level=logging.INFO)
    
    from broker_reconciler import BrokerReconciler
    from daily_artifact_writer import DailyArtifactWriter
    from signal_flow_tracer import SignalFlowTracer
    
    # Initialize components
    reconciler = BrokerReconciler()
    writer = DailyArtifactWriter()
    tracer = SignalFlowTracer()
    
    # Create dry run executor
    dry_run = DryRunExecutor(
        broker_reconciler=reconciler,
        artifact_writer=writer,
        signal_tracer=tracer
    )
    
    # Simulate some trades
    signal1 = {'symbol': 'AAPL', 'action': 'BUY', 'price': 150.00}
    signal2 = {'symbol': 'MSFT', 'action': 'BUY', 'price': 300.00}
    
    dry_run.execute_signal(signal1, 10, 150.05)
    dry_run.execute_signal(signal2, 5, 300.10)
    
    # Read broker state (read-only)
    success, notes = dry_run.reconcile_dry_run()
    print(f"\nReconciliation: {'✅ SUCCESS' if success else '❌ FAIL'}")
    
    # Generate artifact
    date = datetime.now().strftime('%Y-%m-%d')
    json_path, md_path = dry_run.generate_dry_run_artifact(
        date=date,
        regime_data={'vix': 18.5, 'classification': 'NORMAL'},
        signals_data={
            'raw': {'Test_Strategy': [signal1, signal2]},
            'rejected': [],
            'executed': [signal1, signal2]
        },
        risk_data={
            'portfolio_heat': 15.0,
            'daily_pnl': 0,
            'cumulative_pnl': 0,
            'drawdown': 0,
            'max_drawdown': 0,
            'circuit_breaker_state': 'INACTIVE',
            'runtime_seconds': 2.5,
            'errors': [],
            'warnings': []
        }
    )
    
    # Print summary
    dry_run.print_dry_run_summary()
