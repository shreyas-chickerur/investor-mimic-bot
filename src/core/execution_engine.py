#!/usr/bin/env python3
"""
Multi-Strategy Trading System - Main Execution
Runs all 5 strategies independently with separate tracking
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime
import logging
import time

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.database import TradingDatabase
from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from src.strategies.strategy_ml_momentum import MLMomentumStrategy
from src.strategies.strategy_earnings_drift import EarningsDriftStrategy
from src.strategies.strategy_factor_momentum import FactorMomentumStrategy
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import pandas as pd

# Import new modules for professional-grade system
from src.utils.email_notifier import EmailNotifier
from src.data.data_validator import DataValidator
from src.integration.cash_manager import CashManager
from src.risk.portfolio_risk_manager import PortfolioRiskManager
from src.risk.correlation_filter import CorrelationFilter
from src.regime.regime_detector import RegimeDetector
from src.regime.dynamic_allocator import DynamicAllocator
from src.utils.execution_costs import ExecutionCostModel
from src.monitoring.performance_metrics import PerformanceMetrics
from src.risk.broker_reconciler import BrokerReconciler
from src.monitoring.artifact_writer import DailyArtifactWriter, create_artifact_data
from src.utils.kill_switch_service import KillSwitchService
from src.monitoring.signal_funnel_tracker import SignalFunnelTracker
from src.data.universe_provider import UniverseProvider
from src.integration.pending_signals_manager import PendingSignalsManager
from src.utils.structured_logger import StructuredLogger
from src.risk.drawdown_stop_manager import DrawdownStopManager
from src.data.data_quality_checker import DataQualityChecker
from src.integration.dry_run_wrapper import DryRunWrapper, get_dry_run_wrapper
from src.monitoring.strategy_health_scorer import StrategyHealthScorer
from src.monitoring.pnl_calculator import PnLCalculator
from src.utils.config_loader import get_config
from src.utils.news_sentiment import NewsSignalFilter

# Setup logging - CRITICAL FIX: Ensure logs directory exists
Path('logs').mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/multi_strategy.log'),
        logging.StreamHandler()
    ],
    force=True,
)
logger = logging.getLogger(__name__)

class MultiStrategyRunner:
    """Runs all 5 strategies with independent tracking"""
    
    def __init__(self):
        # Load configuration
        self.config = get_config()
        logger.info("Configuration loaded from YAML")
        
        self.db = TradingDatabase('trading.db')
        self.run_id = self.db.run_id
        self.asof_date = datetime.now().strftime('%Y-%m-%d')
        
        # CRITICAL: Log startup datetime for audit trail
        import time
        current_dt = datetime.now()
        logger.info("=" * 80)
        logger.info("TRADING SYSTEM STARTUP - DATETIME VERIFICATION")
        logger.info("=" * 80)
        logger.info(f"Current datetime: {current_dt}")
        logger.info(f"Timezone: {time.tzname}")
        logger.info(f"Run ID: {self.run_id}")
        logger.info(f"As-of date: {self.asof_date}")
        logger.info("=" * 80)
        
        # Get Alpaca credentials
        api_key = os.getenv('ALPACA_API_KEY')
        secret_key = os.getenv('ALPACA_SECRET_KEY')
        
        if not api_key or not secret_key:
            raise ValueError("Missing Alpaca credentials")
        
        self.paper_mode = os.getenv('ALPACA_PAPER', 'true').lower() == 'true'
        live_enabled = os.getenv('ALPACA_LIVE_ENABLED', 'false').lower() == 'true'
        if not self.paper_mode and not live_enabled:
            raise ValueError("Live trading disabled. Set ALPACA_LIVE_ENABLED=true to trade live.")
        self.trading_client = TradingClient(api_key, secret_key, paper=self.paper_mode)
        
        # VALIDATION MODE: Signal injection for testing
        self.signal_injection_enabled = os.getenv('SIGNAL_INJECTION', 'false').lower() == 'true'
        if self.signal_injection_enabled:
            if not self.paper_mode:
                raise ValueError("Signal injection requires ALPACA_PAPER=true")
            logger.warning("=" * 80)
            logger.warning("SIGNAL_INJECTION ENABLED - VALIDATION MODE ONLY")
            logger.warning("=" * 80)
        
        # Get account info - CRITICAL FIX: Use portfolio value, not just cash
        account = self.trading_client.get_account()
        self.portfolio_value = float(account.portfolio_value)
        self.cash_available = float(account.cash)
        
        logger.info(f"Portfolio: ${self.portfolio_value:.2f}, Cash: ${self.cash_available:.2f}")
        
        # Initialize professional-grade modules with config
        self.email_notifier = EmailNotifier()
        self.data_validator = DataValidator()
        self.cash_manager = CashManager(self.portfolio_value, num_strategies=4)
        
        # Portfolio risk manager - load from config
        max_heat = self.config.get('risk.max_portfolio_heat', 0.30)
        max_daily_loss = self.config.get('risk.max_daily_loss_pct', 0.02)
        self.portfolio_risk = PortfolioRiskManager(
            max_portfolio_heat=max_heat,
            max_daily_loss_pct=max_daily_loss
        )
        self.portfolio_risk.daily_start_value = self.portfolio_value
        logger.info(f"Portfolio Risk Manager: max_heat={max_heat:.1%}, max_daily_loss={max_daily_loss:.1%}")
        
        # Correlation filter - load from config
        corr_window = self.config.get('risk.correlation_window', 60)
        corr_short_window = self.config.get('risk.correlation_short_window', 20)
        max_corr = self.config.get('risk.max_correlation', 0.70)
        self.correlation_filter = CorrelationFilter(
            correlation_window=corr_window,
            short_window=corr_short_window,
            max_correlation=max_corr
        )
        logger.info(f"Correlation Filter: window={corr_window}, short={corr_short_window}, max={max_corr}")
        
        self.regime_detector = RegimeDetector()
        self.dynamic_allocator = DynamicAllocator(self.portfolio_value)
        slippage_bps = self.config.get('execution.slippage_bps', 5)
        commission = self.config.get('execution.commission_per_share', 0.0)
        self.cost_model = ExecutionCostModel(slippage_bps=slippage_bps, commission_per_share=commission)
        logger.info(f"Execution costs: {slippage_bps}bps slippage, ${commission}/share commission")
        self.performance_metrics = PerformanceMetrics()
        self.broker_reconciler = BrokerReconciler(email_notifier=self.email_notifier)
        
        # Initialize stop loss manager - load from config
        stop_loss_multiplier = self.config.get('risk.stop_loss_atr_multiplier', 2.5)
        from src.risk.stop_loss_manager import StopLossManager
        self.stop_loss_manager = StopLossManager(atr_multiplier=stop_loss_multiplier)
        logger.info(f"Stop Loss Manager initialized: {stop_loss_multiplier}x ATR catastrophe stops enabled")
        
        # Initialize production-readiness modules
        self.kill_switch = KillSwitchService(self.db, self.email_notifier)
        self.funnel_tracker = SignalFunnelTracker(self.db)
        self.universe_provider = UniverseProvider()
        
        # Pending signals - load decay from config
        decay_days = self.config.get('monitoring.signal_decay_days', 3)
        self.pending_signals = PendingSignalsManager(self.db, decay_days=decay_days)
        self.structured_logger = StructuredLogger(self.run_id)
        logger.info("Production-readiness modules initialized: kill switches, funnel tracking, universe provider, pending signals, structured logging")
        
        # Initialize live trading safety modules - load from config
        halt_threshold = self.config.get('risk.drawdown_halt_threshold', 0.08)
        panic_threshold = self.config.get('risk.drawdown_panic_threshold', 0.10)
        self.drawdown_manager = DrawdownStopManager(
            self.db, 
            self.email_notifier,
            halt_threshold=halt_threshold,
            panic_threshold=panic_threshold
        )
        logger.info(f"Drawdown Manager: halt={halt_threshold:.1%}, panic={panic_threshold:.1%}")
        
        self.data_quality_checker = DataQualityChecker()
        self.dry_run = get_dry_run_wrapper()
        self.health_scorer = StrategyHealthScorer(self.db)
        self.pnl_calculator = PnLCalculator(self.db)
        logger.info("Live trading safety modules initialized: drawdown stop, data quality, DRY_RUN mode, health scoring, P&L calculator")
        
        # Track blocked symbols from data quality checks
        self.blocked_symbols = set()
        self.data_quality_report = {}
        
        # Set daily start value for risk management
        self.portfolio_risk.set_daily_start_value(self.portfolio_value)
        
        # Track errors and executed trades for email reporting
        self.errors = []
        self.executed_trades = []
        self.confirmed_fills = []  # Track confirmed fills from Alpaca
        self.pending_orders = []   # Track pending orders from Alpaca
        self.rejected_orders = []  # Track rejected/canceled orders from Alpaca
        
        # Track P&L metrics
        self.initial_portfolio_value = self.portfolio_value
        self.peak_portfolio_value = self._get_peak_portfolio_value()
        self.cumulative_pnl = 0.0
        self.max_drawdown = 0.0

    def _refresh_account_values(self):
        """Refresh account values from Alpaca."""
        account = self.trading_client.get_account()
        self.portfolio_value = float(account.portfolio_value)
        self.cash_available = float(account.cash)
        return account
    
    def _refresh_account_state(self):
        """Alias for compatibility"""
        return self._refresh_account_values()
    
    def _get_peak_portfolio_value(self):
        """Get peak portfolio value from database or current value."""
        peak_str = self.db.get_system_state('peak_portfolio_value')
        if peak_str:
            try:
                return float(peak_str)
            except:
                pass
        return self.portfolio_value
    
    def _save_peak_portfolio_value(self, peak_value):
        """Save peak portfolio value to database."""
        self.db.set_system_state('peak_portfolio_value', str(peak_value))
    
    def _get_last_close_map(self, market_data) -> dict:
        """Extract last close price per symbol from market_data DataFrame"""
        import pandas as pd
        try:
            if 'symbol' in market_data.columns and 'close' in market_data.columns:
                last = market_data.sort_index().groupby('symbol')['close'].last()
                return last.dropna().astype(float).to_dict()
            if isinstance(market_data.index, pd.MultiIndex) and 'close' in market_data.columns:
                sym_level = 'symbol' if 'symbol' in market_data.index.names else market_data.index.names[-1]
                last = market_data.reset_index().sort_values(market_data.index.names[0]).groupby(sym_level)['close'].last()
                return last.dropna().astype(float).to_dict()
            if isinstance(market_data.columns, pd.MultiIndex):
                if 'close' in market_data.columns.get_level_values(0):
                    close_df = market_data['close']
                    last = close_df.iloc[-1]
                    return last.dropna().astype(float).to_dict()
                elif 'close' in market_data.columns.get_level_values(1):
                    close_df = market_data.xs('close', axis=1, level=1)
                    last = close_df.iloc[-1]
                    return last.dropna().astype(float).to_dict()
            return {}
        except Exception as e:
            logger.warning(f"Could not extract close prices: {e}")
            return {}

    def update_pnl_metrics(self):
        """Calculate and update daily/cumulative P&L and drawdown."""
        account = self._refresh_account_values()
        final_portfolio_value = float(account.portfolio_value)
        daily_pnl = final_portfolio_value - self.initial_portfolio_value
        self.cumulative_pnl += daily_pnl

        if final_portfolio_value > self.peak_portfolio_value:
            self.peak_portfolio_value = final_portfolio_value
            self._save_peak_portfolio_value(final_portfolio_value)

        drawdown = 0.0
        if self.peak_portfolio_value > 0:
            drawdown = ((self.peak_portfolio_value - final_portfolio_value) / self.peak_portfolio_value) * 100

        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

        return {
            'final_portfolio_value': final_portfolio_value,
            'daily_pnl': daily_pnl,
            'cumulative_pnl': self.cumulative_pnl,
            'drawdown': drawdown,
            'max_drawdown': self.max_drawdown
        }

    def verify_order_statuses(self):
        """Verify order status with Alpaca and track confirmed fills."""
        self.confirmed_fills = []
        self.pending_orders = []
        self.rejected_orders = []

        for trade in self.executed_trades:
            order_id = trade.get('order_id')
            if not order_id:
                self.pending_orders.append({**trade, 'status': 'UNKNOWN'})
                continue

            try:
                order = self.trading_client.get_order_by_id(order_id)
                status = str(getattr(order, 'status', 'UNKNOWN')).lower()
                if status == 'filled':
                    self.confirmed_fills.append(trade)
                elif status in {'canceled', 'rejected', 'expired'}:
                    self.rejected_orders.append({**trade, 'status': status})
                else:
                    self.pending_orders.append({**trade, 'status': status})
            except Exception as exc:
                logger.error(f"Failed to verify order {order_id}: {exc}")
                self.pending_orders.append({**trade, 'status': 'ERROR'})

        logger.info(
            "Confirmed fills: %s/%s",
            len(self.confirmed_fills),
            len(self.executed_trades)
        )
        
    def initialize_strategies(self):
        """Initialize the 4 canonical active strategies, creating DB entries for any that are missing."""
        CANONICAL_STRATEGIES = [
            ("RSI Mean Reversion", "Buy when RSI < 30 + low volatility, hold 20 days", RSIMeanReversionStrategy),
            ("ML Momentum", "GradientBoosting 12-feature classifier predicting 5d return", MLMomentumStrategy),
            ("Earnings Drift", "Post-earnings announcement drift via volume spike detection", EarningsDriftStrategy),
            ("Factor Momentum", "Cross-sectional factor ranking: momentum+quality+reversion", FactorMomentumStrategy),
        ]

        capital_per_strategy = self.portfolio_value / len(CANONICAL_STRATEGIES)

        # Build a name→id lookup from whatever is already in the DB
        existing_by_name = {s['name']: s for s in self.db.get_all_strategies()}
        logger.info(
            f"DB has {len(existing_by_name)} strategies: {list(existing_by_name.keys())}. "
            f"Enforcing canonical set: {[n for n, _, _ in CANONICAL_STRATEGIES]}"
        )

        strategies = []
        for name, desc, strategy_class in CANONICAL_STRATEGIES:
            if name in existing_by_name:
                strategy_id = existing_by_name[name]['id']
                logger.info(f"  Loaded existing: {name} (ID: {strategy_id})")
            else:
                strategy_id = self.db.create_strategy(name, desc, capital_per_strategy)
                logger.info(f"  Created new: {name} (ID: {strategy_id}, Capital: ${capital_per_strategy:.2f})")

            strategy = strategy_class(strategy_id, capital_per_strategy)
            self._load_strategy_positions(strategy)
            strategies.append(strategy)

        return strategies
    
    def _load_strategy_positions(self, strategy):
        """Load current positions for a strategy from database"""
        if strategy is None:
            logger.error("Cannot load positions: strategy is None")
            return
            
        try:
            positions = {}
            entry_dates = {}
            entry_prices = {}
            for position in self.db.get_positions(strategy.strategy_id):
                symbol = position['symbol']
                shares = float(position['shares'])
                if shares > 0:
                    positions[symbol] = shares
                    entry_dates[symbol] = position.get('entry_date') or position.get('last_updated')
                    avg_price = position.get('avg_price') or position.get('entry_price')
                    if avg_price:
                        entry_prices[symbol] = float(avg_price)

            strategy.positions = positions
            strategy.entry_dates = entry_dates
            strategy.entry_prices = entry_prices
            logger.info(f"  Loaded {len(positions)} positions for {strategy.name}")

            # Re-initialize stop losses for carried positions — stop_levels is
            # in-memory only and is empty at every startup, so without this all
            # multi-day positions run with zero downside protection.
            for position in self.db.get_positions(strategy.strategy_id):
                symbol = position['symbol']
                if float(position.get('shares', 0)) <= 0:
                    continue
                avg_price = float(position.get('avg_price') or position.get('entry_price') or 0)
                if avg_price <= 0:
                    continue
                atr = float(position.get('atr') or 0)
                if atr <= 0:
                    # Fallback: use 3% of price as ATR proxy
                    atr = avg_price * 0.03
                    logger.warning(f"  No ATR stored for {symbol}, using 3% fallback for stop loss")
                self.stop_loss_manager.set_stop_loss(symbol, avg_price, atr)
                logger.info(f"  Re-initialized stop loss for carried position {symbol}")
        except Exception as e:
            strategy_name = getattr(strategy, 'name', 'Unknown')
            logger.error(f"Error loading positions for {strategy_name}: {e}")
            strategy.positions = {}
            strategy.entry_dates = {}
    
    def _create_strategy_instance(self, strategy_id, name, capital):
        """Create strategy instance for one of the 4 canonical strategies.
        Returns None for any other name so callers can skip gracefully."""
        strategy_map = {
            "RSI Mean Reversion": RSIMeanReversionStrategy,
            "ML Momentum": MLMomentumStrategy,
            "Earnings Drift": EarningsDriftStrategy,
            "Factor Momentum": FactorMomentumStrategy,
        }
        
        strategy_class = strategy_map.get(name)
        if strategy_class:
            return strategy_class(strategy_id, capital)
        return None
    
    def load_market_data(self):
        """Load market data from CSV"""
        data_file = project_root / 'data' / 'training_data.csv'
        
        if not data_file.exists():
            logger.error(f"Data file not found: {data_file}")
            return None

        # Allow configurable max age for automated runs (weekends/holidays)
        max_age_hours = int(os.getenv('DATA_MAX_AGE_HOURS', '24'))
        validator = DataValidator(max_age_hours=max_age_hours)
        is_valid, errors = validator.validate_data_file(data_file)
        if not is_valid:
            auto_update = os.getenv('AUTO_UPDATE_DATA', 'false').lower() == 'true'
            if auto_update:
                logger.warning("Data validation failed; attempting auto-update.")
                try:
                    import subprocess
                    result = subprocess.run(
                        ['python3', str(project_root / 'scripts' / 'update_daily_data.py')],
                        capture_output=True, text=True, timeout=300
                    )
                    if result.returncode != 0:
                        errors.append(f"Auto-update failed: {result.stderr[:500]}")
                    is_valid, errors = validator.validate_data_file(data_file)
                except Exception as exc:
                    errors.append(str(exc))
            if not is_valid:
                error_message = "Data validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
                self.errors.append(error_message)
                logger.error(error_message)
                return None
        
        df = pd.read_csv(data_file, index_col=0)
        df.index = pd.to_datetime(df.index)
        
        # CRITICAL: Filter to last 150 days BEFORE quality checks
        # Provides 50+ days warmup for sma_100 and other long-period indicators
        # This prevents excessive NaN values that would block all symbols
        from datetime import timedelta
        latest_date = df.index.max()
        cutoff_date = latest_date - timedelta(days=150)
        df = df[df.index >= cutoff_date].copy()
        
        # Check data freshness and warn if stale
        data_age_days = (pd.Timestamp.now() - latest_date).days
        if data_age_days > 3:
            logger.warning(f"⚠️  DATA IS STALE: {data_age_days} days old (latest: {latest_date.date()})")
            logger.warning(f"⚠️  Consider running: python3 scripts/update_daily_data.py")
        else:
            logger.info(f"Data freshness: {data_age_days} days old (latest: {latest_date.date()})")
        
        logger.info(f"Loaded {len(df)} rows for {df['symbol'].nunique()} symbols (last 150 days)")
        return df
    
    def check_stop_losses(self, market_data):
        """
        Check all positions for catastrophe stop losses
        Returns list of positions that hit stops
        """
        positions_to_close = []
        current_prices = self._get_last_close_map(market_data)
        
        # Get all current positions from database
        all_positions = self.db.get_positions()
        
        for position in all_positions:
            symbol = position['symbol']
            strategy_id = position['strategy_id']
            
            if symbol not in current_prices:
                logger.warning(f"No current price for {symbol}, skipping stop check")
                continue
            
            current_price = current_prices[symbol]
            
            # Check if stop loss is hit
            if self.stop_loss_manager.check_stop_loss(symbol, current_price):
                stop_price = self.stop_loss_manager.get_stop_price(symbol)
                entry_price = position.get('entry_price') or 0
                stop_str = f"${stop_price:.2f}" if stop_price is not None else "N/A"
                entry_str = f"${entry_price:.2f}" if entry_price else "N/A"
                logger.warning(f"CATASTROPHE STOP HIT: {symbol} at ${current_price:.2f} "
                             f"(stop: {stop_str}, entry: {entry_str})")

                positions_to_close.append({
                    'symbol': symbol,
                    'strategy_id': strategy_id,
                    'shares': position['shares'],
                    'current_price': current_price,
                    'stop_price': stop_price,
                    'entry_price': entry_price,
                    'reason': 'CATASTROPHE_STOP_LOSS'
                })
        
        return positions_to_close
    
    def execute_stop_loss_exits(self, positions_to_close):
        """
        Execute sell orders for positions that hit stop losses
        """
        for position in positions_to_close:
            try:
                symbol = position['symbol']
                shares = abs(position['shares'])
                
                logger.info(f"Executing stop loss exit: SELL {shares} {symbol}")
                
                # Create market order to close position
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY
                )
                
                order = self.trading_client.submit_order(order_data)
                
                # Record the trade
                self.db.record_trade(
                    strategy_id=position['strategy_id'],
                    signal_id=None,
                    symbol=symbol,
                    action='SELL',
                    shares=shares,
                    requested_price=position['current_price'],
                    exec_price=position['current_price'],
                    slippage_cost=0.0,
                    commission_cost=0.0,
                    total_cost=0.0,
                    notional=shares * position['current_price'],
                    order_id=str(order.id),
                    executed_at=datetime.now().isoformat()
                )
                
                # Remove stop loss tracking
                self.stop_loss_manager.remove_stop_loss(symbol)
                
                logger.info(f"Stop loss exit executed: {symbol} order {order.id}")
                
            except Exception as e:
                logger.error(f"Error executing stop loss exit for {symbol}: {e}")
                self.errors.append(f"Stop loss exit failed for {symbol}: {e}")
    
    def run_all_strategies(self, market_data):
        """Run all strategies and execute trades"""
        strategies = self.initialize_strategies()
        self.raw_signals_by_strategy = {}
        
        # CRITICAL: Check kill switches BEFORE any trading
        logger.info("=" * 80)
        logger.info("CHECKING KILL SWITCHES")
        logger.info("=" * 80)
        
        kill_context = {
            'reconciliation_status': 'UNKNOWN',
            'daily_drawdown': 0.0,
            'consecutive_failures': 0,
            'rejected_orders_count': 0,
            'total_orders': 0
        }
        
        if not self.kill_switch.check_all_switches(kill_context):
            logger.critical("Trading halted by kill switch")
            self.errors.append("Trading halted by kill switch: " + ", ".join(self.kill_switch.kill_reasons))
            self.structured_logger.log_kill_switch(
                reason=", ".join(self.kill_switch.kill_reasons),
                details={'context': kill_context}
            )
            return []
        
        logger.info("✅ All kill switches passed")
        logger.info("=" * 80)
        
        # CRITICAL: Check drawdown stop BEFORE trading
        logger.info("=" * 80)
        logger.info("CHECKING DRAWDOWN STOP")
        logger.info("=" * 80)
        
        is_stopped, reason, details = self.drawdown_manager.check_drawdown_stop(
            current_portfolio_value=self.portfolio_value,
            peak_portfolio_value=self.peak_portfolio_value
        )
        
        if is_stopped:
            logger.critical(f"Trading halted by drawdown stop: {reason}")
            self.errors.append(f"Drawdown stop triggered: {reason}")
            return []
        
        # Check if trading allowed (cooldown state)
        if not self.drawdown_manager.is_trading_allowed():
            state = self.drawdown_manager.get_current_state()
            logger.warning(f"Trading not allowed: {state['state']} state")
            self.errors.append(f"Trading blocked: {state['state']} state (cooldown active)")
            return []
        
        # Get sizing multiplier (for rampup mode)
        sizing_multiplier = self.drawdown_manager.get_sizing_multiplier()
        if sizing_multiplier < 1.0:
            logger.info(f"Rampup mode active: {sizing_multiplier:.0%} sizing")
        
        logger.info("✅ Drawdown stop check passed")
        logger.info("=" * 80)
        
        # CRITICAL: Check data quality BEFORE trading
        logger.info("=" * 80)
        logger.info("CHECKING DATA QUALITY")
        logger.info("=" * 80)
        
        self.blocked_symbols, self.data_quality_report = self.data_quality_checker.check_data_quality(
            market_data, datetime.now()
        )
        
        if self.blocked_symbols:
            logger.warning(f"Data quality: {len(self.blocked_symbols)} symbols blocked")
            # Filter market_data to exclude blocked symbols
            market_data = market_data[~market_data['symbol'].isin(self.blocked_symbols)]
            logger.info(f"Filtered market data: {len(market_data['symbol'].unique())} symbols remaining")
        else:
            logger.info("✅ All symbols passed data quality checks")
        
        logger.info("=" * 80)
        
        # CRITICAL: Check stop losses BEFORE generating new signals
        logger.info("=" * 80)
        logger.info("CHECKING CATASTROPHE STOP LOSSES")
        logger.info("=" * 80)
        positions_to_close = self.check_stop_losses(market_data)
        
        if positions_to_close:
            logger.warning(f"Found {len(positions_to_close)} positions at stop loss")
            self.execute_stop_loss_exits(positions_to_close)
        else:
            logger.info("No stop losses triggered")
        logger.info("=" * 80)
        self.executed_signals = []
        self.symbols_bought_this_run: set = set()
        self.symbols_sold_this_run: set = set()
        self.reconciliation_status = "SKIPPED"

        # Pre-fetch news sentiment once per run for all signal symbols
        self._news_filter = NewsSignalFilter()
        self._news_sentiment_map: dict = {}
        self.reconciliation_discrepancies = []
        current_prices = market_data.groupby('symbol')['close'].last().to_dict()

        # Refresh open position prices so unrealized P&L is current in the email
        refreshed = self.db.refresh_position_prices(current_prices)
        if refreshed:
            logger.info(f"Refreshed current prices for {refreshed} open positions")

        allocations = self._calculate_dynamic_allocations(strategies)
        exposures = self._calculate_strategy_exposures(strategies, current_prices)
        self._apply_allocations(strategies, allocations, exposures)
        total_exposure = sum(exposures.values())

        regime_adjustments = self.regime_detector.get_regime_adjustments(market_data=market_data)
        self.portfolio_risk.max_portfolio_heat = regime_adjustments['max_portfolio_heat']
        all_signals = []

        try:
            # Save START snapshot
            logger.info("Saving START broker snapshot...")
            account = self.trading_client.get_account()
            broker_positions = self.trading_client.get_all_positions()
            self.db.save_broker_state(
                snapshot_date=self.asof_date,
                snapshot_type='START',
                cash=float(account.cash),
                portfolio_value=float(account.portfolio_value),
                buying_power=float(account.buying_power),
                positions=[{'symbol': p.symbol, 'qty': float(p.qty), 'market_value': float(p.market_value)} for p in broker_positions],
                reconciliation_status='SKIPPED',
                discrepancies=[]
            )

            if not self.portfolio_risk.check_daily_loss_limit(self.portfolio_value):
                logger.warning("Trading halted due to daily loss limit")
                return []

            # CRITICAL: Hard reconciliation gate (MANDATORY)
            logger.info("=" * 80)
            logger.info("BROKER RECONCILIATION (MANDATORY GATE)")
            logger.info("=" * 80)
            
            # Refresh account before reconciliation
            logger.info("Refreshing account state before reconciliation...")
            self._refresh_account_state()
            
            local_positions = self._build_local_positions()
            success, discrepancies = self.broker_reconciler.reconcile_daily(
                local_positions=local_positions,
                local_cash=self.cash_available
            )
            
            self.reconciliation_status = "PASS" if success else "FAIL"
            self.reconciliation_discrepancies = discrepancies
            
            # Update kill context
            kill_context['reconciliation_status'] = self.reconciliation_status
            
            # Save RECONCILIATION snapshot
            logger.info(f"Saving RECONCILIATION snapshot (status: {self.reconciliation_status})...")
            account = self.trading_client.get_account()
            broker_positions = self.trading_client.get_all_positions()
            self.db.save_broker_state(
                snapshot_date=self.asof_date,
                snapshot_type='RECONCILIATION',
                cash=float(account.cash),
                portfolio_value=float(account.portfolio_value),
                buying_power=float(account.buying_power),
                positions=[{'symbol': p.symbol, 'qty': float(p.qty), 'market_value': float(p.market_value)} for p in broker_positions],
                reconciliation_status=self.reconciliation_status,
                discrepancies=discrepancies
            )
            
            # HARD GATE: Block trading on failure
            if not success:
                logger.critical("🛑 RECONCILIATION FAILED - TRADING BLOCKED")
                logger.critical("Discrepancies:")
                for disc in discrepancies:
                    logger.critical(f"  - {disc}")
                
                self.errors.extend(discrepancies)
                
                # Send critical alert
                self.email_notifier.send_alert(
                    "Reconciliation Failure - Trading Blocked",
                    f"Broker/DB mismatch detected:\n\n" + "\n".join(f"  • {d}" for d in discrepancies)
                )
                
                # Log to structured logger
                self.structured_logger.log_event(
                    'RECONCILIATION_CHECK',
                    {'status': 'FAIL', 'discrepancies': discrepancies},
                    stage='RECONCILIATION'
                )
                
                return []
            
            logger.info("✅ Reconciliation passed")
            logger.info("=" * 80)
            
            print("\n" + "=" * 80)
            print("MULTI-STRATEGY EXECUTION")
            print("=" * 80)
            
            # VALIDATION MODE: Inject synthetic signals if enabled
            injected_signals = []
            if self.signal_injection_enabled:
                logger.info("=" * 80)
                logger.info("SIGNAL INJECTION - Generating validation signals")
                logger.info("=" * 80)
                
                current_prices = self._get_last_close_map(market_data)
                logger.info(f"Extracted prices for {len(current_prices)} symbols")
                
                available_symbols = list(current_prices.keys())[:2]
                
                for symbol in available_symbols:
                    if symbol in current_prices:
                        injected_signal = {
                            'symbol': symbol,
                            'action': 'BUY',
                            'confidence': 0.75,
                            'reasoning': 'VALIDATION: Synthetic signal for testing',
                            'price': current_prices[symbol],
                            'injected': True,
                            'injection_source': 'VALIDATION_MODE'
                        }
                        injected_signals.append(injected_signal)
                        logger.info(f"  [INJECTION] BUY {symbol} @ ${current_prices[symbol]:.2f}")
                
                logger.info(f"Generated {len(injected_signals)} validation signals")
                logger.info("These signals will go through normal correlation filter, risk checks, and sizing")
                logger.info("=" * 80)
            
            for strategy in strategies:
                print(f"\n📈 {strategy.name}")
                print("-" * 80)
                
                try:
                    # Check if strategy is enabled (kill switch)
                    if not self.kill_switch.is_strategy_enabled(strategy.name):
                        logger.info(f"Skipping {strategy.name} - disabled by kill switch")
                        self.funnel_tracker.record_raw_signals(strategy.strategy_id, 0)
                        self.funnel_tracker.record_after_regime(strategy.strategy_id, 0)
                        continue
                    
                    if not self.regime_detector.should_enable_strategy(strategy.name, regime_adjustments):
                        logger.info(f"Skipping {strategy.name} due to regime adjustments")
                        self.funnel_tracker.record_raw_signals(strategy.strategy_id, 0)
                        self.funnel_tracker.record_after_regime(strategy.strategy_id, 0)
                        continue

                    # Generate signals with detailed logging
                    logger.info(f"  Calling {strategy.name}.generate_signals() with {len(market_data)} rows, {market_data['symbol'].nunique()} symbols")
                    signals = strategy.generate_signals(market_data)
                    
                    # FUNNEL STAGE 1: Raw signals
                    raw_count = len(signals) if signals else 0
                    logger.info(f"  {strategy.name} generated {raw_count} raw signals")
                    if raw_count > 0:
                        for sig in signals[:3]:  # Log first 3 signals
                            logger.info(f"    - {sig.get('action')} {sig.get('symbol')}: {sig.get('reasoning', 'No reason')}")
                    self.funnel_tracker.record_raw_signals(strategy.strategy_id, raw_count)
                    
                    # VALIDATION MODE: Route injected signals to RSI Mean Reversion
                    if self.signal_injection_enabled and strategy.name == "RSI Mean Reversion" and len(injected_signals) > 0:
                        logger.info(f"  [INJECTION] Routing {len(injected_signals)} validation signals to {strategy.name}")
                        signals = injected_signals + (signals if signals else [])
                        injected_signals = []
                    
                    self.raw_signals_by_strategy[strategy.name] = list(signals) if signals else []
                    
                    if signals and len(signals) > 0:
                        print(f"✅ Generated {len(signals)} signals")
                        
                        # FUNNEL STAGE 2: After regime (already passed above)
                        self.funnel_tracker.record_after_regime(strategy.strategy_id, len(signals))

                        # FUNNEL STAGE 3: Correlation filter with size attenuation
                        combined_positions = self._get_all_positions(strategies)
                        signals_before_corr = len(signals)
                        signals = self.correlation_filter.filter_signals_with_sizing(
                            signals,
                            combined_positions,
                            market_data
                        )
                        
                        # Log correlation rejections
                        for sig in self.raw_signals_by_strategy[strategy.name]:
                            if sig not in signals:
                                self.funnel_tracker.log_rejection(
                                    strategy.strategy_id,
                                    sig.get('symbol'),
                                    'CORRELATION',
                                    'high_correlation',
                                    {'threshold': 0.8}
                                )
                        
                        self.funnel_tracker.record_after_correlation(strategy.strategy_id, len(signals))

                        # Apply news sentiment as confidence modifier (boost/suppress)
                        signal_symbols = list({s.get('symbol') for s in signals})
                        new_syms = [s for s in signal_symbols if s not in self._news_sentiment_map]
                        if new_syms:
                            self._news_sentiment_map.update(
                                self._news_filter.fetch_for_symbols(new_syms)
                            )
                        signals = self._news_filter.apply(signals, self._news_sentiment_map)
                        logger.info(f"  After news filter: {len(signals)} signals")

                        # Log signals to database
                        signal_ids = []
                        for signal in signals:
                            signal_id = self.db.log_signal(
                                strategy.strategy_id,
                                signal.get('symbol'),
                                signal.get('action', 'BUY'),
                                signal.get('confidence', 0.5),
                                signal.get('reasoning', ''),
                                self.asof_date
                            )
                            signal_ids.append(signal_id)
                            signal['signal_id'] = signal_id

                        # FUNNEL STAGE 4: Risk/cash limits (tracked in _execute_strategy_trades)
                        # Use strategy's own top_n if set (e.g. FactorMomentum=5), else 5
                        max_signals = getattr(strategy, 'top_n', 5)
                        signals_to_execute = signals[:max_signals]

                        # Execute trades
                        executed = self._execute_strategy_trades(
                            strategy,
                            signals_to_execute,
                            total_exposure,
                            self.portfolio_value
                        )

                        # FUNNEL STAGE 5: Executed
                        self.funnel_tracker.record_executed(strategy.strategy_id, len(executed))

                        # Log risk rejections
                        for sig in signals_to_execute:
                            if not any(e.get('symbol') == sig.get('symbol') for e in executed):
                                self.funnel_tracker.log_rejection(
                                    strategy.strategy_id,
                                    sig.get('symbol'),
                                    'RISK',
                                    'cash_or_heat_limit',
                                    {}
                                )

                        all_signals.extend(executed)

                        # Set terminal states for executed signals
                        for signal in signals_to_execute:
                            signal_id = signal.get('signal_id')
                            if signal_id:
                                was_executed = any(e.get('symbol') == signal.get('symbol') for e in executed)
                                if was_executed:
                                    self.db.update_signal_terminal_state(signal_id, 'EXECUTED', 'filled')
                                else:
                                    self.db.update_signal_terminal_state(signal_id, 'FILTERED', 'risk_or_cash_limit')

                        # Mark throttled signals as FILTERED
                        for signal in signals[max_signals:]:
                            signal_id = signal.get('signal_id')
                            if signal_id:
                                self.db.update_signal_terminal_state(signal_id, 'FILTERED', 'throttle')
                                self.funnel_tracker.log_rejection(
                                    strategy.strategy_id,
                                    signal.get('symbol'),
                                    'THROTTLE',
                                    'max_signals_limit',
                                    signal_id=signal_id
                                )
                    else:
                        print("❌ No signals generated")
                        self.funnel_tracker.record_after_regime(strategy.strategy_id, 0)
                        self.funnel_tracker.record_after_correlation(strategy.strategy_id, 0)
                        self.funnel_tracker.record_after_risk(strategy.strategy_id, 0)
                        self.funnel_tracker.record_executed(strategy.strategy_id, 0)
                    
                    # Save funnel data to database
                    self.funnel_tracker.save_to_database(strategy.strategy_id, strategy.name)
                    
                    # Record daily performance
                    self._record_performance(strategy, current_prices)
                    
                except Exception as e:
                    logger.error(f"Error in {strategy.name}: {e}")
                    print(f"❌ Error: {e}")
                    self.errors.append(f"{strategy.name}: {e}")
            
            # Generate artifacts after all strategies complete
            logger.info("=" * 80)
            logger.info("GENERATING ARTIFACTS")
            logger.info("=" * 80)
            
            for strategy in strategies:
                # Generate funnel artifact
                funnel_path = self.funnel_tracker.generate_funnel_artifact(
                    strategy.strategy_id, strategy.name, self.run_id
                )
                if funnel_path:
                    logger.info(f"Generated funnel artifact: {funnel_path}")
                
                # Generate rejections artifact
                rejections_path = self.funnel_tracker.generate_rejections_artifact(
                    strategy.strategy_id, strategy.name, self.run_id
                )
                if rejections_path:
                    logger.info(f"Generated rejections artifact: {rejections_path}")
            
            # Generate why_no_trade artifact (only if no trades)
            why_no_trade_path = self.funnel_tracker.generate_why_no_trade_artifact(self.run_id)
            if why_no_trade_path:
                logger.info(f"Generated why_no_trade artifact: {why_no_trade_path}")
            
            # Generate weekly health summary (on Mondays)
            if datetime.now().weekday() == 0:
                logger.info("Generating weekly health summary...")
                strategies_list = [(s.strategy_id, s.name) for s in strategies]
                health_path = self.health_scorer.generate_health_summary(strategies_list)
                logger.info(f"Generated health summary: {health_path}")
            
            logger.info("=" * 80)
            
            return all_signals
        finally:
            # Save END snapshot (always)
            logger.info("Saving END broker snapshot...")
            account = self.trading_client.get_account()
            broker_positions = self.trading_client.get_all_positions()
            self.db.save_broker_state(
                snapshot_date=self.asof_date,
                snapshot_type='END',
                cash=float(account.cash),
                portfolio_value=float(account.portfolio_value),
                buying_power=float(account.buying_power),
                positions=[{'symbol': p.symbol, 'qty': float(p.qty), 'market_value': float(p.market_value)} for p in broker_positions],
                reconciliation_status=self.reconciliation_status,
                discrepancies=self.reconciliation_discrepancies
            )
    
    def _execute_strategy_trades(self, strategy, signals, total_exposure, portfolio_value):
        """Execute trades for a specific strategy"""
        executed = []
        
        for signal in signals:
            symbol = signal.get('symbol')
            action = signal.get('action', 'BUY')
            shares = signal.get('shares', 0)
            price = signal.get('price', 0)
            
            if action == 'BUY' and shares > 0:
                try:
                    # Wash trade prevention: skip if already sold this symbol this run
                    if symbol in self.symbols_sold_this_run:
                        logger.warning(f"Skipping BUY {symbol} - already sold this run (wash trade prevention)")
                        continue

                    # Duplicate prevention: skip if we already hold this symbol for this strategy today
                    existing_pos = self.db.get_position(strategy.strategy_id, symbol)
                    if existing_pos and float(existing_pos.get('shares', 0)) > 0:
                        entry_dt = existing_pos.get('entry_date', '')
                        if entry_dt and entry_dt[:10] == self.asof_date:
                            logger.warning(f"Skipping BUY {symbol} - position opened today (duplicate prevention)")
                            continue

                    # Apply size multiplier from correlation attenuation
                    size_mult = signal.get('size_multiplier', 1.0)
                    # Apply drawdown sizing multiplier (rampup mode)
                    drawdown_mult = self.drawdown_manager.get_sizing_multiplier()
                    combined_mult = size_mult * drawdown_mult
                    adjusted_shares = int(shares * combined_mult)
                    
                    if adjusted_shares == 0:
                        logger.info(f"Skipping {symbol} - size multiplier reduced shares to 0")
                        continue
                    
                    logger.info(f"Size adjustment for {symbol}: {shares} → {adjusted_shares} "
                               f"(corr_mult={size_mult:.2f}, drawdown_mult={drawdown_mult:.2f}, "
                               f"combined={combined_mult:.2f})")
                    
                    exec_price, slippage_cost, commission_cost, total_cost = self.cost_model.calculate_execution_price(
                        price, 'BUY', adjusted_shares
                    )
                    trade_value = exec_price * adjusted_shares + total_cost
                    
                    if not self.cash_manager.reserve_cash(strategy.strategy_id, trade_value):
                        logger.warning(f"Skipping {symbol} - insufficient cash for strategy {strategy.strategy_id}")
                        continue
                    if not self.portfolio_risk.can_add_position(trade_value, total_exposure, portfolio_value):
                        logger.warning(f"Skipping {symbol} - portfolio heat limit")
                        self.cash_manager.release_cash(strategy.strategy_id, trade_value)
                        continue

                    # Create order intent (idempotency)
                    intent_id = self.db.create_order_intent(
                        strategy.strategy_id,
                        symbol,
                        'BUY',
                        adjusted_shares
                    )
                    
                    # Check if already submitted
                    existing_intent = self.db.get_order_intent_by_id(intent_id)
                    if existing_intent and existing_intent['status'] in ['SUBMITTED', 'ACKED', 'FILLED']:
                        logger.warning(f"Order intent {intent_id} already {existing_intent['status']} - skipping")
                        self.cash_manager.release_cash(strategy.strategy_id, trade_value)
                        continue
                    
                    # Log order intent to structured logger
                    self.structured_logger.log_order_intent(
                        intent_id, strategy.strategy_id, symbol, 'BUY', adjusted_shares
                    )

                    order_data = MarketOrderRequest(
                        symbol=symbol,
                        qty=adjusted_shares,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY
                    )
                    
                    # Wrap with DRY_RUN protection
                    order = self.dry_run.execute_broker_operation(
                        f"submit_order_{symbol}",
                        self.trading_client.submit_order,
                        order_data
                    )
                    
                    # Update intent status
                    self.db.update_order_intent_status(intent_id, 'SUBMITTED', str(order.id))
                    
                    # Log to structured logger
                    self.structured_logger.log_order_submitted(
                        intent_id, str(order.id), strategy.strategy_id, symbol
                    )
                    
                    # CRITICAL FIX: Verify order fill before updating database
                    # Wait for order to be filled (market orders typically fill immediately)
                    fill_verified = False
                    actual_filled_qty = adjusted_shares
                    actual_fill_price = exec_price
                    
                    try:
                        # Get order status from broker
                        filled_order = self.dry_run.execute_broker_operation(
                            f"get_order_{symbol}",
                            self.trading_client.get_order_by_id,
                            order.id
                        )
                        
                        if filled_order.status in ['filled', 'partially_filled']:
                            fill_verified = True
                            actual_filled_qty = float(filled_order.filled_qty) if filled_order.filled_qty else adjusted_shares
                            actual_fill_price = float(filled_order.filled_avg_price) if filled_order.filled_avg_price else exec_price
                            logger.info(f"Order {order.id} verified: {filled_order.status}, filled_qty={actual_filled_qty}, avg_price={actual_fill_price}")
                        else:
                            logger.info(f"Order {order.id} not filled yet: status={filled_order.status} (expected at market close)")
                            # For paper trading, assume immediate fill
                            if self.paper_mode:
                                fill_verified = True
                                logger.info(f"Paper trading mode - assuming immediate fill")
                    except Exception as e:
                        logger.warning(f"Could not verify fill for {order.id}: {e}")
                        # For paper trading, assume fill succeeded
                        if self.paper_mode:
                            fill_verified = True
                            logger.info(f"Paper trading mode - assuming fill despite verification error")
                    
                    if not fill_verified:
                        logger.error(f"Order {order.id} not filled - skipping database update to prevent sync issues")
                        self.cash_manager.release_cash(strategy.strategy_id, trade_value)
                        continue
                    
                    print(f"  ✅ BUY {actual_filled_qty} {symbol} @ ${actual_fill_price:.2f} (Order: {order.id}, Intent: {intent_id})")
                    self.symbols_bought_this_run.add(symbol)

                    # Update in-memory state with actual filled quantities
                    strategy.add_position(symbol, actual_filled_qty)
                    actual_trade_value = actual_fill_price * actual_filled_qty + total_cost
                    strategy.update_capital(-actual_trade_value)
                    entry_date = signal.get('asof_date') or datetime.now()
                    strategy.entry_dates[symbol] = entry_date
                    total_exposure += actual_trade_value
                    self.performance_metrics.add_trade('BUY', symbol, actual_filled_qty, actual_fill_price, actual_trade_value)
                    
                    # CRITICAL: Only update database AFTER verifying fill
                    entry_date_str = (
                        entry_date.date().isoformat()
                        if hasattr(entry_date, 'date')
                        else str(entry_date)[:10]
                    )
                    atr = signal.get('atr', 0) or 0
                    self._update_position_record(
                        strategy.strategy_id, symbol, actual_filled_qty, actual_fill_price,
                        entry_date=entry_date_str, atr=atr if atr > 0 else None,
                    )

                    # CRITICAL: Set stop loss for new position
                    if atr > 0:
                        self.stop_loss_manager.set_stop_loss(symbol, actual_fill_price, atr)
                    else:
                        logger.warning(f"No ATR available for {symbol}, stop loss not set")

                    # Calculate P&L for this trade
                    total_costs = slippage_cost + commission_cost
                    pnl, pnl_explanation = self.pnl_calculator.calculate_trade_pnl(
                        strategy.strategy_id,
                        symbol,
                        'BUY',
                        adjusted_shares,
                        exec_price,
                        total_costs
                    )
                    logger.info(f"P&L: {pnl_explanation}")
                    
                    # Log trade with full execution details and P&L
                    signal_id = signal.get('signal_id')
                    self.db.log_trade(
                        strategy.strategy_id,
                        signal_id,
                        symbol,
                        'BUY',
                        adjusted_shares,
                        price,
                        exec_price,
                        slippage_cost,
                        commission_cost,
                        str(order.id),
                        pnl
                    )
                    
                    # Track as executed (will verify fill status later)
                    trade_info = {
                        'symbol': signal['symbol'],
                        'action': signal['action'],
                        'shares': adjusted_shares,
                        'price': signal['price'],
                        'order_id': order.id,
                        'intent_id': intent_id
                    }
                    self.executed_trades.append(trade_info)
                    
                    executed.append({
                        'strategy': strategy.name,
                        'symbol': symbol,
                        'shares': shares,
                        'price': price,
                        'action': 'BUY'
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to execute {symbol}: {e}")
                    print(f"  ❌ Failed {symbol}: {e}")
                    
            elif action == 'SELL' and shares > 0:
                try:
                    # Wash trade prevention: skip if already bought this symbol this run
                    if symbol in self.symbols_bought_this_run:
                        logger.warning(f"Skipping SELL {symbol} - already bought this run (wash trade prevention)")
                        continue

                    exec_price, slippage_cost, commission_cost, total_cost = self.cost_model.calculate_execution_price(
                        price, 'SELL', shares
                    )
                    order_data = MarketOrderRequest(
                        symbol=symbol,
                        qty=shares,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY
                    )
                    
                    # Wrap with DRY_RUN protection
                    order = self.dry_run.execute_broker_operation(
                        f"submit_order_sell_{symbol}",
                        self.trading_client.submit_order,
                        order_data
                    )
                    
                    # CRITICAL FIX: Verify order fill before updating database
                    fill_verified = False
                    actual_filled_qty = shares
                    actual_fill_price = exec_price
                    
                    try:
                        # Get order status from broker
                        filled_order = self.dry_run.execute_broker_operation(
                            f"get_order_sell_{symbol}",
                            self.trading_client.get_order_by_id,
                            order.id
                        )
                        
                        if filled_order.status in ['filled', 'partially_filled']:
                            fill_verified = True
                            actual_filled_qty = float(filled_order.filled_qty) if filled_order.filled_qty else shares
                            actual_fill_price = float(filled_order.filled_avg_price) if filled_order.filled_avg_price else exec_price
                            logger.info(f"SELL Order {order.id} verified: {filled_order.status}, filled_qty={actual_filled_qty}, avg_price={actual_fill_price}")
                        else:
                            logger.info(f"SELL Order {order.id} not filled yet: status={filled_order.status} (expected at market close)")
                            # For paper trading, assume immediate fill
                            if self.paper_mode:
                                fill_verified = True
                                logger.info(f"Paper trading mode - assuming immediate SELL fill")
                    except Exception as e:
                        logger.warning(f"Could not verify SELL fill for {order.id}: {e}")
                        # For paper trading, assume fill succeeded
                        if self.paper_mode:
                            fill_verified = True
                            logger.info(f"Paper trading mode - assuming SELL fill despite verification error")
                    
                    if not fill_verified:
                        logger.error(f"SELL Order {order.id} not filled - skipping database update to prevent sync issues")
                        continue
                    
                    print(f"  ✅ SELL {actual_filled_qty} {symbol} @ ${actual_fill_price:.2f} (Order: {order.id})")
                    self.symbols_sold_this_run.add(symbol)

                    # Release cash back with actual filled quantities
                    trade_value = actual_fill_price * actual_filled_qty - total_cost
                    self.cash_manager.release_cash(strategy.strategy_id, trade_value)
                    strategy.update_capital(trade_value)
                    
                    # Calculate P&L for this trade
                    total_costs = slippage_cost + commission_cost
                    pnl, pnl_explanation = self.pnl_calculator.calculate_trade_pnl(
                        strategy.strategy_id,
                        symbol,
                        'SELL',
                        actual_filled_qty,
                        actual_fill_price,
                        total_costs
                    )
                    logger.info(f"P&L: {pnl_explanation}")
                    
                    # Log trade with P&L
                    self.db.log_trade(
                        strategy.strategy_id,
                        signal.get('signal_id'),
                        symbol,
                        'SELL',
                        actual_filled_qty,
                        price,
                        actual_fill_price,
                        slippage_cost,
                        commission_cost,
                        str(order.id),
                        pnl
                    )
                    
                    # CRITICAL FIX: Update strategy positions with actual filled quantities
                    entry_price_for_pnl = getattr(strategy, 'entry_prices', {}).get(symbol)
                    entry_date_for_pnl = getattr(strategy, 'entry_dates', {}).get(symbol)
                    if entry_date_for_pnl and hasattr(entry_date_for_pnl, 'date'):
                        entry_date_for_pnl = entry_date_for_pnl.date().isoformat()
                    elif entry_date_for_pnl:
                        entry_date_for_pnl = str(entry_date_for_pnl)[:10]

                    if symbol in strategy.positions:
                        strategy.positions[symbol] -= actual_filled_qty
                        if strategy.positions[symbol] <= 0:
                            del strategy.positions[symbol]
                            if symbol in strategy.entry_dates:
                                del strategy.entry_dates[symbol]
                            if hasattr(strategy, 'entry_prices') and symbol in strategy.entry_prices:
                                del strategy.entry_prices[symbol]
                            # Remove stop loss when position is fully closed
                            self.stop_loss_manager.remove_stop_loss(symbol)
                            logger.info(f"Stop loss removed for {symbol} (position closed)")
                            total_exposure = max(total_exposure - trade_value, 0)

                    # Record matched buy→sell P&L for paper trading metrics
                    if entry_price_for_pnl and entry_price_for_pnl > 0:
                        try:
                            exit_reason = signal.get('reasoning', '')
                            self.db.log_trade_pnl(
                                strategy_id=strategy.strategy_id,
                                strategy_name=strategy.name,
                                symbol=symbol,
                                sell_run_id=self.run_id,
                                entry_price=float(entry_price_for_pnl),
                                exit_price=actual_fill_price,
                                shares=actual_filled_qty,
                                entry_date=entry_date_for_pnl,
                                exit_reason=exit_reason,
                            )
                        except Exception as _pnl_exc:
                            logger.warning("log_trade_pnl failed for %s: %s", symbol, _pnl_exc)

                    # CRITICAL: Only update database AFTER verifying fill
                    self._update_position_record(strategy.strategy_id, symbol, -actual_filled_qty, actual_fill_price)
                    
                    trade_record = {
                        'strategy': strategy.name,
                        'symbol': symbol,
                        'shares': shares,
                        'price': price,
                        'action': 'SELL',
                        'order_id': order.id
                    }
                    executed.append(trade_record)
                    self.executed_trades.append(trade_record)
                    self.performance_metrics.add_trade('SELL', symbol, shares, exec_price, trade_value)
                except Exception as e:
                    logger.error(f"Failed to execute {symbol}: {e}")
                    print(f"  ❌ Failed {symbol}: {e}")
        
        return executed
    
    def _record_performance(self, strategy, current_prices):
        """Record daily performance for a strategy into DB for dynamic allocation."""
        try:
            positions_value = sum(
                shares * current_prices.get(symbol, 0)
                for symbol, shares in strategy.positions.items()
            )
            portfolio_value = strategy.capital + positions_value
            initial = getattr(strategy, 'initial_capital', strategy.capital)
            return_pct = ((portfolio_value - initial) / initial * 100) if initial > 0 else 0.0
            self.db.record_daily_performance(
                strategy_id=strategy.strategy_id,
                portfolio_value=portfolio_value,
                cash=strategy.capital,
                positions_value=positions_value,
                total_return_pct=return_pct,
                num_positions=len(strategy.positions),
                num_trades=0,
            )
        except Exception as exc:
            logger.warning("_record_performance failed for %s: %s", strategy.name, exc)
    

    def _get_all_positions(self, strategies):
        """Combine positions across strategies"""
        combined = {}
        for strategy in strategies:
            for symbol, shares in strategy.positions.items():
                combined[symbol] = combined.get(symbol, 0) + shares
        return combined

    def _build_local_positions(self):
        """Build local positions with qty and avg price for reconciliation."""
        local_positions = {}
        for position in self.db.get_positions():
            symbol = position['symbol']
            shares = float(position['shares'])
            avg_price = float(position['avg_price'])
            if shares <= 0:
                continue
            combined = local_positions.setdefault(symbol, {'qty': 0.0, 'avg_price': 0.0})
            total_cost = combined['avg_price'] * combined['qty'] + avg_price * shares
            combined['qty'] += shares
            combined['avg_price'] = total_cost / combined['qty'] if combined['qty'] else 0.0
        return local_positions

    def _update_position_record(self, strategy_id, symbol, shares_delta, exec_price,
                                 entry_date=None, atr=None):
        """Persist position updates for reconciliation."""
        existing = self.db.get_position(strategy_id, symbol)
        if existing:
            current_shares = float(existing['shares'])
            current_avg = float(existing['avg_price'])
        else:
            current_shares = 0.0
            current_avg = 0.0

        new_shares = current_shares + shares_delta
        if new_shares <= 0:
            self.db.delete_position(strategy_id, symbol)
            return

        if shares_delta > 0:
            total_cost = current_avg * current_shares + exec_price * shares_delta
            avg_price = total_cost / new_shares
        else:
            avg_price = current_avg

        # Only pass entry_date and atr for brand-new positions (current_shares == 0)
        is_new = shares_delta > 0 and current_shares == 0.0
        effective_entry_date = entry_date if is_new else None
        effective_atr = atr if is_new else None

        self.db.update_position(
            strategy_id=strategy_id,
            symbol=symbol,
            shares=new_shares,
            avg_price=avg_price,
            current_price=exec_price,
            entry_date=effective_entry_date,
            atr=effective_atr,
        )

    def _calculate_dynamic_allocations(self, strategies):
        """Calculate strategy allocations from recent performance"""
        performance_data = {}
        for strategy in strategies:
            history = self.db.get_strategy_performance(strategy.strategy_id, days=60)
            if history:
                values = [row['portfolio_value'] for row in reversed(history)]
                returns = []
                for idx in range(1, len(values)):
                    prev = values[idx - 1]
                    if prev:
                        returns.append((values[idx] - prev) / prev)
                performance_data[strategy.strategy_id] = returns
            else:
                performance_data[strategy.strategy_id] = []
        strategy_ids = [strategy.strategy_id for strategy in strategies]
        return self.dynamic_allocator.calculate_allocations(strategy_ids, performance_data)

    def _calculate_strategy_exposures(self, strategies, current_prices):
        """Calculate current exposure per strategy"""
        exposures = {}
        for strategy in strategies:
            exposure = 0.0
            for symbol, shares in strategy.positions.items():
                exposure += shares * current_prices.get(symbol, 0)
            exposures[strategy.strategy_id] = exposure
        return exposures

    def _apply_allocations(self, strategies, allocations, exposures):
        """Apply capital allocations to strategies and cash manager"""
        for strategy in strategies:
            allocation = allocations.get(strategy.strategy_id, strategy.capital)
            strategy.capital = max(allocation - exposures.get(strategy.strategy_id, 0), 0)
        self.cash_manager.set_allocations(allocations, exposures)

    def _format_signal_flowchart(self, strategy_name, signal):
        """Build a flowchart-style reasoning chain for a signal."""
        action = str(signal.get('action', 'BUY')).upper()
        reasoning = str(signal.get('reasoning', '')).strip()
        symbol = signal.get('symbol', 'N/A')

        news_events = []
        explicit_news_events = signal.get('news_events')
        if isinstance(explicit_news_events, list):
            news_events.extend([str(item).strip() for item in explicit_news_events if str(item).strip()])

        for key in ['news_headline', 'headline', 'article_title', 'news_summary']:
            value = signal.get(key)
            if value:
                news_events.append(str(value).strip())

        has_news_context = bool(news_events) or 'news' in strategy_name.lower()
        if not has_news_context:
            return None

        chain_parts = [f"Symbol {symbol}"]
        for event in news_events[:3]:
            chain_parts.append(f"News: {event}")

        if reasoning:
            chain_parts.append(reasoning)

        if action == 'BUY':
            chain_parts.append("Price expected to rise")
        else:
            chain_parts.append("Price expected to weaken")

        chain_parts.append(f"Signal generated ({action})")
        return " -> ".join(chain_parts)

    def build_signal_reasoning_chains(self):
        """Build reasoning chains for email reporting from generated signals."""
        if not getattr(self, 'raw_signals_by_strategy', None):
            return []

        executed_keys = {
            (str(trade.get('symbol')), str(trade.get('action', '')).upper())
            for trade in self.executed_trades
        }

        chains = []
        for strategy_name, signals in self.raw_signals_by_strategy.items():
            for signal in signals or []:
                flowchart = self._format_signal_flowchart(strategy_name, signal)
                if not flowchart:
                    continue

                symbol = str(signal.get('symbol', 'N/A'))
                action = str(signal.get('action', 'BUY')).upper()
                chains.append({
                    'strategy': strategy_name,
                    'symbol': symbol,
                    'action': action,
                    'flowchart': flowchart,
                    'executed': (symbol, action) in executed_keys,
                })

        return chains
    
    def generate_performance_report(self):
        """Generate performance report for all strategies"""
        print("\n" + "=" * 80)
        print("📊 STRATEGY PERFORMANCE DASHBOARD")
        print("=" * 80)
        
        strategies = self.db.get_all_strategies()
        
        print(f"\n{'Strategy':<25} {'Capital':<12} {'Return':<10} {'Positions':<10} {'Trades':<10}")
        print("-" * 80)
        
        for strat in strategies:
            perf = self.db.get_latest_performance(strat['id'])
            trades = self.db.get_strategy_trades(strat['id'])
            
            if perf:
                return_pct = perf.get('total_return_pct', 0)
                num_positions = perf.get('num_positions', 0)
            else:
                return_pct = 0
                num_positions = 0
            
            print(f"{strat['name']:<25} ${strat['capital_allocation']:<11,.0f} {return_pct:>+8.2f}% {num_positions:<10} {len(trades):<10}")
        
        print("-" * 80)

def main():
    """Main execution"""
    start_time = time.time()
    print("=" * 80)
    print("MULTI-STRATEGY TRADING SYSTEM")
    print("=" * 80)
    
    runner = None
    
    try:
        runner = MultiStrategyRunner()
        
        # Load market data with validation
        print("\n📊 Loading and validating market data...")
        market_data = runner.load_market_data()
        
        if market_data is None:
            error_msg = "Failed to load market data"
            logger.error(error_msg)
            if runner:
                runner.email_notifier.send_error_alert(error_msg, "\n".join(runner.errors))
            sys.exit(1)
        
        # Run all strategies
        signals = runner.run_all_strategies(market_data)
        
        # Generate report
        runner.generate_performance_report()

        pnl_metrics = runner.update_pnl_metrics()
        runner.verify_order_statuses()

        print("\n" + "=" * 80)
        print(f"✅ EXECUTION COMPLETE - {len(signals)} trades executed")
        print("=" * 80)
        
        # Send email summary
        try:
            positions = runner.trading_client.get_all_positions()
            positions_data = [
                {
                    'symbol': p.symbol,
                    'shares': float(p.qty),
                    'entry_price': float(p.avg_entry_price),
                    'current_price': float(p.current_price),
                }
                for p in positions
            ]
            
            runner.email_notifier.send_daily_summary(
                trades=runner.executed_trades,
                positions=positions_data,
                portfolio_value=runner.portfolio_value,
                cash=runner.cash_available,
                errors=runner.errors if runner.errors else None,
                signal_reasoning_chains=runner.build_signal_reasoning_chains(),
            )
            logger.info("Email summary sent successfully")
        except Exception as e:
            logger.error(f"Failed to send email summary: {e}")

        try:
            writer = DailyArtifactWriter()
            latest_date = market_data.index.max()
            data_freshness_hours = (datetime.now() - latest_date).total_seconds() / 3600
            data_freshness = f"{data_freshness_hours:.1f}h old"
            regime = runner.regime_detector.get_status(market_data)
            warnings = []
            if runner.pending_orders:
                warnings.append(
                    f"{len(runner.pending_orders)} orders pending confirmation"
                )
            portfolio_heat = 0.0
            if runner.portfolio_value > 0:
                total_exposure = sum(
                    pos['shares'] * pos['current_price'] for pos in positions_data
                )
                portfolio_heat = (total_exposure / runner.portfolio_value) * 100

            # Paper trading validation: write daily snapshot
            try:
                import json as _json
                _alloc_json = _json.dumps({
                    str(s.strategy_id): round(getattr(s, 'capital', 0), 2)
                    for s in runner.strategies_cache if hasattr(s, 'capital')
                }) if hasattr(runner, 'strategies_cache') else None
                runner.db.log_daily_snapshot(
                    run_id=runner.run_id,
                    portfolio_value=runner.portfolio_value,
                    cash=runner.cash_available,
                    positions_value=total_exposure,
                    heat_pct=portfolio_heat,
                    vix=regime.get('vix'),
                    regime=f"{regime.get('volatility_regime','?')}/{regime.get('trend_regime','?')}",
                    allocation_json=_alloc_json,
                )
                logger.info("Daily portfolio snapshot recorded")
            except Exception as _snap_exc:
                logger.warning("log_daily_snapshot failed: %s", _snap_exc)

            placed_orders = [
                {
                    'symbol': trade['symbol'],
                    'side': trade['action'],
                    'qty': trade['shares'],
                    'price': trade['price']
                }
                for trade in runner.executed_trades
            ]
            open_positions = [
                {
                    'symbol': pos['symbol'],
                    'qty': pos['shares'],
                    'avg_price': pos['entry_price'],
                    'market_value': pos['shares'] * pos['current_price'],
                    'unrealized_pl': (pos['current_price'] - pos['entry_price']) * pos['shares'],
                    'exposure_pct': (pos['shares'] * pos['current_price'] / runner.portfolio_value * 100)
                    if runner.portfolio_value > 0 else 0
                }
                for pos in positions_data
            ]

            artifact = create_artifact_data(
                vix=regime.get('vix', 0),
                regime_classification=regime.get('volatility_regime', 'UNKNOWN'),
                raw_signals=runner.raw_signals_by_strategy,
                rejected_signals=[],
                executed_signals=runner.executed_signals,
                placed_orders=placed_orders,
                filled_orders=runner.confirmed_fills,
                rejected_orders=runner.rejected_orders,
                portfolio_heat=portfolio_heat,
                daily_pnl=pnl_metrics['daily_pnl'],
                cumulative_pnl=pnl_metrics['cumulative_pnl'],
                drawdown=pnl_metrics['drawdown'],
                max_drawdown=pnl_metrics['max_drawdown'],
                circuit_breaker_state="ACTIVE" if runner.portfolio_risk.trading_halted else "INACTIVE",
                open_positions=open_positions,
                runtime_seconds=time.time() - start_time,
                data_freshness=data_freshness,
                errors=runner.errors,
                warnings=warnings,
                reconciliation_status=runner.reconciliation_status,
                portfolio_value=runner.portfolio_value,
                cash=runner.cash_available,
            )
            artifact['system_health']['reconciliation_discrepancies'] = runner.reconciliation_discrepancies
            writer.write_daily_artifact(datetime.now().strftime('%Y-%m-%d'), artifact)
        except Exception as e:
            logger.error(f"Failed to write daily artifact: {e}")

        logger.info("Multi-strategy execution completed successfully")
        
    except Exception as e:
        error_msg = f"Fatal error: {e}"
        logger.error(error_msg, exc_info=True)
        print(f"\n❌ FATAL ERROR: {e}")
        
        # Send error alert
        if runner:
            try:
                import traceback
                runner.email_notifier.send_error_alert(error_msg, traceback.format_exc())
            except:
                pass
        
        sys.exit(1)

if __name__ == "__main__":
    main()
