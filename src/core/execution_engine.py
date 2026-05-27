#!/usr/bin/env python3
"""
Multi-Strategy Trading System - Main Execution
Runs all strategies independently with separate tracking per strategy
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

from src.core.database import TradingDatabase
from src.data.data_quality_checker import DataQualityChecker
from src.data.data_validator import DataValidator
from src.data.universe_provider import UniverseProvider
from src.integration.cash_manager import CashManager
from src.integration.dry_run_wrapper import get_dry_run_wrapper
from src.integration.pending_signals_manager import PendingSignalsManager
from src.monitoring.artifact_writer import DailyArtifactWriter, create_artifact_data
from src.monitoring.daily_strategy_weights import (
    apply_strategy_weight_to_signals,
    compute_strategy_weights,
)
from src.monitoring.performance_metrics import PerformanceMetrics
from src.monitoring.pnl_calculator import PnLCalculator
from src.monitoring.signal_funnel_tracker import SignalFunnelTracker
from src.monitoring.strategy_health_scorer import StrategyHealthScorer
from src.regime.dynamic_allocator import DynamicAllocator
from src.regime.regime_detector import RegimeDetector
from src.risk.broker_reconciler import BrokerReconciler
from src.risk.correlation_filter import CorrelationFilter
from src.risk.drawdown_stop_manager import DrawdownStopManager
from src.risk.portfolio_risk_manager import PortfolioRiskManager
from src.strategies.strategy_earnings_drift import EarningsDriftStrategy
from src.strategies.strategy_factor_momentum import _SECTOR_MAP, FactorMomentumStrategy
from src.strategies.strategy_ma_crossover import MACrossoverStrategy
from src.strategies.strategy_ml_momentum import MLMomentumStrategy
from src.strategies.strategy_news_sentiment import NewsSentimentStrategy
from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from src.strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy
from src.utils.config_loader import get_config

# Import new modules for professional-grade system
from src.utils.email_notifier import EmailNotifier
from src.utils.execution_costs import ExecutionCostModel
from src.utils.kill_switch_service import KillSwitchService
from src.utils.news_sentiment import NewsSignalFilter
from src.utils.structured_logger import StructuredLogger

# Setup logging - CRITICAL FIX: Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/multi_strategy.log"), logging.StreamHandler()],
    force=True,
)
logger = logging.getLogger(__name__)

CANONICAL_STRATEGY_SPECS = [
    (
        "RSI Mean Reversion",
        "Buy when RSI < 30 + low volatility, hold 20 days",
        RSIMeanReversionStrategy,
    ),
    (
        "ML Momentum",
        "GradientBoosting 12-feature classifier predicting 5d return",
        MLMomentumStrategy,
    ),
    (
        "Earnings Drift",
        "Post-earnings announcement drift via volume spike detection",
        EarningsDriftStrategy,
    ),
    (
        "Factor Momentum",
        "Cross-sectional factor ranking: momentum+quality+reversion",
        FactorMomentumStrategy,
    ),
    (
        "News Sentiment",
        "Buy on positive news sentiment score (Google News RSS + VADER), exit when sentiment sours",
        NewsSentimentStrategy,
    ),
    (
        "MA Crossover",
        "Golden/death cross on SMA-20/50 with ADX trend filter and volume confirmation",
        MACrossoverStrategy,
    ),
    (
        "Volatility Breakout",
        "Bollinger Band upper breakout with 1.5x volume surge confirmation",
        VolatilityBreakoutStrategy,
    ),
]


class MultiStrategyRunner:
    """Runs all 7 canonical strategies with independent tracking"""

    def __init__(self):
        # Load configuration
        self.config = get_config()
        logger.info("Configuration loaded from YAML")

        self.db = TradingDatabase(db_path="trading.db")
        self.run_id = self.db.run_id
        self.asof_date = datetime.now().strftime("%Y-%m-%d")
        self.db.upsert_run_state(
            stage="INIT", status="RUNNING", metadata={"asof_date": self.asof_date}
        )

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
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            raise ValueError("Missing Alpaca credentials")

        self.paper_mode = os.getenv("ALPACA_PAPER", "true").lower() == "true"
        live_enabled = os.getenv("ALPACA_LIVE_ENABLED", "false").lower() == "true"
        if not self.paper_mode and not live_enabled:
            raise ValueError("Live trading disabled. Set ALPACA_LIVE_ENABLED=true to trade live.")
        self.trading_client = TradingClient(api_key, secret_key, paper=self.paper_mode)

        # VALIDATION MODE: Signal injection for testing
        self.signal_injection_enabled = os.getenv("SIGNAL_INJECTION", "false").lower() == "true"
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
        self.buying_power = float(getattr(account, "buying_power", self.cash_available))

        logger.info(
            "Portfolio: $%.2f, Cash: $%.2f, Buying Power: $%.2f",
            self.portfolio_value,
            self.cash_available,
            self.buying_power,
        )

        # Initialize professional-grade modules with config
        self.email_notifier = EmailNotifier(outbox_writer=self.db.enqueue_notification)
        self.data_validator = DataValidator()
        total_capital = max(self.portfolio_value, self.buying_power)
        self.cash_manager = CashManager(total_capital, num_strategies=len(CANONICAL_STRATEGY_SPECS))

        # Portfolio risk manager - load from config
        max_heat = self.config.get("risk.max_portfolio_heat", 0.30)
        max_daily_loss = self.config.get("risk.max_daily_loss_pct", 0.02)
        self.portfolio_risk = PortfolioRiskManager(
            max_portfolio_heat=max_heat, max_daily_loss_pct=max_daily_loss
        )
        self.portfolio_risk.daily_start_value = self.portfolio_value
        logger.info(
            f"Portfolio Risk Manager: max_heat={max_heat:.1%}, max_daily_loss={max_daily_loss:.1%}"
        )

        # Correlation filter - load from config
        corr_window = self.config.get("risk.correlation_window", 60)
        corr_short_window = self.config.get("risk.correlation_short_window", 20)
        max_corr = self.config.get("risk.max_correlation", 0.70)
        self.correlation_filter = CorrelationFilter(
            correlation_window=corr_window, short_window=corr_short_window, max_correlation=max_corr
        )
        logger.info(
            f"Correlation Filter: window={corr_window}, short={corr_short_window}, max={max_corr}"
        )

        self.regime_detector = RegimeDetector()
        self.dynamic_allocator = DynamicAllocator(
            total_capital,
            max_allocation_pct=self.config.get("risk.dynamic_max_allocation_pct", 0.35),
            min_allocation_pct=self.config.get("risk.dynamic_min_allocation_pct", 0.10),
        )
        slippage_bps = self.config.get("execution.slippage_bps", 5)
        commission = self.config.get("execution.commission_per_share", 0.0)
        self.cost_model = ExecutionCostModel(
            slippage_bps=slippage_bps, commission_per_share=commission
        )
        logger.info(f"Execution costs: {slippage_bps}bps slippage, ${commission}/share commission")
        self.performance_metrics = PerformanceMetrics()
        self.broker_reconciler = BrokerReconciler(email_notifier=self.email_notifier)

        # Initialize stop loss manager - load from config
        stop_loss_multiplier = self.config.get("risk.stop_loss_atr_multiplier", 2.5)
        breakeven_atr = self.config.get("risk.trailing_breakeven_atr", 1.0)
        lock_atr = self.config.get("risk.trailing_lock_atr", 2.0)
        from src.risk.stop_loss_manager import StopLossManager

        self.stop_loss_manager = StopLossManager(
            atr_multiplier=stop_loss_multiplier,
            breakeven_atr=breakeven_atr,
            lock_atr=lock_atr,
        )
        # Cached current regime-adjusted multiplier (refreshed per run)
        self._current_stop_multiplier = stop_loss_multiplier
        logger.info(
            f"Stop Loss Manager initialized: {stop_loss_multiplier}x ATR base, "
            f"ratchet at +{breakeven_atr}×ATR → entry, +{lock_atr}×ATR → entry+1×ATR"
        )

        # Initialize production-readiness modules
        self.kill_switch = KillSwitchService(self.db, self.email_notifier)
        self.funnel_tracker = SignalFunnelTracker(self.db)
        self.universe_provider = UniverseProvider()

        # Pending signals - load decay from config
        decay_days = self.config.get("monitoring.signal_decay_days", 3)
        self.pending_signals = PendingSignalsManager(self.db, decay_days=decay_days)
        self.structured_logger = StructuredLogger(self.run_id)
        logger.info(
            "Production-readiness modules initialized: kill switches, funnel tracking, universe provider, pending signals, structured logging"
        )

        # Initialize live trading safety modules - load from config
        halt_threshold = self.config.get("risk.drawdown_halt_threshold", 0.08)
        panic_threshold = self.config.get("risk.drawdown_panic_threshold", 0.10)
        self.drawdown_manager = DrawdownStopManager(
            self.db,
            self.email_notifier,
            halt_threshold=halt_threshold,
            panic_threshold=panic_threshold,
        )
        logger.info(f"Drawdown Manager: halt={halt_threshold:.1%}, panic={panic_threshold:.1%}")

        self.data_quality_checker = DataQualityChecker()
        self.dry_run = get_dry_run_wrapper()
        self.health_scorer = StrategyHealthScorer(self.db)
        self.pnl_calculator = PnLCalculator(self.db)
        logger.info(
            "Live trading safety modules initialized: drawdown stop, data quality, DRY_RUN mode, health scoring, P&L calculator"
        )

        # Track blocked symbols from data quality checks
        self.blocked_symbols = set()
        self.data_quality_report = {}

        # Set daily start value for risk management
        self.portfolio_risk.set_daily_start_value(self.portfolio_value)

        # PDT guardrail tracking
        self._day_trades_today: list = []
        self._day_trade_count: int = 0

        # Track errors and executed trades for email reporting
        self.errors = []
        self.executed_trades = []
        self.confirmed_fills = []  # Track confirmed fills from Alpaca
        self.pending_orders = []  # Track pending orders from Alpaca
        self.rejected_orders = []  # Track rejected/canceled orders from Alpaca
        self.alpha_vantage_usage: dict = {}

        # Track P&L metrics
        self.initial_portfolio_value = self.portfolio_value
        self.peak_portfolio_value = self._get_peak_portfolio_value()
        _cpnl = self.db.get_system_state("cumulative_pnl")
        self.cumulative_pnl = float(_cpnl) if _cpnl else 0.0
        _mdd = self.db.get_system_state("max_drawdown")
        self.max_drawdown = float(_mdd) if _mdd else 0.0

        # Initialize reconciliation state so finally block never hits AttributeError
        self.reconciliation_status = "UNKNOWN"
        self.reconciliation_discrepancies = []
        self.strategies_cache: list = []

    def _set_run_stage(
        self,
        stage: str,
        status: str,
        error_message: str = None,
        metadata: dict = None,
        completed: bool = False,
    ):
        """Persist run state machine updates for observability and recovery."""
        try:
            self.db.upsert_run_state(
                stage=stage,
                status=status,
                error_message=error_message,
                metadata=metadata,
                completed=completed,
            )
        except Exception as exc:
            logger.warning("Failed to persist run stage %s/%s: %s", stage, status, exc)

    def execute_pipeline(self, market_data):
        """Run staged trading pipeline and return execution outputs."""
        self._set_run_stage("TRADING", "RUNNING")
        try:
            signals = self.run_all_strategies(market_data)
            self._set_run_stage("TRADING", "SUCCESS", metadata={"signals": len(signals)})
        except Exception as exc:
            self._set_run_stage("TRADING", "FAILED", error_message=str(exc))
            raise

        self._set_run_stage("REPORTING", "RUNNING")
        try:
            self.generate_performance_report()
            pnl_metrics = self.update_pnl_metrics()
            self.verify_order_statuses()
            self._set_run_stage("REPORTING", "SUCCESS")
            return signals, pnl_metrics
        except Exception as exc:
            self._set_run_stage("REPORTING", "FAILED", error_message=str(exc))
            raise

    def emit_slo_metrics(self, start_time: float, signals: list, pnl_metrics: dict):
        """Compute and persist per-run service-level observability metrics."""
        total_signals, with_terminal = self.db.verify_terminal_states(self.run_id)
        runtime_seconds = round(time.time() - start_time, 3)
        metrics = {
            "runtime_seconds": runtime_seconds,
            "signals_total": int(total_signals),
            "signals_terminalized": int(with_terminal),
            "signals_terminalized_pct": (
                round((with_terminal / total_signals) * 100.0, 2) if total_signals else 100.0
            ),
            "executed_trades_count": len(self.executed_trades),
            "confirmed_fills_count": len(self.confirmed_fills),
            "rejected_orders_count": len(self.rejected_orders),
            "pending_orders_count": len(self.pending_orders),
            "error_count": len(self.errors),
            "reconciliation_status": self.reconciliation_status,
            "drawdown": pnl_metrics.get("drawdown", 0.0),
            "max_drawdown": pnl_metrics.get("max_drawdown", 0.0),
            "daily_pnl": pnl_metrics.get("daily_pnl", 0.0),
            "cumulative_pnl": pnl_metrics.get("cumulative_pnl", 0.0),
            "run_id": self.run_id,
        }
        self.db.save_run_slo_metrics(metrics)
        return metrics

    def _refresh_account_values(self):
        """Refresh account values from Alpaca."""
        account = self.trading_client.get_account()
        self.portfolio_value = float(account.portfolio_value)
        self.cash_available = float(account.cash)
        self.buying_power = float(getattr(account, "buying_power", self.cash_available))
        return account

    def _refresh_account_state(self):
        """Alias for compatibility"""
        return self._refresh_account_values()

    def _cancel_stale_orders(self):
        """Cancel all open orders left over from previous runs.

        OPG orders placed during a prior run that did not fill (e.g. the run
        happened twice in one session, or a position was closed since the order
        was created) must be removed before new orders are submitted.  Without
        this, duplicate BUY orders accumulate across days.
        """
        try:
            open_orders = self.trading_client.get_orders()
            if not open_orders:
                logger.info("No stale orders to cancel")
                return
            cancelled = 0
            for order in open_orders:
                try:
                    self.trading_client.cancel_order_by_id(order.id)
                    cancelled += 1
                    logger.info(
                        f"Cancelled stale order: {order.symbol} {order.side} {order.qty} ({order.id})"
                    )
                except Exception as cancel_err:
                    logger.warning(f"Could not cancel order {order.id}: {cancel_err}")
            logger.info(f"Cancelled {cancelled}/{len(open_orders)} stale open orders")
        except Exception as exc:
            logger.warning(f"Stale order cleanup failed (non-fatal): {exc}")

    def _get_peak_portfolio_value(self):
        """Get peak portfolio value from database or current value."""
        peak_str = self.db.get_system_state("peak_portfolio_value")
        if peak_str:
            try:
                return float(peak_str)
            except:
                pass
        return self.portfolio_value

    def _save_peak_portfolio_value(self, peak_value):
        """Save peak portfolio value to database."""
        self.db.set_system_state("peak_portfolio_value", str(peak_value))

    def _get_last_close_map(self, market_data) -> dict:
        """Extract last close price per symbol from market_data DataFrame"""
        import pandas as pd

        try:
            if "symbol" in market_data.columns and "close" in market_data.columns:
                last = market_data.sort_index().groupby("symbol")["close"].last()
                return last.dropna().astype(float).to_dict()
            if isinstance(market_data.index, pd.MultiIndex) and "close" in market_data.columns:
                sym_level = (
                    "symbol" if "symbol" in market_data.index.names else market_data.index.names[-1]
                )
                last = (
                    market_data.reset_index()
                    .sort_values(market_data.index.names[0])
                    .groupby(sym_level)["close"]
                    .last()
                )
                return last.dropna().astype(float).to_dict()
            if isinstance(market_data.columns, pd.MultiIndex):
                if "close" in market_data.columns.get_level_values(0):
                    close_df = market_data["close"]
                    last = close_df.iloc[-1]
                    return last.dropna().astype(float).to_dict()
                elif "close" in market_data.columns.get_level_values(1):
                    close_df = market_data.xs("close", axis=1, level=1)
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
            drawdown = (
                (self.peak_portfolio_value - final_portfolio_value) / self.peak_portfolio_value
            ) * 100

        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

        self.db.set_system_state("cumulative_pnl", str(self.cumulative_pnl))
        self.db.set_system_state("max_drawdown", str(self.max_drawdown))

        return {
            "final_portfolio_value": final_portfolio_value,
            "daily_pnl": daily_pnl,
            "cumulative_pnl": self.cumulative_pnl,
            "drawdown": drawdown,
            "max_drawdown": self.max_drawdown,
        }

    def verify_order_statuses(self):
        """Verify order status with Alpaca and track confirmed fills.

        For paper-mode OPG orders: the fill was optimistically recorded at submission
        time (intent already marked FILLED).  We treat those as confirmed fills without
        re-polling Alpaca, which would always return 'new' since OPG executes at the
        next morning's open — hours after this method runs.
        """
        self.confirmed_fills = []
        self.pending_orders = []
        self.rejected_orders = []

        for trade in self.executed_trades:
            order_id = trade.get("order_id")
            order_id_str = str(order_id) if order_id is not None else None
            intent_id = trade.get("intent_id")
            if not order_id:
                self.pending_orders.append({**trade, "status": "UNKNOWN"})
                continue

            # If we already marked this intent FILLED optimistically (paper OPG path),
            # trust that record rather than re-polling Alpaca and downgrading to ACKED.
            if intent_id and self.paper_mode:
                existing = self.db.get_order_intent_by_id(intent_id)
                if existing and existing.get("status") == "FILLED":
                    self.confirmed_fills.append(trade)
                    continue

            try:
                order = self.trading_client.get_order_by_id(order_id)
                status = str(getattr(order, "status", "UNKNOWN")).lower()
                if status == "filled":
                    self.confirmed_fills.append(trade)
                    if intent_id:
                        self.db.update_order_intent_status(
                            intent_id, "FILLED", broker_order_id=order_id_str
                        )
                elif status in {"canceled", "rejected", "expired"}:
                    self.rejected_orders.append({**trade, "status": status})
                    if intent_id:
                        self.db.update_order_intent_status(
                            intent_id, "FAILED", broker_order_id=order_id_str, error=status
                        )
                else:
                    self.pending_orders.append({**trade, "status": status})
                    if intent_id:
                        self.db.update_order_intent_status(
                            intent_id, "ACKED", broker_order_id=order_id_str
                        )
            except Exception as exc:
                logger.error(f"Failed to verify order {order_id}: {exc}")
                self.pending_orders.append({**trade, "status": "ERROR"})
                if intent_id:
                    self.db.update_order_intent_status(
                        intent_id,
                        "FAILED",
                        broker_order_id=order_id_str,
                        error="status_check_failed",
                    )

        logger.info("Confirmed fills: %s/%s", len(self.confirmed_fills), len(self.executed_trades))

    def initialize_strategies(self):
        """Initialize canonical active strategies, skipping any marked disabled in config."""
        # Filter out strategies disabled via config (e.g. factor_momentum: disabled: true)
        active_specs = [
            (name, desc, cls)
            for name, desc, cls in CANONICAL_STRATEGY_SPECS
            if not self.config.get(f"strategies.{name.lower().replace(' ', '_')}.disabled", False)
        ]
        active_names = {name for name, _, _ in active_specs}
        disabled_names = [
            name for name, _, _ in CANONICAL_STRATEGY_SPECS if name not in active_names
        ]
        if disabled_names:
            logger.warning("Disabled strategies (config): %s", disabled_names)

        # Equal capital normalization: each active strategy gets an equal share of
        # deployed_capital_pct * portfolio_value so strategies are directly comparable.
        deployed_pct = self.config.get("strategies.deployed_capital_pct", 0.85)
        deployed_capital = self.portfolio_value * deployed_pct
        capital_per_strategy = deployed_capital / max(len(active_specs), 1)
        logger.info(
            "Capital normalization: portfolio=$%.2f deployed_pct=%.0f%% "
            "deployed=$%.2f per_strategy=$%.2f (n=%d)",
            self.portfolio_value,
            deployed_pct * 100,
            deployed_capital,
            capital_per_strategy,
            len(active_specs),
        )

        # Build a name→id lookup from whatever is already in the DB
        existing_by_name = {s["name"]: s for s in self.db.get_all_strategies()}
        logger.info(
            f"DB has {len(existing_by_name)} strategies: {list(existing_by_name.keys())}. "
            f"Active: {[n for n, _, _ in active_specs]}"
        )

        strategies = []
        for name, desc, strategy_class in active_specs:
            if name in existing_by_name:
                strategy_id = existing_by_name[name]["id"]
                # Normalize capital allocation each run so all strategies stay equal
                self.db.update_strategy_capital_allocation(strategy_id, capital_per_strategy)
                logger.info(
                    f"  Loaded existing: {name} (ID: {strategy_id}, Capital updated: ${capital_per_strategy:.2f})"
                )
            else:
                strategy_id = self.db.create_strategy(name, desc, capital_per_strategy)
                logger.info(
                    f"  Created new: {name} (ID: {strategy_id}, Capital: ${capital_per_strategy:.2f})"
                )

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
                symbol = position["symbol"]
                shares = float(position["shares"])
                if shares > 0:
                    positions[symbol] = shares
                    entry_dates[symbol] = position.get("entry_date") or position.get("last_updated")
                    avg_price = position.get("avg_price") or position.get("entry_price")
                    if avg_price:
                        entry_prices[symbol] = float(avg_price)

            strategy.positions = positions
            strategy.entry_dates = entry_dates
            strategy.entry_prices = entry_prices
            logger.info(f"  Loaded {len(positions)} positions for {strategy.name}")

            # Restore partial-exit state so cross-run tranche logic is consistent.
            for sym in list(positions.keys()):
                key = f"partial_exit_{strategy.strategy_id}_{sym}"
                if self.db.get_system_state(key) == "1":
                    strategy._partial_exit_done.add(sym)
                    logger.debug("  Partial exit already done for %s (%s)", sym, strategy.name)

            # Re-initialize stop losses for carried positions — stop_levels is
            # in-memory only and is empty at every startup, so without this all
            # multi-day positions run with zero downside protection.
            for position in self.db.get_positions(strategy.strategy_id):
                symbol = position["symbol"]
                if float(position.get("shares", 0)) <= 0:
                    continue
                avg_price = float(position.get("avg_price") or position.get("entry_price") or 0)
                if avg_price <= 0:
                    continue
                atr = float(position.get("atr") or 0)
                if atr <= 0:
                    # Fallback: use 3% of price as ATR proxy
                    atr = avg_price * 0.03
                    logger.warning(f"  No ATR stored for {symbol}, using 3% fallback for stop loss")
                self.stop_loss_manager.set_stop_loss(
                    symbol,
                    avg_price,
                    atr,
                    multiplier=getattr(self, "_current_stop_multiplier", None),
                )
                logger.info(f"  Re-initialized stop loss for carried position {symbol}")
        except Exception as e:
            strategy_name = getattr(strategy, "name", "Unknown")
            logger.error(f"Error loading positions for {strategy_name}: {e}")
            strategy.positions = {}
            strategy.entry_dates = {}

    def _create_strategy_instance(self, strategy_id, name, capital):
        """Create strategy instance by name; returns None for unknown names."""
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

    def _collect_strategy_health(self, strategies):
        """Collect a lightweight health snapshot for strategy weighting."""
        health_by_strategy = {}
        for strategy in strategies:
            try:
                health_by_strategy[strategy.name] = self.health_scorer.calculate_strategy_health(
                    strategy.strategy_id,
                    strategy.name,
                )
            except Exception as exc:
                logger.warning("Health scoring unavailable for %s: %s", strategy.name, exc)
                health_by_strategy[strategy.name] = {}
        return health_by_strategy

    def _compute_trailing_sharpe(self, strategies, window_days: int = 30) -> dict:
        """Compute trailing Sharpe per strategy from realized trade-level P&L.

        Uses trade_pnl_detail (matched buy→sell gross_pnl_pct) rather than
        portfolio snapshots.  Snapshots are equal-capital for all strategies
        when no fills occur, producing an identical and meaningless Sharpe for
        every strategy.  Trade returns are zero for strategies with no closed
        trades (correctly yielding no entry) and reflect actual win/loss mix
        otherwise.
        """
        import numpy as _np

        sharpe_by_strategy = {}
        for strategy in strategies:
            try:
                returns = self.db.get_strategy_trade_returns(strategy.strategy_id, days=window_days)
                if len(returns) < 3:
                    continue
                arr = _np.array(returns)
                mean_r = _np.mean(arr)
                std_r = _np.std(arr, ddof=1)
                if std_r > 0:
                    # Annualise assuming ~252 trading days; trade returns are
                    # per-trade not per-day but this preserves the relative ranking.
                    sharpe = (mean_r / std_r) * (_np.sqrt(252))
                    sharpe_by_strategy[strategy.name] = round(float(sharpe), 3)
            except Exception as exc:
                logger.debug("Trailing Sharpe unavailable for %s: %s", strategy.name, exc)
        return sharpe_by_strategy

    def _compute_kelly_weights(
        self, strategies, min_trades: int = 20, fraction: float = 0.25
    ) -> dict[str, float]:
        """Compute fractional Kelly multipliers per strategy.

        f* = p - (1-p)/b  where b = avg_win / avg_loss (in % terms)
        Applied at `fraction` x Kelly (default 0.25x = quarter-Kelly) to cap volatility.
        Gate: only activates when strategy has >= min_trades closed trades.
        Returns weight in [0.5, 1.5]; neutral 1.0 for strategies below the trade gate.
        """
        kelly_weights: dict[str, float] = {}
        for strategy in strategies:
            stats = self.db.get_strategy_pnl_stats(strategy.strategy_id)
            n = stats.get("trades", 0)
            if n < min_trades:
                kelly_weights[strategy.name] = 1.0
                logger.debug(
                    "Kelly gated for %s: only %d closed trades (need %d)",
                    strategy.name,
                    n,
                    min_trades,
                )
                continue
            p = stats["win_rate"]
            avg_win = stats["avg_win_pct"] or 0.0
            avg_loss = stats["avg_loss_pct"] or 1e-9  # avoid div/0
            b = avg_win / avg_loss
            f_star = p - (1 - p) / b
            # Clamp Kelly fraction and convert to a position-sizing multiplier around 1.0
            f_capped = max(0.0, min(f_star * fraction, 0.5))  # quarter-Kelly, max +50%
            mult = round(1.0 + f_capped, 3)  # e.g. f*=0.3 → mult=1.075
            kelly_weights[strategy.name] = max(0.5, min(1.5, mult))
            logger.info(
                "Kelly(%s): n=%d p=%.2f b=%.2f f*=%.3f → mult=%.3f",
                strategy.name,
                n,
                p,
                b,
                f_star,
                kelly_weights[strategy.name],
            )
        return kelly_weights

    def _maybe_refresh_earnings_calendar(self):
        """Auto-refresh the earnings calendar CSV if it is older than 7 days."""
        cal_path = project_root / "data" / "earnings_calendar.csv"
        if cal_path.exists():
            age_days = (pd.Timestamp.now() - pd.Timestamp(cal_path.stat().st_mtime, unit="s")).days
            if age_days <= 7:
                return
        logger.info("Earnings calendar is stale — auto-refreshing...")
        try:
            import subprocess

            result = subprocess.run(
                ["python3", str(project_root / "scripts" / "update_earnings_calendar.py")],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                logger.info("Earnings calendar refreshed successfully")
            else:
                logger.warning("Earnings calendar refresh failed: %s", result.stderr[:300])
        except Exception as exc:
            logger.warning("Earnings calendar auto-refresh error: %s", exc)

    def _submit_covered_calls(self, symbol: str, shares: int, current_price: float):
        """Stub: submit a 30-day covered call on a long position (live trading only).

        For each long equity position, this would sell a ~30-delta call with a strike
        ~5% above current price.  Generates ~1% monthly income while the trade matures.

        Not enabled in paper mode — options trading requires separate Alpaca approval
        and a different order endpoint (OptionOrderRequest).  Uncomment and wire in once
        live options permissions are confirmed.
        """
        if self.paper_mode:
            return
        logger.info(
            "Covered call opportunity: %s (%d shares @ $%.2f) — "
            "enable options trading in Alpaca to activate",
            symbol,
            shares,
            current_price,
        )

    def load_market_data(self):
        """Load market data from CSV"""
        data_file = project_root / "data" / "training_data.csv"

        if not data_file.exists():
            logger.error(f"Data file not found: {data_file}")
            return None

        # Allow configurable max age for automated runs (weekends/holidays)
        max_age_hours = int(
            os.getenv("DATA_MAX_AGE_HOURS", os.getenv("DATA_VALIDATOR_MAX_AGE_HOURS", "24"))
        )
        validator = DataValidator(max_age_hours=max_age_hours)
        is_valid, errors = validator.validate_data_file(data_file)
        if not is_valid:
            auto_update = os.getenv("AUTO_UPDATE_DATA", "false").lower() == "true"
            if auto_update:
                logger.warning("Data validation failed; attempting auto-update.")
                try:
                    import subprocess

                    result = subprocess.run(
                        ["python3", str(project_root / "scripts" / "update_daily_data.py")],
                        capture_output=True,
                        text=True,
                        timeout=300,
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
            logger.warning(
                f"⚠️  DATA IS STALE: {data_age_days} days old (latest: {latest_date.date()})"
            )
            logger.warning("⚠️  Consider running: python3 scripts/update_daily_data.py")
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
            symbol = position["symbol"]
            strategy_id = position["strategy_id"]

            if symbol not in current_prices:
                logger.warning(f"No current price for {symbol}, skipping stop check")
                continue

            current_price = current_prices[symbol]

            # Ratchet trailing stop upward before checking — stops only move up, never down.
            # Tiered: +1×ATR profit → stop to entry; +2×ATR → stop to entry +1×ATR;
            # then chandelier extends further as the winner runs.
            atr = float(position.get("atr") or 0)
            if atr > 0:
                self.stop_loss_manager.update_ratchet_stop(symbol, current_price, atr)

            # Check if stop loss is hit
            if self.stop_loss_manager.check_stop_loss(symbol, current_price):
                stop_price = self.stop_loss_manager.get_stop_price(symbol)
                entry_price = position.get("entry_price") or 0
                stop_str = f"${stop_price:.2f}" if stop_price is not None else "N/A"
                entry_str = f"${entry_price:.2f}" if entry_price else "N/A"
                logger.warning(
                    f"CATASTROPHE STOP HIT: {symbol} at ${current_price:.2f} "
                    f"(stop: {stop_str}, entry: {entry_str})"
                )

                positions_to_close.append(
                    {
                        "symbol": symbol,
                        "strategy_id": strategy_id,
                        "shares": position["shares"],
                        "current_price": current_price,
                        "stop_price": stop_price,
                        "entry_price": entry_price,
                        "reason": "CATASTROPHE_STOP_LOSS",
                    }
                )

        return positions_to_close

    def execute_stop_loss_exits(self, positions_to_close):
        """
        Execute sell orders for positions that hit stop losses
        """
        for position in positions_to_close:
            try:
                symbol = position["symbol"]
                shares = abs(position["shares"])

                if shares <= 0:
                    logger.warning("Skipping stop-loss exit for %s: shares=%s", symbol, shares)
                    self.stop_loss_manager.remove_stop_loss(symbol)
                    continue

                # Short-prevention guard: a double-exit (stop-loss fired twice, or race
                # between stop-loss and strategy exit) would submit a SELL with 0 broker
                # shares and create a short position. Verify the DB still shows shares > 0.
                local_pos = self.db.get_position(position["strategy_id"], symbol)
                local_shares = float(local_pos["shares"]) if local_pos else 0.0
                if local_shares <= 0:
                    logger.warning(
                        f"Skipping stop-loss SELL {symbol} - DB shows {local_shares} shares "
                        "(already exited or double-exit prevented)"
                    )
                    self.stop_loss_manager.remove_stop_loss(symbol)
                    continue

                # Idempotency guard: GHA retries must not re-submit stop-loss exits
                # that already completed in a prior run (would create a short).
                existing_stop_intent = self.db.find_active_order_intent_for_today(
                    position["strategy_id"], symbol, "SELL"
                )
                if existing_stop_intent:
                    logger.warning(
                        "Idempotency guard: stop-loss SELL %s already %s today (intent %s) — skipping",
                        symbol,
                        existing_stop_intent["status"],
                        existing_stop_intent["intent_id"],
                    )
                    self.stop_loss_manager.remove_stop_loss(symbol)
                    continue
                stop_intent_id = self.db.create_order_intent(
                    position["strategy_id"], symbol, "SELL", shares
                )

                logger.info(f"Executing stop loss exit: SELL {shares} {symbol}")

                # Create market order to close position - DAY fills immediately during market hours
                order_data = MarketOrderRequest(
                    symbol=symbol, qty=shares, side=OrderSide.SELL, time_in_force=TimeInForce.DAY
                )

                order = self.dry_run.execute_broker_operation(
                    f"submit_order_stoploss_{symbol}", self.trading_client.submit_order, order_data
                )

                exit_price = position["current_price"]

                # Record the trade
                self.db.log_trade(
                    strategy_id=position["strategy_id"],
                    signal_id=None,
                    symbol=symbol,
                    action="SELL",
                    shares=shares,
                    requested_price=exit_price,
                    exec_price=exit_price,
                    slippage_cost=0.0,
                    commission_cost=0.0,
                    order_id=str(order.id),
                )

                # CRITICAL: Zero out the local DB position so reconciliation sees
                # broker=0 and DB=0 (previously this was missing, causing every
                # stop-loss to produce a guaranteed reconciliation mismatch).
                self._update_position_record(position["strategy_id"], symbol, -shares, exit_price)

                # Release cash back to the pool so other strategies see correct capacity
                exit_proceeds = exit_price * shares
                self.cash_manager.release_cash(position["strategy_id"], exit_proceeds)

                # Record matched P&L so stop-loss exits appear in win-rate and profit-factor
                entry_price_sl = float(
                    position.get("avg_price") or position.get("entry_price") or 0
                )
                if entry_price_sl > 0:
                    try:
                        self.db.log_trade_pnl(
                            strategy_id=position["strategy_id"],
                            strategy_name=position.get("strategy_name", ""),
                            symbol=symbol,
                            sell_run_id=self.run_id,
                            entry_price=entry_price_sl,
                            exit_price=exit_price,
                            shares=shares,
                            exit_reason="STOP_LOSS",
                        )
                    except Exception as _sl_pnl_exc:
                        logger.warning(
                            "log_trade_pnl failed for stop-loss %s: %s", symbol, _sl_pnl_exc
                        )

                # Remove stop loss tracking
                self.stop_loss_manager.remove_stop_loss(symbol)

                try:
                    self.db.update_order_intent_status(
                        stop_intent_id, "FILLED", broker_order_id=str(order.id)
                    )
                except Exception as _ie:
                    logger.warning("Failed to update stop-loss intent status: %s", _ie)

                logger.info(f"Stop loss exit executed: {symbol} order {order.id}")

            except Exception as e:
                logger.error(f"Error executing stop loss exit for {symbol}: {e}")
                self.errors.append(f"Stop loss exit failed for {symbol}: {e}")

    def _get_symbols_reporting_tomorrow(self) -> set:
        """Return set of symbols with earnings in the next 1 trading day."""
        cal_path = Path("data/earnings_calendar.csv")
        if not cal_path.exists():
            return set()
        try:
            cal = pd.read_csv(cal_path)
            cal["reportDate"] = pd.to_datetime(cal["reportDate"], errors="coerce")
            tomorrow = (pd.Timestamp.today() + pd.Timedelta(days=1)).normalize()
            return set(cal[cal["reportDate"] == tomorrow]["symbol"].dropna().str.upper())
        except Exception as e:
            logger.warning(f"Could not load earnings calendar for pre-earnings check: {e}")
            return set()

    def run_all_strategies(self, market_data):
        """Run all strategies and execute trades"""
        strategies = self.initialize_strategies()
        self.strategies_cache = strategies
        self.raw_signals_by_strategy = {}

        # CRITICAL: Check kill switches BEFORE any trading
        logger.info("=" * 80)
        logger.info("CHECKING KILL SWITCHES")
        logger.info("=" * 80)

        kill_context = {
            "reconciliation_status": "UNKNOWN",
            "daily_drawdown": abs(float(self.max_drawdown or 0.0)),
            "consecutive_failures": self.db.get_consecutive_failed_runs(),
            "rejected_orders_count": 0,
            "total_orders": 0,
        }

        if not self.kill_switch.check_all_switches(kill_context):
            logger.critical("Trading halted by kill switch")
            self.errors.append(
                "Trading halted by kill switch: " + ", ".join(self.kill_switch.kill_reasons)
            )
            self.structured_logger.log_kill_switch(
                reason=", ".join(self.kill_switch.kill_reasons), details={"context": kill_context}
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
            peak_portfolio_value=self.peak_portfolio_value,
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

        # Cancel any stale open orders from previous runs before placing new ones.
        # OPG orders placed last session and not filled (e.g. market was closed, duplicate run)
        # must be cancelled so we don't accumulate conflicting order intent.
        self._cancel_stale_orders()

        # CRITICAL: Check data quality BEFORE trading
        logger.info("=" * 80)
        logger.info("CHECKING DATA QUALITY")
        logger.info("=" * 80)

        (
            self.blocked_symbols,
            self.data_quality_report,
        ) = self.data_quality_checker.check_data_quality(market_data, datetime.now())

        if self.blocked_symbols:
            logger.warning(f"Data quality: {len(self.blocked_symbols)} symbols blocked")
            # Filter market_data to exclude blocked symbols
            market_data = market_data[~market_data["symbol"].isin(self.blocked_symbols)]
            logger.info(
                f"Filtered market data: {len(market_data['symbol'].unique())} symbols remaining"
            )
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
        self.rejected_signals = []
        self.symbols_bought_this_run: set = set()
        self.symbols_sold_this_run: set = set()
        self.reconciliation_status = "SKIPPED"
        # Snapshot of all held symbols at run start — used by cross-strategy dedup guard.
        # Updated in-memory as BUYs execute so subsequent strategies see fresh state.
        self._held_symbols: set = {p["symbol"] for p in self.db.get_all_open_positions()}

        # Pre-fetch news sentiment once per run for all signal symbols
        self._news_filter = NewsSignalFilter()
        self._news_sentiment_map: dict = {}
        self.alpha_vantage_usage = self._news_filter.get_usage_summary()
        self.reconciliation_discrepancies = []
        # Pre-earnings: symbols reporting tomorrow — block new BUY entries
        self._reporting_tomorrow: set = self._get_symbols_reporting_tomorrow()
        if self._reporting_tomorrow:
            logger.info(
                f"Pre-earnings guard active for {len(self._reporting_tomorrow)} symbol(s): "
                f"{sorted(self._reporting_tomorrow)}"
            )

        # ML risk-off pre-scan: generate ML signals once before the main loop so the
        # risk-off flag is available to RSI / Factor strategies that run before ML.
        self._ml_risk_off: bool = False
        self._ml_signals_cache = None
        ml_strategy = next((s for s in strategies if "ml" in s.name.lower()), None)
        if ml_strategy is not None:
            try:
                ml_pre = ml_strategy.generate_signals(market_data)
                ml_sell_count = sum(1 for s in ml_pre if s.get("action") == "SELL")
                self._ml_risk_off = ml_sell_count >= 3
                self._ml_signals_cache = ml_pre
                if self._ml_risk_off:
                    logger.warning(
                        f"ML risk-off: {ml_sell_count} broad SELL signals — "
                        f"BUY suppressed for non-ML strategies this run"
                    )
                else:
                    logger.info(
                        f"ML pre-scan: {ml_sell_count} SELL(s) — risk-off threshold not reached"
                    )
            except Exception as _e:
                logger.warning(f"ML risk-off pre-scan skipped: {_e}")

        current_prices = market_data.groupby("symbol")["close"].last().to_dict()

        # Pre-compute typical prices (H+L+C)/3 for VWAP-proxy OPG limit orders.
        # Stocks that gap up past this level at the open won't fill — we avoid chasing gap-ups.
        if "high" in market_data.columns and "low" in market_data.columns:
            _last = market_data.groupby("symbol")[["high", "low", "close"]].last()
            self._typical_prices = ((_last["high"] + _last["low"] + _last["close"]) / 3).to_dict()
        else:
            self._typical_prices = dict(current_prices)

        # Auto-refresh earnings calendar if stale (> 7 days old).
        self._maybe_refresh_earnings_calendar()

        # Refresh open position prices so unrealized P&L is current in the email
        refreshed = self.db.refresh_position_prices(current_prices)
        if refreshed:
            logger.info(f"Refreshed current prices for {refreshed} open positions")

        self.dynamic_allocator.total_capital = max(self.portfolio_value, self.buying_power)
        self.dynamic_allocator.max_allocation = self.config.get(
            "risk.dynamic_max_allocation_pct", 0.35
        )
        self.dynamic_allocator.min_allocation = self.config.get(
            "risk.dynamic_min_allocation_pct", 0.10
        )
        allocations = self._calculate_dynamic_allocations(strategies)
        exposures = self._calculate_strategy_exposures(strategies, current_prices)
        self._apply_allocations(strategies, allocations, exposures)
        total_exposure = sum(exposures.values())

        regime_adjustments = self.regime_detector.get_regime_adjustments(
            market_data=market_data,
            base_max_heat=self.portfolio_risk.base_max_heat,
        )
        self.portfolio_risk.max_portfolio_heat = regime_adjustments["max_portfolio_heat"]

        # Regime-adaptive stop-loss multiplier: wider in low-vol (avoid noise stop-outs),
        # tighter in high-vol (protect against fast moves)
        vol_regime = regime_adjustments.get("volatility_regime", "normal")
        if vol_regime == "low_volatility":
            mult = self.config.get("risk.stop_loss_atr_multiplier_low_vol", 3.0)
        elif vol_regime == "high_volatility":
            mult = self.config.get("risk.stop_loss_atr_multiplier_high_vol", 2.0)
        else:
            mult = self.config.get("risk.stop_loss_atr_multiplier", 2.5)
        self._current_stop_multiplier = mult
        self.stop_loss_manager.atr_multiplier = mult
        logger.info(f"Regime-adjusted stop multiplier: {mult:.1f}×ATR ({vol_regime})")

        # Persist regime so daily email shows the correct market status (not 'Unknown')
        _VOL_TO_CLASSIFICATION = {
            "low_volatility": "LOW_VOL",
            "normal": "NORMAL",
            "high_volatility": "HIGH_VOL",
        }
        try:
            import json as _json

            self.db.set_system_state(
                "regime",
                _json.dumps(
                    {
                        "classification": _VOL_TO_CLASSIFICATION.get(
                            regime_adjustments.get("volatility_regime", "normal"), "NORMAL"
                        ),
                        "vix": regime_adjustments.get("vix"),
                        "volatility_regime": regime_adjustments.get("volatility_regime"),
                        "trend_regime": regime_adjustments.get("trend_regime"),
                        "hmm_regime": regime_adjustments.get("hmm_regime"),
                    }
                ),
            )
            logger.info(
                "Regime persisted: %s (VIX=%.1f, trend=%s, hmm=%s)",
                regime_adjustments.get("volatility_regime"),
                regime_adjustments.get("vix") or 0,
                regime_adjustments.get("trend_regime"),
                regime_adjustments.get("hmm_regime"),
            )
        except Exception as _exc:
            logger.warning("Could not persist regime to system_state: %s", _exc)

        # 5-regime composite label for the strategy weight table
        composite_regime = self.regime_detector.detect_composite_regime(
            vix=regime_adjustments.get("vix"), market_data=market_data
        )
        # Persist composite alongside legacy regime fields
        try:
            import json as _json2

            _regime_state = _json2.loads(self.db.get_system_state("regime") or "{}")
            _regime_state["composite_regime"] = composite_regime
            self.db.set_system_state("regime", _json2.dumps(_regime_state))
        except Exception as _exc2:
            logger.warning("Could not persist composite regime: %s", _exc2)

        health_by_strategy = self._collect_strategy_health(strategies)
        trailing_sharpe = self._compute_trailing_sharpe(strategies)
        if trailing_sharpe:
            logger.info(
                "Trailing 30d Sharpe: %s",
                ", ".join(f"{k}={v:.2f}" for k, v in trailing_sharpe.items()),
            )
        kelly_weights = self._compute_kelly_weights(strategies)
        self.strategy_weights = compute_strategy_weights(
            strategy_names=[s.name for s in strategies],
            regime_adjustments=regime_adjustments,
            health_by_strategy=health_by_strategy,
            trailing_sharpe_by_strategy=trailing_sharpe,
            composite_regime=composite_regime,
            kelly_weights=kelly_weights,
        )
        logger.info(
            "Daily strategy weights: %s",
            ", ".join(
                f"{name}={weight:.2f}" for name, weight in sorted(self.strategy_weights.items())
            ),
        )
        all_signals = []

        try:
            # Save START snapshot
            logger.info("Saving START broker snapshot...")
            account = self.trading_client.get_account()
            broker_positions = self.trading_client.get_all_positions()
            self.db.save_broker_state(
                snapshot_date=self.asof_date,
                snapshot_type="START",
                cash=float(account.cash),
                portfolio_value=float(account.portfolio_value),
                buying_power=float(account.buying_power),
                positions=[
                    {"symbol": p.symbol, "qty": float(p.qty), "market_value": float(p.market_value)}
                    for p in broker_positions
                ],
                reconciliation_status="SKIPPED",
                discrepancies=[],
            )

            # CRITICAL: Hard reconciliation gate (MANDATORY)
            logger.info("=" * 80)
            logger.info("BROKER RECONCILIATION (MANDATORY GATE)")
            logger.info("=" * 80)

            # Refresh account before reconciliation (also ensures daily loss check
            # uses fresh portfolio_value, not the stale value from __init__)
            logger.info("Refreshing account state before reconciliation...")
            self._refresh_account_state()

            if not self.portfolio_risk.check_daily_loss_limit(self.portfolio_value):
                logger.warning("Trading halted due to daily loss limit")
                return []

            local_positions = self._build_local_positions()
            success, discrepancies = self.broker_reconciler.reconcile_daily(
                local_positions=local_positions, local_cash=self.cash_available
            )

            self.reconciliation_status = "PASS" if success else "FAIL"
            self.reconciliation_discrepancies = discrepancies

            # Update kill context
            kill_context["reconciliation_status"] = self.reconciliation_status

            # Save RECONCILIATION snapshot
            logger.info(f"Saving RECONCILIATION snapshot (status: {self.reconciliation_status})...")
            account = self.trading_client.get_account()
            broker_positions = self.trading_client.get_all_positions()
            self.db.save_broker_state(
                snapshot_date=self.asof_date,
                snapshot_type="RECONCILIATION",
                cash=float(account.cash),
                portfolio_value=float(account.portfolio_value),
                buying_power=float(account.buying_power),
                positions=[
                    {"symbol": p.symbol, "qty": float(p.qty), "market_value": float(p.market_value)}
                    for p in broker_positions
                ],
                reconciliation_status=self.reconciliation_status,
                discrepancies=discrepancies,
            )

            # HARD GATE: Block trading on failure
            if not success:
                auto_sync_enabled = os.getenv("AUTO_SYNC_ON_RECON_FAIL", "true").lower() == "true"
                if auto_sync_enabled:
                    (
                        retry_success,
                        retry_discrepancies,
                    ) = self._attempt_auto_sync_and_reconciliation_retry(strategies=strategies)
                    if retry_success:
                        self.reconciliation_status = "PASS"
                        self.reconciliation_discrepancies = []
                        kill_context["reconciliation_status"] = self.reconciliation_status

                        logger.warning("✅ Reconciliation recovered after automatic sync and retry")
                        account = self.trading_client.get_account()
                        broker_positions = self.trading_client.get_all_positions()
                        self.db.save_broker_state(
                            snapshot_date=self.asof_date,
                            snapshot_type="RECONCILIATION_RETRY",
                            cash=float(account.cash),
                            portfolio_value=float(account.portfolio_value),
                            buying_power=float(account.buying_power),
                            positions=[
                                {
                                    "symbol": p.symbol,
                                    "qty": float(p.qty),
                                    "market_value": float(p.market_value),
                                }
                                for p in broker_positions
                            ],
                            reconciliation_status="PASS",
                            discrepancies=[],
                        )
                        success = True
                        discrepancies = []
                    else:
                        discrepancies = discrepancies + retry_discrepancies
                        self.reconciliation_discrepancies = discrepancies

            if not success:
                logger.critical("🛑 RECONCILIATION FAILED - TRADING BLOCKED")
                logger.critical("Discrepancies:")
                for disc in discrepancies:
                    logger.critical(f"  - {disc}")

                self.errors.extend(discrepancies)

                # Write zero-count signal funnel rows for every strategy so the
                # post-run guardrail doesn't flag "missing funnel rows" when trading
                # is legitimately blocked rather than silently skipped.
                for strategy in strategies:
                    self.funnel_tracker.record_raw_signals(strategy.strategy_id, 0)
                    self.funnel_tracker.record_after_regime(strategy.strategy_id, 0)
                    self.funnel_tracker.record_after_correlation(strategy.strategy_id, 0)
                    self.funnel_tracker.record_after_risk(strategy.strategy_id, 0)
                    self.funnel_tracker.record_executed(strategy.strategy_id, 0)
                    self.funnel_tracker.save_to_database(strategy.strategy_id, strategy.name)

                # Send critical alert
                disc_html = "".join(f"<li>{d}</li>" for d in discrepancies)
                self.email_notifier.send_alert(
                    "Reconciliation Failure - Trading Blocked",
                    f"<html><body style='font-family:sans-serif;max-width:600px;margin:0 auto'>"
                    f"<div style='background:#dc3545;color:#fff;padding:16px 20px;border-radius:8px 8px 0 0'>"
                    f"<h2 style='margin:0'>🛑 Reconciliation Failure — Trading Blocked</h2></div>"
                    f"<div style='padding:20px;border:1px solid #dee2e6;border-top:none'>"
                    f"<p>The trading run was halted because the local database does not match "
                    f"the Alpaca broker state. No orders were submitted.</p>"
                    f"<h3 style='color:#dc3545'>Discrepancies ({len(discrepancies)})</h3>"
                    f"<ul style='color:#333;line-height:1.6'>{disc_html}</ul>"
                    f"<hr style='border:none;border-top:1px solid #eee'>"
                    f"<p style='color:#666;font-size:13px'>"
                    f"Run the sync workflow or <code>python3 scripts/sync_broker_state.py</code> "
                    f"to resolve the drift, then re-run the daily workflow.</p>"
                    f"</div></body></html>",
                )

                # Log to structured logger
                self.structured_logger.log_event(
                    "RECONCILIATION_CHECK",
                    {"status": "FAIL", "discrepancies": discrepancies},
                    stage="RECONCILIATION",
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
                            "symbol": symbol,
                            "action": "BUY",
                            "confidence": 0.75,
                            "reasoning": "VALIDATION: Synthetic signal for testing",
                            "price": current_prices[symbol],
                            "injected": True,
                            "injection_source": "VALIDATION_MODE",
                        }
                        injected_signals.append(injected_signal)
                        logger.info(f"  [INJECTION] BUY {symbol} @ ${current_prices[symbol]:.2f}")

                logger.info(f"Generated {len(injected_signals)} validation signals")
                logger.info(
                    "These signals will go through normal correlation filter, risk checks, and sizing"
                )
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

                    if not self.regime_detector.should_enable_strategy(
                        strategy.name, regime_adjustments
                    ):
                        logger.info(f"Skipping {strategy.name} due to regime adjustments")
                        self.funnel_tracker.record_raw_signals(strategy.strategy_id, 0)
                        self.funnel_tracker.record_after_regime(strategy.strategy_id, 0)
                        continue

                    if self._check_strategy_loss_limit(strategy, strategies):
                        logger.warning(
                            "Skipping %s signal generation — strategy loss limit triggered",
                            strategy.name,
                        )
                        self.funnel_tracker.record_raw_signals(strategy.strategy_id, 0)
                        self.funnel_tracker.record_after_regime(strategy.strategy_id, 0)
                        self.funnel_tracker.record_after_correlation(strategy.strategy_id, 0)
                        self.funnel_tracker.record_after_risk(strategy.strategy_id, 0)
                        self.funnel_tracker.record_executed(strategy.strategy_id, 0)
                        self.funnel_tracker.save_to_database(strategy.strategy_id, strategy.name)
                        continue

                    # Generate signals (reuse ML pre-scan cache to avoid double-training)
                    logger.info(
                        f"  Calling {strategy.name}.generate_signals() with {len(market_data)} rows, {market_data['symbol'].nunique()} symbols"
                    )
                    if strategy is ml_strategy and self._ml_signals_cache is not None:
                        signals = self._ml_signals_cache
                        self._ml_signals_cache = None  # consume cache
                    else:
                        signals = strategy.generate_signals(market_data)

                    # FUNNEL STAGE 1: Raw signals
                    raw_count = len(signals) if signals else 0
                    logger.info(f"  {strategy.name} generated {raw_count} raw signals")
                    if raw_count > 0:
                        for sig in signals[:3]:  # Log first 3 signals
                            logger.info(
                                f"    - {sig.get('action')} {sig.get('symbol')}: {sig.get('reasoning', 'No reason')}"
                            )
                    self.funnel_tracker.record_raw_signals(strategy.strategy_id, raw_count)

                    # VALIDATION MODE: Route injected signals to RSI Mean Reversion
                    if (
                        self.signal_injection_enabled
                        and strategy.name == "RSI Mean Reversion"
                        and len(injected_signals) > 0
                    ):
                        logger.info(
                            f"  [INJECTION] Routing {len(injected_signals)} validation signals to {strategy.name}"
                        )
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
                            signals, combined_positions, market_data
                        )

                        # Log correlation rejections
                        for sig in self.raw_signals_by_strategy[strategy.name]:
                            if sig not in signals:
                                self.funnel_tracker.log_rejection(
                                    strategy.strategy_id,
                                    sig.get("symbol"),
                                    "CORRELATION",
                                    "high_correlation",
                                    {"threshold": 0.8},
                                )

                        self.funnel_tracker.record_after_correlation(
                            strategy.strategy_id, len(signals)
                        )

                        # Apply news sentiment as confidence modifier (boost/suppress)
                        signal_symbols = list({s.get("symbol") for s in signals})
                        new_syms = [s for s in signal_symbols if s not in self._news_sentiment_map]
                        if new_syms:
                            self._news_sentiment_map.update(
                                self._news_filter.fetch_for_symbols(new_syms)
                            )
                            self.alpha_vantage_usage = self._news_filter.get_usage_summary()
                        signals = self._news_filter.apply(signals, self._news_sentiment_map)
                        signals = apply_strategy_weight_to_signals(
                            strategy_name=strategy.name,
                            signals=signals,
                            strategy_weights=self.strategy_weights,
                        )
                        logger.info(f"  After news filter: {len(signals)} signals")

                        # Log signals to database
                        signal_ids = []
                        for signal in signals:
                            signal_id = self.db.log_signal(
                                strategy.strategy_id,
                                signal.get("symbol"),
                                signal.get("action", "BUY"),
                                signal.get("confidence", 0.5),
                                signal.get("reasoning", ""),
                                self.asof_date,
                            )
                            signal_ids.append(signal_id)
                            signal["signal_id"] = signal_id

                        # FUNNEL STAGE 4: Risk/cash limits (tracked in _execute_strategy_trades)
                        # Sort: SELL signals always execute before BUYs so exits are never
                        # throttled by the top_n cap when a strategy generates both actions.
                        signals.sort(key=lambda s: 0 if s.get("action") == "SELL" else 1)
                        max_signals = getattr(strategy, "top_n", 5)
                        # Always include all SELL signals; cap only BUY signals with top_n
                        _sells = [s for s in signals if s.get("action") == "SELL"]
                        _buys = [s for s in signals if s.get("action") != "SELL"]
                        signals_to_execute = _sells + _buys[: max(0, max_signals - len(_sells))]
                        self.funnel_tracker.record_after_risk(
                            strategy.strategy_id, len(signals_to_execute)
                        )

                        # Execute trades
                        executed, total_exposure = self._execute_strategy_trades(
                            strategy, signals_to_execute, total_exposure, self.portfolio_value
                        )

                        # FUNNEL STAGE 5: Executed
                        self.funnel_tracker.record_executed(
                            strategy.strategy_id, min(len(executed), len(signals_to_execute))
                        )

                        # Log risk rejections
                        for sig in signals_to_execute:
                            if not any(e.get("symbol") == sig.get("symbol") for e in executed):
                                self.funnel_tracker.log_rejection(
                                    strategy.strategy_id,
                                    sig.get("symbol"),
                                    "RISK",
                                    "cash_or_heat_limit",
                                    {},
                                )

                        all_signals.extend(executed)

                        # Set terminal states for executed signals
                        for signal in signals_to_execute:
                            signal_id = signal.get("signal_id")
                            if signal_id:
                                was_executed = any(
                                    e.get("symbol") == signal.get("symbol")
                                    and e.get("action") == signal.get("action")
                                    for e in executed
                                )
                                if was_executed:
                                    self.db.update_signal_terminal_state(
                                        signal_id, "EXECUTED", "filled"
                                    )
                                else:
                                    # Use distinct reasons so auditing can tell
                                    # cash/heat rejections apart from failed exits.
                                    _action = signal.get("action", "BUY")
                                    _reason = (
                                        "exit_blocked"
                                        if _action == "SELL"
                                        else "risk_or_cash_limit"
                                    )
                                    self.db.update_signal_terminal_state(
                                        signal_id, "FILTERED", _reason
                                    )

                        # Mark throttled BUY signals as FILTERED (only BUYs are capped by top_n;
                        # SELLs always execute so they are never throttled here)
                        for signal in _buys[max(0, max_signals - len(_sells)) :]:
                            signal_id = signal.get("signal_id")
                            if signal_id:
                                self.db.update_signal_terminal_state(
                                    signal_id, "FILTERED", "throttle"
                                )
                                self.funnel_tracker.log_rejection(
                                    strategy.strategy_id,
                                    signal.get("symbol"),
                                    "THROTTLE",
                                    "max_signals_limit",
                                    signal_id=signal_id,
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

            # Signal crowding detection: warn if 2+ strategies want the same symbol

            buy_symbol_sources: dict = {}
            for strat_name, strat_signals in self.raw_signals_by_strategy.items():
                for sig in strat_signals or []:
                    if sig.get("action", "").upper() == "BUY":
                        sym = sig.get("symbol")
                        if sym:
                            buy_symbol_sources.setdefault(sym, []).append(strat_name)
            for sym, sources in buy_symbol_sources.items():
                if len(sources) >= 2:
                    logger.warning(
                        "Crowding detected: %s wanted by %s — signals may reflect same factor, not independent edge",
                        sym,
                        " + ".join(sources),
                    )

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
                snapshot_type="END",
                cash=float(account.cash),
                portfolio_value=float(account.portfolio_value),
                buying_power=float(account.buying_power),
                positions=[
                    {"symbol": p.symbol, "qty": float(p.qty), "market_value": float(p.market_value)}
                    for p in broker_positions
                ],
                reconciliation_status=self.reconciliation_status,
                discrepancies=self.reconciliation_discrepancies,
            )

    def _check_strategy_loss_limit(self, strategy, strategies) -> bool:
        """Return True (halted) if strategy has lost more than max_strategy_loss_pct of its capital.

        Loss is measured from actual trade P&L (trade_pnl_detail) plus unrealized open-position
        P&L — NOT from capital_allocation changes. The dynamic allocator legitimately reduces a
        strategy's budget when its Sharpe is poor; that must not count as a trading loss.
        """
        max_loss = self.config.get("risk.max_strategy_loss_pct", 0.20)
        all_strategies_db = {s["name"]: s for s in self.db.get_all_strategies()}
        db_entry = all_strategies_db.get(strategy.name, {})
        reference_capital = float(
            db_entry.get("capital_allocation", strategy.capital) or strategy.capital
        )
        if reference_capital <= 0:
            return False

        # Realized P&L: sum of all closed trade gross_pnl for this strategy
        import sqlite3 as _sqlite3

        realized_pnl = 0.0
        try:
            _conn = _sqlite3.connect(self.db.db_path)
            _cur = _conn.cursor()
            _cur.execute(
                "SELECT COALESCE(SUM(gross_pnl), 0.0) FROM trade_pnl_detail WHERE strategy_id = ?",
                (strategy.strategy_id,),
            )
            row = _cur.fetchone()
            realized_pnl = float(row[0]) if row else 0.0
            _conn.close()
        except Exception as _e:
            logger.warning("Failed to load realized P&L for strategy loss check: %s", _e)

        # Unrealized P&L: (current_price - avg_entry_price) * shares for open positions
        current_prices: dict = {}
        try:
            import pandas as pd

            data_file = project_root / "data" / "training_data.csv"
            if data_file.exists():
                _df = pd.read_csv(data_file, index_col=0)
                current_prices = (
                    _df.groupby("symbol")["close"].last().dropna().astype(float).to_dict()
                )
        except Exception as _e:
            logger.warning("Failed to load price data for strategy loss check: %s", _e)

        unrealized_pnl = 0.0
        try:
            _conn = _sqlite3.connect(self.db.db_path)
            _cur = _conn.cursor()
            _cur.execute(
                "SELECT symbol, shares, avg_price FROM positions WHERE strategy_id = ? AND shares > 0",
                (strategy.strategy_id,),
            )
            for sym, shares, avg_price in _cur.fetchall():
                current = current_prices.get(sym, avg_price)
                unrealized_pnl += (current - avg_price) * shares
            _conn.close()
        except Exception as _e:
            logger.warning("Failed to compute unrealized P&L for strategy loss check: %s", _e)

        total_pnl = realized_pnl + unrealized_pnl
        loss_pct = (-total_pnl / reference_capital) if total_pnl < 0 else 0.0

        if loss_pct > max_loss:
            logger.critical(
                "STRATEGY LOSS LIMIT: %s has lost %.1f%% (limit %.0f%%) — freezing strategy",
                strategy.name,
                loss_pct * 100,
                max_loss * 100,
            )
            frozen_capital = strategy.capital
            active_others = [s for s in strategies if s is not strategy]
            redistribution_lines = []
            if active_others and frozen_capital > 0:
                share = frozen_capital / len(active_others)
                for other in active_others:
                    other.capital += share
                    redistribution_lines.append(f"<li>{other.name}: +${share:,.2f}</li>")
                    logger.info(
                        "Redistributed $%.2f from frozen strategy %s to %s",
                        share,
                        strategy.name,
                        other.name,
                    )
                strategy.capital = 0.0

            # Email alert — strategy freeze is a critical event requiring human awareness
            try:
                self.email_notifier.send_alert(
                    subject=f"STRATEGY FROZEN: {strategy.name}",
                    message=(
                        f"<h2>Strategy Loss Limit Triggered</h2>"
                        f"<p>Strategy <strong>{strategy.name}</strong> has been frozen "
                        f"after losing <strong>{loss_pct*100:.1f}%</strong> of its capital "
                        f"(limit: {max_loss*100:.0f}%).</p>"
                        f"<table>"
                        f"<tr><td>Reference capital</td><td>${reference_capital:,.2f}</td></tr>"
                        f"<tr><td>Realized P&L</td><td>${realized_pnl:,.2f}</td></tr>"
                        f"<tr><td>Unrealized P&L</td><td>${unrealized_pnl:,.2f}</td></tr>"
                        f"<tr><td>Total loss</td><td>${-total_pnl:,.2f} "
                        f"({loss_pct*100:.1f}%)</td></tr>"
                        f"</table>"
                        f"<h3>Capital redistributed to:</h3><ul>"
                        + "".join(redistribution_lines)
                        + "</ul><p>No further trades will be placed for this strategy.</p>"
                    ),
                )
            except Exception as _email_exc:
                logger.warning("Failed to send strategy-freeze email: %s", _email_exc)

            return True
        return False

    def _execute_strategy_trades(self, strategy, signals, total_exposure, portfolio_value):
        """Execute trades for a specific strategy"""
        executed = []

        for signal in signals:
            symbol = signal.get("symbol")
            action = signal.get("action", "BUY")
            shares = signal.get("shares", 0)
            price = signal.get("price", 0)

            if action == "BUY" and shares > 0:
                intent_id = None
                try:
                    # Benchmark ETF guard: never trade index/sector ETFs as positions
                    if symbol in UniverseProvider.BENCHMARK_SYMBOLS:
                        logger.warning(
                            f"Skipping BUY {symbol} - benchmark ETF cannot be traded as position"
                        )
                        self.rejected_signals.append(
                            {
                                "strategy": strategy.name,
                                "symbol": symbol,
                                "action": action,
                                "shares": shares,
                                "price": price,
                                "reason": "benchmark_etf_guard",
                            }
                        )
                        continue

                    # Max positions guard: cap total open positions across all strategies
                    max_total_positions = self.config.get("risk.max_total_positions", 12)
                    total_open = len(self.db.get_all_open_positions())
                    if total_open >= max_total_positions:
                        logger.warning(
                            f"Skipping BUY {symbol} - at max positions limit ({total_open}/{max_total_positions})"
                        )
                        self.rejected_signals.append(
                            {
                                "strategy": strategy.name,
                                "symbol": symbol,
                                "action": action,
                                "shares": shares,
                                "price": price,
                                "reason": "max_positions_reached",
                            }
                        )
                        continue

                    # Cross-strategy dedup: block if symbol already held by any strategy.
                    # Each strategy's generate_signals() blocks re-entry for its own
                    # positions, but a second strategy can independently signal the same
                    # symbol, creating unintended double-concentration.
                    if symbol in self._held_symbols:
                        logger.info(
                            f"Skipping BUY {symbol} ({strategy.name}) - already held by another strategy"
                        )
                        self.rejected_signals.append(
                            {
                                "strategy": strategy.name,
                                "symbol": symbol,
                                "action": action,
                                "shares": shares,
                                "price": price,
                                "reason": "cross_strategy_dedup",
                            }
                        )
                        continue

                    # Wash trade prevention: skip if already sold this symbol this run
                    if symbol in self.symbols_sold_this_run:
                        logger.warning(
                            f"Skipping BUY {symbol} - already sold this run (wash trade prevention)"
                        )
                        self.rejected_signals.append(
                            {
                                "strategy": strategy.name,
                                "symbol": symbol,
                                "action": action,
                                "shares": shares,
                                "price": price,
                                "reason": "wash_trade_guard",
                            }
                        )
                        continue

                    # Pre-earnings guard: skip new entries for symbols reporting tomorrow
                    if symbol in getattr(self, "_reporting_tomorrow", set()):
                        logger.info(
                            f"Skipping BUY {symbol} — reports earnings tomorrow (binary event protection)"
                        )
                        self.rejected_signals.append(
                            {
                                "strategy": strategy.name,
                                "symbol": symbol,
                                "action": action,
                                "shares": shares,
                                "price": price,
                                "reason": "pre_earnings_guard",
                            }
                        )
                        continue

                    # ML risk-off guard: suppress BUY from non-ML strategies when ML detected
                    # broad bearish conditions (≥3 SELL signals across the universe)
                    if getattr(self, "_ml_risk_off", False) and "ml" not in strategy.name.lower():
                        logger.info(f"Skipping BUY {symbol} ({strategy.name}) — ML risk-off active")
                        self.rejected_signals.append(
                            {
                                "strategy": strategy.name,
                                "symbol": symbol,
                                "action": action,
                                "shares": shares,
                                "price": price,
                                "reason": "ml_risk_off",
                            }
                        )
                        continue

                    # Duplicate prevention: skip if we already hold this symbol for this strategy today
                    existing_pos = self.db.get_position(strategy.strategy_id, symbol)
                    if existing_pos and float(existing_pos.get("shares", 0)) > 0:
                        entry_dt = existing_pos.get("entry_date", "")
                        if entry_dt and entry_dt[:10] == self.asof_date:
                            logger.warning(
                                f"Skipping BUY {symbol} - position opened today (duplicate prevention)"
                            )
                            self.rejected_signals.append(
                                {
                                    "strategy": strategy.name,
                                    "symbol": symbol,
                                    "action": action,
                                    "shares": shares,
                                    "price": price,
                                    "reason": "duplicate_prevention",
                                }
                            )
                            continue

                    # Apply size multiplier from correlation attenuation
                    size_mult = signal.get("size_multiplier", 1.0)
                    # Apply drawdown sizing multiplier (rampup mode)
                    drawdown_mult = self.drawdown_manager.get_sizing_multiplier()
                    # Daily strategy weighting multiplier (meta-layer)
                    strategy_mult = float(signal.get("strategy_weight", 1.0))
                    # Confidence-scaled sizing: linear interpolation
                    # conf=0.55→0.75x, conf=0.90→1.25x (allows high-conviction oversize)
                    _conf = max(0.55, min(0.90, float(signal.get("confidence", 0.70))))
                    _t = (_conf - 0.55) / (0.90 - 0.55)
                    conviction_mult = round(0.75 + _t * (1.25 - 0.75), 3)
                    combined_mult = size_mult * drawdown_mult * strategy_mult * conviction_mult
                    adjusted_shares = round(shares * combined_mult)

                    if adjusted_shares == 0:
                        logger.info(f"Skipping {symbol} - size multiplier reduced shares to 0")
                        self.rejected_signals.append(
                            {
                                "strategy": strategy.name,
                                "symbol": symbol,
                                "action": action,
                                "shares": shares,
                                "price": price,
                                "reason": "size_reduced_to_zero",
                            }
                        )
                        continue

                    logger.info(
                        f"Size adjustment for {symbol}: {shares} → {adjusted_shares} "
                        f"(corr={size_mult:.2f}, drawdown={drawdown_mult:.2f}, "
                        f"strategy={strategy_mult:.2f}, conviction={conviction_mult:.2f}, combined={combined_mult:.2f})"
                    )

                    (
                        exec_price,
                        slippage_cost,
                        commission_cost,
                        total_cost,
                    ) = self.cost_model.calculate_execution_price(price, "BUY", adjusted_shares)
                    trade_value = exec_price * adjusted_shares + total_cost

                    if not self.cash_manager.reserve_cash(strategy.strategy_id, trade_value):
                        logger.warning(
                            f"Skipping {symbol} - insufficient cash for strategy {strategy.strategy_id}"
                        )
                        self.rejected_signals.append(
                            {
                                "strategy": strategy.name,
                                "symbol": symbol,
                                "action": action,
                                "shares": adjusted_shares,
                                "price": price,
                                "reason": "insufficient_cash",
                            }
                        )
                        continue
                    if not self.portfolio_risk.can_add_position(
                        trade_value, total_exposure, portfolio_value
                    ):
                        logger.warning(f"Skipping {symbol} - portfolio heat limit")
                        self.rejected_signals.append(
                            {
                                "strategy": strategy.name,
                                "symbol": symbol,
                                "action": action,
                                "shares": adjusted_shares,
                                "price": price,
                                "reason": "portfolio_heat",
                            }
                        )
                        self.cash_manager.release_cash(strategy.strategy_id, trade_value)
                        continue

                    # Sector concentration check — uses per-position market values
                    _prices = getattr(self, "_typical_prices", {})
                    _open_positions = self.db.get_all_open_positions()
                    _current_mvs = {
                        p["symbol"]: float(p.get("shares", 0)) * _prices.get(p["symbol"], 0)
                        for p in _open_positions
                    }
                    max_sector_pct = self.config.get("risk.max_sector_pct", 0.30)
                    (
                        _sector_allowed,
                        _sector_reason,
                    ) = self.portfolio_risk.check_sector_concentration(
                        symbol=symbol,
                        position_value=trade_value,
                        current_positions=_current_mvs,
                        portfolio_value=portfolio_value,
                        sector_map=_SECTOR_MAP,
                        max_sector_pct=max_sector_pct,
                        strategy_name=strategy.name,
                    )
                    if not _sector_allowed:
                        logger.warning(
                            f"Skipping BUY {symbol} ({strategy.name}) - {_sector_reason}"
                        )
                        self.rejected_signals.append(
                            {
                                "strategy": strategy.name,
                                "symbol": symbol,
                                "action": action,
                                "shares": adjusted_shares,
                                "price": price,
                                "reason": "sector_concentration",
                            }
                        )
                        self.cash_manager.release_cash(strategy.strategy_id, trade_value)
                        continue

                    # True idempotency gate: check for an existing active intent
                    # for this (strategy, symbol, side) today BEFORE creating a new one.
                    # create_order_intent embeds run_id in the hash, so two runs on the
                    # same day generate different intent_ids — the old check was circular.
                    existing_today = self.db.find_active_order_intent_for_today(
                        strategy.strategy_id, symbol, "BUY"
                    )
                    if existing_today:
                        logger.warning(
                            "Idempotency guard: %s BUY already %s today (intent %s) — skipping",
                            symbol,
                            existing_today["status"],
                            existing_today["intent_id"],
                        )
                        self.cash_manager.release_cash(strategy.strategy_id, trade_value)
                        continue

                    # Create order intent
                    intent_id = self.db.create_order_intent(
                        strategy.strategy_id, symbol, "BUY", adjusted_shares
                    )

                    # Log order intent to structured logger
                    self.structured_logger.log_order_intent(
                        intent_id, strategy.strategy_id, symbol, "BUY", adjusted_shares
                    )

                    # Limit-on-open: use previous day's typical price (H+L+C)/3 as the cap.
                    # Orders only fill if the open is at or below this limit — avoids chasing
                    # overnight gap-ups.  A 1% buffer keeps fill rates high on normal opens.
                    _typical = getattr(self, "_typical_prices", {}).get(symbol, price)
                    _limit_price = round(_typical * 1.01, 2)
                    order_data = LimitOrderRequest(
                        symbol=symbol,
                        qty=adjusted_shares,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.OPG,
                        limit_price=_limit_price,
                    )

                    # Wrap with DRY_RUN protection
                    order = self.dry_run.execute_broker_operation(
                        f"submit_order_{symbol}", self.trading_client.submit_order, order_data
                    )

                    # Update intent status
                    self.db.update_order_intent_status(intent_id, "SUBMITTED", str(order.id))

                    trade_info = {
                        "symbol": signal["symbol"],
                        "action": signal["action"],
                        "shares": adjusted_shares,
                        "price": signal["price"],
                        "order_id": order.id,
                        "intent_id": intent_id,
                    }
                    self.executed_trades.append(trade_info)
                    executed.append(
                        {
                            "strategy": strategy.name,
                            "symbol": symbol,
                            "shares": adjusted_shares,
                            "price": price,
                            "action": "BUY",
                        }
                    )
                    self.executed_signals.append(
                        {
                            "strategy": strategy.name,
                            "symbol": symbol,
                            "shares": adjusted_shares,
                            "price": price,
                            "action": "BUY",
                        }
                    )

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
                            f"get_order_{symbol}", self.trading_client.get_order_by_id, order.id
                        )

                        if filled_order.status in ["filled", "partially_filled"]:
                            fill_verified = True
                            actual_filled_qty = (
                                float(filled_order.filled_qty)
                                if filled_order.filled_qty
                                else adjusted_shares
                            )
                            actual_fill_price = (
                                float(filled_order.filled_avg_price)
                                if filled_order.filled_avg_price
                                else exec_price
                            )
                            logger.info(
                                f"Order {order.id} verified: {filled_order.status}, filled_qty={actual_filled_qty}, avg_price={actual_fill_price}"
                            )
                        else:
                            logger.info(
                                f"Order {order.id} not filled yet: status={filled_order.status} (OPG fills at market open)"
                            )
                            # OPG orders fill at next morning's open, not immediately.
                            # In paper mode we treat the submission as a confirmed fill
                            # and mark FILLED now so the intent lifecycle completes this run.
                            if self.paper_mode:
                                fill_verified = True
                                self.db.update_order_intent_status(
                                    intent_id, "FILLED", broker_order_id=str(order.id)
                                )
                                logger.info("Paper mode: OPG order marked FILLED optimistically")
                    except Exception as e:
                        logger.warning(f"Could not verify fill for {order.id}: {e}")
                        if self.paper_mode:
                            fill_verified = True
                            self.db.update_order_intent_status(
                                intent_id, "FILLED", broker_order_id=str(order.id)
                            )
                            logger.info(
                                "Paper mode: OPG order marked FILLED despite status-check error"
                            )

                    if not fill_verified:
                        logger.info(f"Order {order.id} not filled yet - keeping order pending")
                        self.cash_manager.release_cash(strategy.strategy_id, trade_value)
                        self.db.update_order_intent_status(
                            intent_id, "ACKED", broker_order_id=str(order.id)
                        )
                        self.pending_orders.append(
                            {
                                "symbol": symbol,
                                "side": "BUY",
                                "qty": adjusted_shares,
                                "price": price,
                                "status": "pending",
                            }
                        )
                        continue

                    print(
                        f"  ✅ BUY {actual_filled_qty} {symbol} @ ${actual_fill_price:.2f} (Order: {order.id}, Intent: {intent_id})"
                    )
                    self.symbols_bought_this_run.add(symbol)
                    self._held_symbols.add(symbol)  # keep cross-strategy dedup current

                    # Update in-memory state with actual filled quantities
                    strategy.add_position(symbol, actual_filled_qty)
                    actual_trade_value = actual_fill_price * actual_filled_qty + total_cost
                    strategy.update_capital(-actual_trade_value)
                    entry_date = signal.get("asof_date") or datetime.now()
                    strategy.entry_dates[symbol] = entry_date
                    strategy.entry_prices[symbol] = actual_fill_price
                    total_exposure += actual_trade_value
                    self.performance_metrics.add_trade(
                        "BUY", symbol, actual_filled_qty, actual_fill_price, actual_trade_value
                    )

                    # CRITICAL: Only update database AFTER verifying fill
                    entry_date_str = (
                        entry_date.date().isoformat()
                        if hasattr(entry_date, "date")
                        else str(entry_date)[:10]
                    )
                    atr = signal.get("atr", 0) or 0
                    self._update_position_record(
                        strategy.strategy_id,
                        symbol,
                        actual_filled_qty,
                        actual_fill_price,
                        entry_date=entry_date_str,
                        atr=atr if atr > 0 else None,
                    )

                    # CRITICAL: Set stop loss for new position (regime-aware multiplier)
                    if atr > 0:
                        self.stop_loss_manager.set_stop_loss(
                            symbol,
                            actual_fill_price,
                            atr,
                            multiplier=getattr(self, "_current_stop_multiplier", None),
                        )
                    else:
                        logger.warning(f"No ATR available for {symbol}, stop loss not set")

                    # Covered call opportunity (live trading only; no-op in paper mode).
                    self._submit_covered_calls(symbol, actual_filled_qty, actual_fill_price)

                    # BUY opens a position — realized P&L is None until the position is sold
                    signal_id = signal.get("signal_id")
                    self.db.log_trade(
                        strategy.strategy_id,
                        signal_id,
                        symbol,
                        "BUY",
                        actual_filled_qty,
                        price,
                        exec_price,
                        slippage_cost,
                        commission_cost,
                        str(order.id),
                        None,  # pnl is None for open positions; set on SELL
                    )

                    # Fill quality: record deviation between signal price and actual fill
                    if price > 0 and actual_fill_price > 0:
                        deviation_bps = int(round((actual_fill_price / price - 1) * 10000))
                        self.db.log_fill_quality(
                            strategy_id=strategy.strategy_id,
                            symbol=symbol,
                            action="BUY",
                            expected_price=price,
                            fill_price=actual_fill_price,
                            shares=actual_filled_qty,
                            deviation_bps=deviation_bps,
                        )
                        if abs(deviation_bps) > 100:
                            logger.warning(
                                "Poor fill quality: %s BUY expected $%.2f got $%.2f (%+d bps)",
                                symbol,
                                price,
                                actual_fill_price,
                                deviation_bps,
                            )

                except Exception as e:
                    logger.error(f"Failed to execute {symbol}: {e}")
                    print(f"  ❌ Failed {symbol}: {e}")
                    if intent_id is not None:
                        self.cash_manager.release_cash(strategy.strategy_id, trade_value)
                        try:
                            self.db.update_order_intent_status(intent_id, "FAILED", error=str(e))
                        except Exception:
                            logger.warning("Failed to update order intent status for %s", intent_id)

            elif action == "SELL" and shares > 0:
                sell_intent_id = None
                try:
                    # Wash trade prevention: skip if already bought this symbol this run
                    if symbol in self.symbols_bought_this_run:
                        logger.warning(
                            f"Skipping SELL {symbol} - already bought this run (wash trade prevention)"
                        )
                        continue

                    # Short-prevention guard: verify this strategy actually holds shares.
                    # A SELL on a zero-share position creates a short, which was observed
                    # when double-exits fired (e.g. stop-loss + strategy exit same day).
                    local_pos = self.db.get_position(strategy.strategy_id, symbol)
                    local_shares = float(local_pos["shares"]) if local_pos else 0.0
                    if local_shares <= 0:
                        logger.warning(
                            f"Skipping SELL {symbol} ({strategy.name}) - "
                            f"DB shows {local_shares} shares; selling would create a short"
                        )
                        # Clean up stale in-memory state to match DB reality
                        strategy.positions.pop(symbol, None)
                        continue

                    # Idempotency gate for SELL: GHA retries would re-submit exit orders,
                    # potentially creating short positions if the first run already sold.
                    existing_sell = self.db.find_active_order_intent_for_today(
                        strategy.strategy_id, symbol, "SELL"
                    )
                    if existing_sell:
                        logger.warning(
                            "Idempotency guard: %s SELL already %s today (intent %s) — skipping",
                            symbol,
                            existing_sell["status"],
                            existing_sell["intent_id"],
                        )
                        continue
                    sell_intent_id = self.db.create_order_intent(
                        strategy.strategy_id, symbol, "SELL", shares
                    )

                    (
                        exec_price,
                        slippage_cost,
                        commission_cost,
                        total_cost,
                    ) = self.cost_model.calculate_execution_price(price, "SELL", shares)
                    # Market-on-open: signals generated after close, execute at next day's open
                    order_data = MarketOrderRequest(
                        symbol=symbol,
                        qty=shares,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.OPG,
                    )

                    # Wrap with DRY_RUN protection
                    order = self.dry_run.execute_broker_operation(
                        f"submit_order_sell_{symbol}", self.trading_client.submit_order, order_data
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
                            order.id,
                        )

                        if filled_order.status in ["filled", "partially_filled"]:
                            fill_verified = True
                            actual_filled_qty = (
                                float(filled_order.filled_qty)
                                if filled_order.filled_qty
                                else shares
                            )
                            actual_fill_price = (
                                float(filled_order.filled_avg_price)
                                if filled_order.filled_avg_price
                                else exec_price
                            )
                            logger.info(
                                f"SELL Order {order.id} verified: {filled_order.status}, filled_qty={actual_filled_qty}, avg_price={actual_fill_price}"
                            )
                        else:
                            logger.info(
                                f"SELL Order {order.id} not filled yet: status={filled_order.status} (OPG fills at market open)"
                            )
                            if self.paper_mode:
                                fill_verified = True
                                logger.info("Paper mode: SELL OPG order assumed filled")
                    except Exception as e:
                        logger.warning(f"Could not verify SELL fill for {order.id}: {e}")
                        if self.paper_mode:
                            fill_verified = True
                            logger.info(
                                "Paper mode: SELL OPG order assumed filled despite status-check error"
                            )

                    if not fill_verified:
                        logger.error(
                            f"SELL Order {order.id} not filled - skipping database update to prevent sync issues"
                        )
                        continue

                    print(
                        f"  ✅ SELL {actual_filled_qty} {symbol} @ ${actual_fill_price:.2f} (Order: {order.id})"
                    )
                    self.symbols_sold_this_run.add(symbol)
                    if sell_intent_id:
                        try:
                            self.db.update_order_intent_status(
                                sell_intent_id, "FILLED", broker_order_id=str(order.id)
                            )
                        except Exception as _ie:
                            logger.warning("Failed to update SELL intent status: %s", _ie)

                    # PDT guardrail: track day trades (buy and sell same symbol same day)
                    if symbol in self.symbols_bought_this_run:
                        self._day_trades_today.append(symbol)
                        self._day_trade_count = len(set(self._day_trades_today))
                        if self._day_trade_count >= 3:
                            logger.warning(
                                "PDT WARNING: 3 day trades reached — next day trade would trigger "
                                "PDT restriction on accounts under $25k"
                            )

                    # Release cash back with actual filled quantities
                    trade_value = actual_fill_price * actual_filled_qty - total_cost
                    self.cash_manager.release_cash(strategy.strategy_id, trade_value)
                    strategy.update_capital(trade_value)

                    # Calculate P&L for this trade
                    total_costs = slippage_cost + commission_cost
                    pnl, pnl_explanation = self.pnl_calculator.calculate_trade_pnl(
                        strategy.strategy_id,
                        symbol,
                        "SELL",
                        actual_filled_qty,
                        actual_fill_price,
                        total_costs,
                    )
                    logger.info(f"P&L: {pnl_explanation}")

                    # Log trade with P&L
                    self.db.log_trade(
                        strategy.strategy_id,
                        signal.get("signal_id"),
                        symbol,
                        "SELL",
                        actual_filled_qty,
                        price,
                        actual_fill_price,
                        slippage_cost,
                        commission_cost,
                        str(order.id),
                        pnl,
                    )

                    # Fill quality: record deviation between signal price and actual fill
                    if price > 0 and actual_fill_price > 0:
                        deviation_bps = int(round((actual_fill_price / price - 1) * 10000))
                        self.db.log_fill_quality(
                            strategy_id=strategy.strategy_id,
                            symbol=symbol,
                            action="SELL",
                            expected_price=price,
                            fill_price=actual_fill_price,
                            shares=actual_filled_qty,
                            deviation_bps=deviation_bps,
                        )
                        if abs(deviation_bps) > 100:
                            logger.warning(
                                "Poor fill quality: %s SELL expected $%.2f got $%.2f (%+d bps)",
                                symbol,
                                price,
                                actual_fill_price,
                                deviation_bps,
                            )

                    # CRITICAL FIX: Update strategy positions with actual filled quantities
                    entry_price_for_pnl = getattr(strategy, "entry_prices", {}).get(symbol)
                    entry_date_for_pnl = getattr(strategy, "entry_dates", {}).get(symbol)
                    if entry_date_for_pnl and hasattr(entry_date_for_pnl, "date"):
                        entry_date_for_pnl = entry_date_for_pnl.date().isoformat()
                    elif entry_date_for_pnl:
                        entry_date_for_pnl = str(entry_date_for_pnl)[:10]

                    if symbol in strategy.positions:
                        strategy.positions[symbol] -= actual_filled_qty
                        if strategy.positions[symbol] <= 0:
                            del strategy.positions[symbol]
                            if symbol in strategy.entry_dates:
                                del strategy.entry_dates[symbol]
                            if (
                                hasattr(strategy, "entry_prices")
                                and symbol in strategy.entry_prices
                            ):
                                del strategy.entry_prices[symbol]
                            # Remove stop loss when position is fully closed
                            self.stop_loss_manager.remove_stop_loss(symbol)
                            logger.info(f"Stop loss removed for {symbol} (position closed)")
                            total_exposure = max(
                                total_exposure - actual_fill_price * actual_filled_qty, 0
                            )
                            # Clear partial-exit DB flag now that position is gone
                            self.db.set_system_state(
                                f"partial_exit_{strategy.strategy_id}_{symbol}", "0"
                            )
                            strategy._partial_exit_done.discard(symbol)
                        elif signal.get("partial_exit"):
                            # First tranche sold — persist flag so next run skips profit-target exit
                            self.db.set_system_state(
                                f"partial_exit_{strategy.strategy_id}_{symbol}", "1"
                            )
                            logger.info(
                                "Partial exit persisted for %s (%s) — trailing stop now active",
                                symbol,
                                strategy.name,
                            )

                    # Record matched buy→sell P&L for paper trading metrics
                    if entry_price_for_pnl and entry_price_for_pnl > 0:
                        try:
                            exit_reason = signal.get("reasoning", "")
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
                    self._update_position_record(
                        strategy.strategy_id, symbol, -actual_filled_qty, actual_fill_price
                    )
                    # Release cross-strategy dedup lock so other strategies can buy this symbol again
                    self._held_symbols.discard(symbol)

                    trade_record = {
                        "strategy": strategy.name,
                        "symbol": symbol,
                        "shares": actual_filled_qty,
                        "price": price,
                        "action": "SELL",
                        "order_id": order.id,
                    }
                    executed.append(trade_record)
                    self.executed_trades.append(trade_record)
                    self.executed_signals.append(trade_record)
                    self.performance_metrics.add_trade(
                        "SELL", symbol, actual_filled_qty, actual_fill_price, trade_value
                    )
                except Exception as e:
                    logger.error(f"Failed to execute {symbol}: {e}")
                    print(f"  ❌ Failed {symbol}: {e}")
                    if sell_intent_id:
                        try:
                            self.db.update_order_intent_status(
                                sell_intent_id, "FAILED", error=str(e)
                            )
                        except Exception:
                            pass

        return executed, total_exposure

    def _record_performance(self, strategy, current_prices):
        """Record daily performance for a strategy into DB for dynamic allocation."""
        try:
            positions_value = sum(
                shares * current_prices.get(symbol, 0)
                for symbol, shares in strategy.positions.items()
            )
            portfolio_value = strategy.capital + positions_value
            initial = getattr(strategy, "initial_capital", strategy.capital)
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
        """Build local positions with qty and avg price for reconciliation.

        Includes short positions (negative shares). Excluding them caused
        the reconciliation flow to perpetually fail when the broker held a
        short that auto-sync had imported under BROKER_SYNC: the sync wrote
        shares=-N, but this method skipped it, so the reconciler kept
        reporting "exists in broker but not locally". See 2026-05-15 run
        25943767585 for the case (NFLX short of -24 shares).
        """
        local_positions = {}
        for position in self.db.get_positions():
            symbol = position["symbol"]
            shares = float(position["shares"])
            avg_price = float(position["avg_price"])
            if shares == 0:
                continue
            combined = local_positions.setdefault(symbol, {"qty": 0.0, "avg_price": 0.0})
            total_cost = combined["avg_price"] * combined["qty"] + avg_price * shares
            combined["qty"] += shares
            combined["avg_price"] = total_cost / combined["qty"] if combined["qty"] else 0.0
        return local_positions

    def _attempt_auto_sync_and_reconciliation_retry(self, strategies=None):
        """Attempt corrective DB sync to broker and retry reconciliation once.

        Pass `strategies` so that in-memory positions are reloaded from the
        just-synced DB.  Without this, strategy.positions still contains phantom
        symbols (e.g. unfilled OPG BUY positions) even after the DB row is
        deleted, causing spurious SELL attempts and misleading allocation math.
        """
        try:
            from scripts.sync_broker_state import sync_broker_to_database
        except Exception as exc:
            return False, [f"Auto-sync unavailable: {exc}"]

        try:
            logger.warning("Attempting automatic broker-state sync before reconciliation retry...")
            synced = sync_broker_to_database(self.db.db_path)
            if not synced:
                return False, ["Auto-sync completed with unresolved discrepancies"]

            # Reload in-memory positions so strategy logic reflects the cleaned DB.
            if strategies:
                for strategy in strategies:
                    self._load_strategy_positions(strategy)

            self._refresh_account_state()
            local_positions = self._build_local_positions()
            retry_success, retry_discrepancies = self.broker_reconciler.reconcile_daily(
                local_positions=local_positions,
                local_cash=self.cash_available,
            )
            return retry_success, retry_discrepancies
        except Exception as exc:
            return False, [f"Auto-sync retry failed: {exc}"]

    def _update_position_record(
        self, strategy_id, symbol, shares_delta, exec_price, entry_date=None, atr=None
    ):
        """Persist position updates for reconciliation."""
        existing = self.db.get_position(strategy_id, symbol)
        if existing:
            current_shares = float(existing["shares"])
            current_avg = float(existing["avg_price"])
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
        """Calculate strategy allocations from actual closed-trade P&L.

        Previously used strategy_performance.portfolio_value history, which is
        contaminated by the allocator's own capital re-assignments (a strategy
        getting more budget registers as a large positive "return", creating a
        self-reinforcing feedback loop). Using per-trade gross_pnl_pct from
        trade_pnl_detail gives genuine edge signal — the same data used by the
        trailing Sharpe logger and health scorer.
        """
        performance_data = {}
        for strategy in strategies:
            returns = self.db.get_strategy_trade_returns(strategy.strategy_id, days=60)
            performance_data[strategy.strategy_id] = returns

        config_key_map = {s.name.lower().replace(" ", "_"): s.strategy_id for s in strategies}

        # Build per-strategy max allocation from config overrides
        raw_overrides = self.config.get("strategies.allocation_overrides", {}) or {}
        per_strategy_max: dict[int, float] = {}
        for config_key, max_pct in raw_overrides.items():
            sid = config_key_map.get(config_key)
            if sid is not None:
                per_strategy_max[sid] = float(max_pct)
                logger.info(f"Allocation cap override: {config_key} → {max_pct*100:.0f}%")

        # Build prior Sharpes from backtest results — used when live history < 20 days
        raw_priors = self.config.get("strategies.backtest_sharpe_priors", {}) or {}
        prior_sharpes: dict[int, float] = {}
        for config_key, sharpe in raw_priors.items():
            sid = config_key_map.get(config_key)
            if sid is not None:
                prior_sharpes[sid] = float(sharpe)

        strategy_ids = [strategy.strategy_id for strategy in strategies]
        return self.dynamic_allocator.calculate_allocations(
            strategy_ids,
            performance_data,
            per_strategy_max=per_strategy_max,
            prior_sharpes=prior_sharpes,
        )

    def _calculate_strategy_exposures(self, strategies, current_prices):
        """Calculate current exposure per strategy, including BROKER_SYNC."""
        exposures = {}
        for strategy in strategies:
            exposure = 0.0
            for symbol, shares in strategy.positions.items():
                exposure += shares * current_prices.get(symbol, 0)
            exposures[strategy.strategy_id] = exposure

        # Include BROKER_SYNC positions so they count toward portfolio heat.
        # BROKER_SYNC is not a canonical strategy object, so it never appears
        # in the loop above — without this, its $85k of positions is invisible
        # to the heat limit and the system can over-deploy capital.
        try:
            import sqlite3 as _sqlite3

            _conn = _sqlite3.connect(self.db.db_path)
            _cur = _conn.cursor()
            _cur.execute(
                """
                SELECT p.symbol, p.shares
                FROM positions p
                JOIN strategies s ON p.strategy_id = s.id
                WHERE s.name = 'BROKER_SYNC' AND p.shares > 0
                """
            )
            bs_rows = _cur.fetchall()
            _conn.close()
            bs_exposure = sum(shares * current_prices.get(sym, 0) for sym, shares in bs_rows)
            if bs_exposure > 0:
                exposures["BROKER_SYNC"] = bs_exposure
                logger.info("BROKER_SYNC exposure included in heat: $%.0f", bs_exposure)
        except Exception as _exc:
            logger.warning("Could not compute BROKER_SYNC exposure: %s", _exc)

        return exposures

    def _apply_allocations(self, strategies, allocations, exposures):
        """Apply capital allocations to strategies and cash manager"""
        min_cash_pct = self.config.get("risk.min_cash_allocation_pct", 0.05)
        for strategy in strategies:
            allocation = allocations.get(strategy.strategy_id, strategy.capital)
            strategy.capital = max(allocation - exposures.get(strategy.strategy_id, 0), 0)
        self.cash_manager.set_allocations(allocations, exposures, min_cash_pct=min_cash_pct)

    def _format_signal_flowchart(self, strategy_name, signal):
        """Build a flowchart-style reasoning chain for a signal."""
        action = str(signal.get("action", "BUY")).upper()
        reasoning = str(signal.get("reasoning", "")).strip()
        symbol = signal.get("symbol", "N/A")

        news_events = []
        explicit_news_events = signal.get("news_events")
        if isinstance(explicit_news_events, list):
            news_events.extend(
                [str(item).strip() for item in explicit_news_events if str(item).strip()]
            )

        for key in ["news_headline", "headline", "article_title", "news_summary"]:
            value = signal.get(key)
            if value:
                news_events.append(str(value).strip())

        has_news_context = bool(news_events) or "news" in strategy_name.lower()
        if not has_news_context:
            return None

        chain_parts = [f"Symbol {symbol}"]
        for event in news_events[:3]:
            chain_parts.append(f"News: {event}")

        if reasoning:
            chain_parts.append(reasoning)

        if action == "BUY":
            chain_parts.append("Price expected to rise")
        else:
            chain_parts.append("Price expected to weaken")

        chain_parts.append(f"Signal generated ({action})")
        return " -> ".join(chain_parts)

    def build_signal_reasoning_chains(self):
        """Build reasoning chains for email reporting from generated signals."""
        if not getattr(self, "raw_signals_by_strategy", None):
            return []

        executed_keys = {
            (str(trade.get("symbol")), str(trade.get("action", "")).upper())
            for trade in self.executed_trades
        }

        chains = []
        for strategy_name, signals in self.raw_signals_by_strategy.items():
            for signal in signals or []:
                flowchart = self._format_signal_flowchart(strategy_name, signal)
                if not flowchart:
                    continue

                symbol = str(signal.get("symbol", "N/A"))
                action = str(signal.get("action", "BUY")).upper()
                chains.append(
                    {
                        "strategy": strategy_name,
                        "symbol": symbol,
                        "action": action,
                        "flowchart": flowchart,
                        "executed": (symbol, action) in executed_keys,
                    }
                )

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
            perf = self.db.get_latest_performance(strat["id"])
            trades = self.db.get_strategy_trades(strat["id"])

            if perf:
                return_pct = perf.get("total_return_pct", 0)
                num_positions = perf.get("num_positions", 0)
            else:
                return_pct = 0
                num_positions = 0

            print(
                f"{strat['name']:<25} ${strat['capital_allocation']:<11,.0f} {return_pct:>+8.2f}% {num_positions:<10} {len(trades):<10}"
            )

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
        runner._set_run_stage("LOAD_DATA", "RUNNING")

        # Load market data with validation
        print("\n📊 Loading and validating market data...")
        market_data = runner.load_market_data()

        if market_data is None:
            error_msg = "Failed to load market data"
            logger.error(error_msg)
            runner._set_run_stage("LOAD_DATA", "FAILED", error_message=error_msg)
            if runner:
                runner.email_notifier.send_error_alert(error_msg, "\n".join(runner.errors))
            sys.exit(1)
        runner._set_run_stage("LOAD_DATA", "SUCCESS")

        signals, pnl_metrics = runner.execute_pipeline(market_data)
        slo_metrics = runner.emit_slo_metrics(start_time, signals, pnl_metrics)

        print("\n" + "=" * 80)
        print(f"✅ EXECUTION COMPLETE - {len(signals)} trades executed")
        print("=" * 80)
        runner._set_run_stage(
            "EXECUTION_COMPLETE",
            "SUCCESS",
            metadata={"trades_executed": len(signals), "slo": slo_metrics},
        )

        # Send email summary
        positions_data: list = []
        try:
            positions = runner.trading_client.get_all_positions()

            # Enrich broker positions with days_held from DB (F3)
            db_positions = {p["symbol"]: p for p in runner.db.get_positions()}
            today = datetime.now().date()
            positions_data = []
            for p in positions:
                db_pos = db_positions.get(p.symbol, {})
                entry_date_str = db_pos.get("entry_date", "") or ""
                days_held = None
                if entry_date_str:
                    try:
                        ed = datetime.strptime(entry_date_str[:10], "%Y-%m-%d").date()
                        days_held = (today - ed).days
                    except ValueError:
                        pass
                positions_data.append(
                    {
                        "symbol": p.symbol,
                        "shares": float(p.qty),
                        "entry_price": float(p.avg_entry_price),
                        "current_price": float(p.current_price),
                        "days_held": days_held,
                        "strategy_name": db_pos.get("strategy_name", ""),
                    }
                )

            logger.info(
                "Skipping runtime notifier daily summary; "
                "digest delivery is unified via scripts/generate_daily_email.py"
            )
        except Exception as e:
            logger.error(f"Failed to send email summary: {e}")

        try:
            runner._set_run_stage("ARTIFACTS", "RUNNING")
            writer = DailyArtifactWriter()
            latest_date = market_data.index.max()
            data_freshness_hours = (datetime.now() - latest_date).total_seconds() / 3600
            data_freshness = f"{data_freshness_hours:.1f}h old"
            regime = runner.regime_detector.get_status(market_data)
            warnings = []
            if runner.pending_orders:
                warnings.append(f"{len(runner.pending_orders)} orders pending confirmation")
            portfolio_heat = 0.0
            if runner.portfolio_value > 0:
                total_exposure = sum(pos["shares"] * pos["current_price"] for pos in positions_data)
                portfolio_heat = (total_exposure / runner.portfolio_value) * 100

            # Paper trading validation: write daily snapshot
            try:
                import json as _json

                _alloc_json = (
                    _json.dumps(
                        {
                            str(s.strategy_id): round(getattr(s, "capital", 0), 2)
                            for s in runner.strategies_cache
                            if hasattr(s, "capital")
                        }
                    )
                    if hasattr(runner, "strategies_cache")
                    else None
                )
                runner.db.log_daily_snapshot(
                    run_id=runner.run_id,
                    portfolio_value=runner.portfolio_value,
                    cash=runner.cash_available,
                    positions_value=total_exposure,
                    heat_pct=portfolio_heat,
                    vix=regime.get("vix"),
                    regime=f"{regime.get('volatility_regime','?')}/{regime.get('trend_regime','?')}",
                    allocation_json=_alloc_json,
                )
                logger.info("Daily portfolio snapshot recorded")
            except Exception as _snap_exc:
                logger.warning("log_daily_snapshot failed: %s", _snap_exc)

            placed_orders = [
                {
                    "symbol": trade["symbol"],
                    "side": trade["action"],
                    "qty": trade["shares"],
                    "price": trade["price"],
                }
                for trade in runner.executed_trades
            ]
            fallback_fills = [
                {
                    "symbol": trade["symbol"],
                    "side": trade["action"],
                    "qty": trade["shares"],
                    "price": trade["price"],
                }
                for trade in runner.executed_trades
            ]
            open_positions = [
                {
                    "symbol": pos["symbol"],
                    "qty": pos["shares"],
                    "avg_price": pos["entry_price"],
                    "market_value": pos["shares"] * pos["current_price"],
                    "unrealized_pl": (pos["current_price"] - pos["entry_price"]) * pos["shares"],
                    "exposure_pct": (
                        pos["shares"] * pos["current_price"] / runner.portfolio_value * 100
                    )
                    if runner.portfolio_value > 0
                    else 0,
                }
                for pos in positions_data
            ]

            artifact = create_artifact_data(
                vix=regime.get("vix", 0),
                regime_classification=regime.get("volatility_regime", "UNKNOWN"),
                raw_signals=runner.raw_signals_by_strategy,
                rejected_signals=runner.rejected_signals,
                executed_signals=runner.executed_signals,
                placed_orders=placed_orders,
                filled_orders=runner.confirmed_fills or fallback_fills,
                rejected_orders=runner.rejected_orders,
                portfolio_heat=portfolio_heat,
                daily_pnl=pnl_metrics["daily_pnl"],
                cumulative_pnl=pnl_metrics["cumulative_pnl"],
                drawdown=pnl_metrics["drawdown"],
                max_drawdown=pnl_metrics["max_drawdown"],
                circuit_breaker_state="ACTIVE"
                if runner.portfolio_risk.trading_halted
                else "INACTIVE",
                open_positions=open_positions,
                runtime_seconds=time.time() - start_time,
                data_freshness=data_freshness,
                errors=runner.errors,
                warnings=warnings,
                reconciliation_status=runner.reconciliation_status,
                portfolio_value=runner.portfolio_value,
                cash=runner.cash_available,
            )
            artifact["system_health"][
                "reconciliation_discrepancies"
            ] = runner.reconciliation_discrepancies
            artifact["system_health"]["slo_metrics"] = slo_metrics
            artifact["system_health"]["alpha_vantage_usage"] = runner.alpha_vantage_usage
            writer.write_daily_artifact(datetime.now().strftime("%Y-%m-%d"), artifact)
            runner._set_run_stage("ARTIFACTS", "SUCCESS")
        except Exception as e:
            logger.error(f"Failed to write daily artifact: {e}")
            runner._set_run_stage("ARTIFACTS", "FAILED", error_message=str(e))

        logger.info("Multi-strategy execution completed successfully")
        runner._set_run_stage("COMPLETE", "SUCCESS", completed=True)

    except Exception as e:
        error_msg = f"Fatal error: {e}"
        logger.error(error_msg, exc_info=True)
        print(f"\n❌ FATAL ERROR: {e}")
        if runner:
            runner._set_run_stage("FAILED", "FAILED", error_message=error_msg, completed=True)

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
