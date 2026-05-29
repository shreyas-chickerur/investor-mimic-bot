#!/usr/bin/env python3
"""
Trading Database Adapter
Single source of truth for paper trading operational validation
"""
from __future__ import annotations

import json
import logging
import random
import sqlite3
import string
from contextlib import closing
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class TradingDatabase:
    """Database adapter for trading system with proper schema"""

    def __init__(self, db_path="trading.db", run_id=None):
        self.db_path = db_path
        self.run_id = run_id or self._generate_run_id()
        self._init_database()

    def _generate_run_id(self) -> str:
        """Generate unique run_id: YYYYMMDD_HHMMSS_<random_suffix>"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"{timestamp}_{suffix}"

    def _init_database(self):
        """Initialize trading database schema"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")  # concurrent readers don't block each other
            conn.execute("PRAGMA synchronous=NORMAL")  # safe + faster than FULL for WAL mode
            cursor = conn.cursor()

            # Strategies table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    capital_allocation REAL NOT NULL,
                    initial_capital REAL NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Signals table with asof_date and terminal state tracking
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    strategy_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    confidence REAL,
                    reasoning TEXT,
                    asof_date TEXT NOT NULL,
                    generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    terminal_state TEXT,
                    terminal_reason TEXT,
                    terminal_at TEXT,
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
                )
            """
            )

            # Create indexes for common queries (Phase 3.1 optimization)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_run_id ON signals(run_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_signals_terminal_state ON signals(terminal_state)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_signals_generated_at ON signals(generated_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_signals_strategy_date ON signals(strategy_id, generated_at)"
            )

            # Trades table with execution costs
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    strategy_id INTEGER NOT NULL,
                    signal_id INTEGER,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    shares REAL NOT NULL,
                    requested_price REAL NOT NULL,
                    exec_price REAL NOT NULL,
                    slippage_cost REAL DEFAULT 0,
                    commission_cost REAL DEFAULT 0,
                    total_cost REAL DEFAULT 0,
                    notional REAL NOT NULL,
                    order_id TEXT,
                    executed_at TEXT NOT NULL,
                    pnl REAL,
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id),
                    FOREIGN KEY (signal_id) REFERENCES signals(id)
                )
            """
            )

            # Indexes for trades: run_id lookups + strategy/date range queries (health scorer, performance report)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_run_id ON trades(run_id)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_trades_strategy_date ON trades(strategy_id, executed_at)"
            )

            # Positions table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    shares REAL NOT NULL,
                    avg_price REAL NOT NULL,
                    current_price REAL,
                    market_value REAL,
                    unrealized_pnl REAL,
                    entry_price REAL,
                    entry_date TEXT,
                    atr REAL,
                    stop_loss_price REAL,
                    last_updated TEXT NOT NULL,
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id),
                    UNIQUE(strategy_id, symbol)
                )
            """
            )

            # Broker state snapshots
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS broker_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    snapshot_date TEXT NOT NULL,
                    snapshot_type TEXT NOT NULL,
                    cash REAL NOT NULL,
                    portfolio_value REAL NOT NULL,
                    buying_power REAL NOT NULL,
                    positions_json TEXT,
                    reconciliation_status TEXT,
                    discrepancies_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Add index on run_id for performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_broker_state_run_id ON broker_state(run_id)"
            )

            # System state
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Run state machine tracking
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS run_state (
                    run_id TEXT PRIMARY KEY,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    metadata_json TEXT,
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_run_state_status ON run_state(status)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_run_state_updated_at ON run_state(updated_at)"
            )

            # Notification outbox (decouples runtime from delivery side effects)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    channel TEXT NOT NULL,
                    category TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    sent_at TEXT
                )
            """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_notification_outbox_status ON notification_outbox(status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_notification_outbox_run_id ON notification_outbox(run_id)"
            )

            # Per-run SLO metrics for observability
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS run_slo_metrics (
                    run_id TEXT PRIMARY KEY,
                    metrics_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """
            )

            # Signal funnel tracking (portfolio-level per run)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_funnel (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    strategy_id INTEGER NOT NULL,
                    strategy_name TEXT NOT NULL,
                    raw_signals_count INTEGER DEFAULT 0,
                    after_regime_count INTEGER DEFAULT 0,
                    after_correlation_count INTEGER DEFAULT 0,
                    after_risk_count INTEGER DEFAULT 0,
                    executed_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
                )
            """
            )

            # Signal rejection reasons (per-signal detail)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_rejections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    signal_id INTEGER,
                    strategy_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    details_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (signal_id) REFERENCES signals(id),
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
                )
            """
            )

            # Order intents (idempotency tracking)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS order_intents (
                    intent_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    strategy_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    target_qty REAL NOT NULL,
                    status TEXT NOT NULL,
                    broker_order_id TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    submitted_at TEXT,
                    acked_at TEXT,
                    filled_at TEXT,
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
                )
            """
            )

            # Add indexes for performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_signal_funnel_run_id ON signal_funnel(run_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_signal_rejections_run_id ON signal_rejections(run_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_signal_rejections_stage ON signal_rejections(stage)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_rejections_strategy_date ON signal_rejections(strategy_id, created_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_order_intents_run_id ON order_intents(run_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_order_intents_status ON order_intents(status)"
            )

            # Per-strategy daily performance snapshots (feeds dynamic allocator)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    strategy_id INTEGER NOT NULL,
                    snapshot_date TEXT NOT NULL,
                    portfolio_value REAL NOT NULL,
                    cash REAL NOT NULL,
                    positions_value REAL NOT NULL,
                    total_return_pct REAL NOT NULL,
                    num_positions INTEGER DEFAULT 0,
                    num_trades INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
                )
            """
            )
            # Schema migration: add snapshot_date if missing from a pre-existing DB.
            # Must run BEFORE the index creation below which references snapshot_date.
            cursor.execute("PRAGMA table_info(strategy_performance)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "snapshot_date" not in existing_cols:
                cursor.execute(
                    "ALTER TABLE strategy_performance ADD COLUMN snapshot_date TEXT NOT NULL DEFAULT ''"
                )
                logger.info("Migrated strategy_performance: added snapshot_date column")

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_strategy_perf_strat ON strategy_performance(strategy_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_strategy_perf_date ON strategy_performance(snapshot_date)"
            )

            # Paper trading validation: portfolio-level daily snapshot
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_portfolio_snapshot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    snapshot_date TEXT NOT NULL,
                    portfolio_value REAL NOT NULL,
                    cash REAL NOT NULL,
                    positions_value REAL NOT NULL,
                    heat_pct REAL,
                    daily_pnl REAL,
                    daily_pnl_pct REAL,
                    cumulative_pnl REAL,
                    drawdown_pct REAL,
                    peak_value REAL,
                    num_open_positions INTEGER DEFAULT 0,
                    vix REAL,
                    regime TEXT,
                    allocation_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(snapshot_date)
                )
            """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_daily_snap_date ON daily_portfolio_snapshot(snapshot_date)"
            )

            # Per-trade P&L detail: matched BUY→SELL for win rate and profit factor
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_pnl_detail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id INTEGER NOT NULL,
                    strategy_name TEXT,
                    symbol TEXT NOT NULL,
                    buy_run_id TEXT,
                    sell_run_id TEXT NOT NULL,
                    entry_date TEXT,
                    exit_date TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    shares REAL NOT NULL,
                    gross_pnl REAL NOT NULL,
                    gross_pnl_pct REAL NOT NULL,
                    hold_days INTEGER,
                    exit_reason TEXT,
                    is_winner INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
                )
            """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_trade_pnl_strategy ON trade_pnl_detail(strategy_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_trade_pnl_exit ON trade_pnl_detail(exit_date)"
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS fill_quality (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    strategy_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    expected_price REAL NOT NULL,
                    fill_price REAL NOT NULL,
                    shares REAL NOT NULL,
                    deviation_bps INTEGER NOT NULL,
                    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
                )
            """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_fill_quality_run ON fill_quality(run_id)"
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS stop_loss_state (
                    symbol TEXT PRIMARY KEY,
                    stop_price REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_atr REAL NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.commit()

    def upsert_run_state(
        self,
        stage: str,
        status: str,
        error_message: Optional[str] = None,
        metadata: Optional[dict] = None,
        completed: bool = False,
    ) -> None:
        """Create or update run-state machine row for the current run."""
        now = datetime.now().isoformat()
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT run_id FROM run_state WHERE run_id = ?", (self.run_id,))
            exists = cursor.fetchone() is not None
            metadata_json = json.dumps(metadata) if metadata else None

            if exists:
                cursor.execute(
                    """
                    UPDATE run_state
                    SET stage = ?,
                        status = ?,
                        error_message = ?,
                        metadata_json = ?,
                        updated_at = ?,
                        completed_at = CASE WHEN ? THEN ? ELSE completed_at END
                    WHERE run_id = ?
                    """,
                    (stage, status, error_message, metadata_json, now, completed, now, self.run_id),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO run_state
                    (run_id, stage, status, error_message, metadata_json, started_at, updated_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.run_id,
                        stage,
                        status,
                        error_message,
                        metadata_json,
                        now,
                        now,
                        now if completed else None,
                    ),
                )

            conn.commit()

    def enqueue_notification(self, channel: str, category: str, subject: str, body: str) -> int:
        """Queue a notification for asynchronous delivery."""
        now = datetime.now().isoformat()
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO notification_outbox
                (run_id, channel, category, subject, body, status, attempts, created_at)
                VALUES (?, ?, ?, ?, ?, 'PENDING', 0, ?)
                """,
                (self.run_id, channel, category, subject, body, now),
            )
            notification_id = cursor.lastrowid
            conn.commit()
        return notification_id

    def fetch_pending_notifications(self, limit: int = 50) -> list[dict]:
        """Fetch pending/failed notifications for delivery workers."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM notification_outbox
                WHERE status IN ('PENDING', 'FAILED')
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = [dict(r) for r in cursor.fetchall()]
        return rows

    def mark_notification_sent(self, notification_id: int) -> None:
        """Mark outbox notification as sent."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE notification_outbox
                SET status = 'SENT',
                    attempts = attempts + 1,
                    sent_at = ?
                WHERE id = ?
                """,
                (datetime.now().isoformat(), notification_id),
            )
            conn.commit()

    def mark_notification_failed(self, notification_id: int, error_message: str) -> None:
        """Mark outbox notification delivery failure."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE notification_outbox
                SET status = 'FAILED',
                    attempts = attempts + 1,
                    last_error = ?
                WHERE id = ?
                """,
                (error_message[:1000], notification_id),
            )
            conn.commit()

    def get_consecutive_failed_runs(self, max_lookback: int = 20) -> int:
        """Return count of consecutive failed runs from most recent run backward."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT status
                FROM run_state
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max_lookback,),
            )
            rows = [str(r[0]).upper() for r in cursor.fetchall()]

        failures = 0
        for status in rows:
            if status == "FAILED":
                failures += 1
            else:
                break
        return failures

    def save_run_slo_metrics(self, metrics: dict) -> None:
        """Persist per-run SLO metrics for observability dashboards and audits."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO run_slo_metrics (run_id, metrics_json, created_at)
                VALUES (?, ?, ?)
                """,
                (self.run_id, json.dumps(metrics), datetime.now().isoformat()),
            )
            conn.commit()

    def log_daily_snapshot(
        self,
        run_id: str,
        portfolio_value: float,
        cash: float,
        positions_value: float,
        heat_pct: float = None,
        vix: float = None,
        regime: str = None,
        allocation_json: str = None,
    ):
        """Record end-of-run portfolio state for paper trading validation tracking."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")

            # Compute daily P&L vs yesterday's snapshot
            cursor.execute(
                "SELECT portfolio_value, peak_value FROM daily_portfolio_snapshot ORDER BY snapshot_date DESC LIMIT 1"
            )
            prev = cursor.fetchone()
            prev_value = prev[0] if prev else portfolio_value
            prev_peak = prev[1] if prev else portfolio_value

            daily_pnl = portfolio_value - prev_value
            daily_pnl_pct = daily_pnl / prev_value if prev_value else 0.0
            peak_value = max(prev_peak, portfolio_value)

            # Cumulative P&L: use first recorded portfolio snapshot as baseline.
            # SUM(initial_capital) across all strategies exceeds the actual broker account
            # value because strategies were added over time — each carries its own budget,
            # making the total appear far larger than what the broker ever held.
            cursor.execute(
                "SELECT portfolio_value FROM daily_portfolio_snapshot ORDER BY snapshot_date ASC LIMIT 1"
            )
            first_snap = cursor.fetchone()
            initial_capital = first_snap[0] if first_snap else portfolio_value
            cumulative_pnl = portfolio_value - initial_capital

            drawdown_pct = (peak_value - portfolio_value) / peak_value if peak_value else 0.0

            # Count actual open positions rather than hardcoding 0
            cursor.execute("SELECT COUNT(*) FROM positions WHERE shares > 0")
            num_open_positions_row = cursor.fetchone()
            num_open_positions = num_open_positions_row[0] if num_open_positions_row else 0

            cursor.execute(
                """
                INSERT INTO daily_portfolio_snapshot
                (run_id, snapshot_date, portfolio_value, cash, positions_value,
                 heat_pct, daily_pnl, daily_pnl_pct, cumulative_pnl, drawdown_pct,
                 peak_value, num_open_positions, vix, regime, allocation_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_date) DO UPDATE SET
                    portfolio_value = excluded.portfolio_value,
                    cash = excluded.cash,
                    positions_value = excluded.positions_value,
                    heat_pct = excluded.heat_pct,
                    daily_pnl = excluded.daily_pnl,
                    daily_pnl_pct = excluded.daily_pnl_pct,
                    cumulative_pnl = excluded.cumulative_pnl,
                    drawdown_pct = excluded.drawdown_pct,
                    peak_value = excluded.peak_value,
                    vix = excluded.vix,
                    regime = excluded.regime,
                    allocation_json = excluded.allocation_json
            """,
                (
                    run_id,
                    today,
                    portfolio_value,
                    cash,
                    positions_value,
                    heat_pct,
                    daily_pnl,
                    daily_pnl_pct,
                    cumulative_pnl,
                    drawdown_pct,
                    peak_value,
                    num_open_positions,
                    vix,
                    regime,
                    allocation_json,
                ),
            )
            conn.commit()

    def log_trade_pnl(
        self,
        strategy_id: int,
        strategy_name: str,
        symbol: str,
        sell_run_id: str,
        entry_price: float,
        exit_price: float,
        shares: float,
        entry_date: str = None,
        exit_reason: str = None,
    ):
        """Record matched buy→sell P&L for win-rate and profit-factor tracking."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            gross_pnl = (exit_price - entry_price) * shares
            gross_pnl_pct = (exit_price - entry_price) / entry_price if entry_price else 0.0
            exit_date = datetime.now().strftime("%Y-%m-%d")
            hold_days = None
            if entry_date:
                try:
                    from datetime import date
                    from datetime import datetime as _dt

                    if isinstance(entry_date, _dt):
                        ed = entry_date.date()
                    elif isinstance(entry_date, date):
                        ed = entry_date
                    else:
                        ed = date.fromisoformat(str(entry_date)[:10])
                    hold_days = (date.today() - ed).days
                    # Normalize entry_date to string for the INSERT
                    if not isinstance(entry_date, str):
                        entry_date = ed.isoformat()
                except Exception:
                    pass

            # Look up buy_run_id from trades table
            cursor.execute(
                "SELECT run_id FROM trades WHERE strategy_id=? AND symbol=? AND action='BUY' ORDER BY executed_at DESC LIMIT 1",
                (strategy_id, symbol),
            )
            buy_row = cursor.fetchone()
            buy_run_id = buy_row[0] if buy_row else None

            cursor.execute(
                """
                INSERT INTO trade_pnl_detail
                (strategy_id, strategy_name, symbol, buy_run_id, sell_run_id,
                 entry_date, exit_date, entry_price, exit_price, shares,
                 gross_pnl, gross_pnl_pct, hold_days, exit_reason, is_winner)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    strategy_id,
                    strategy_name,
                    symbol,
                    buy_run_id,
                    sell_run_id,
                    entry_date,
                    exit_date,
                    entry_price,
                    exit_price,
                    shares,
                    gross_pnl,
                    gross_pnl_pct,
                    hold_days,
                    exit_reason,
                    1 if gross_pnl > 0 else 0,
                ),
            )
            conn.commit()

    def get_paper_trading_stats(self, days: int = 30) -> dict:
        """Return win rate, profit factor, avg hold days, and streak stats for the last N days."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            cursor.execute(
                """
                SELECT gross_pnl, gross_pnl_pct, hold_days, is_winner, strategy_name
                FROM trade_pnl_detail WHERE exit_date >= ? ORDER BY exit_date
            """,
                (since,),
            )
            rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT snapshot_date, portfolio_value, daily_pnl_pct, drawdown_pct, cumulative_pnl
                FROM daily_portfolio_snapshot WHERE snapshot_date >= ?
                ORDER BY snapshot_date
            """,
                (since,),
            )
            snapshots = cursor.fetchall()

        if not rows:
            return {
                "trades": 0,
                "win_rate": None,
                "profit_factor": None,
                "avg_hold_days": None,
                "snapshots": snapshots,
            }

        wins = [r for r in rows if r[3] == 1]
        losses = [r for r in rows if r[3] == 0]
        gross_wins = sum(r[0] for r in wins)
        gross_losses = abs(sum(r[0] for r in losses)) or 1e-9
        hold_days_list = [r[2] for r in rows if r[2] is not None]

        return {
            "trades": len(rows),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(rows),
            "profit_factor": gross_wins / gross_losses,
            "avg_hold_days": sum(hold_days_list) / len(hold_days_list) if hold_days_list else None,
            "total_pnl": sum(r[0] for r in rows),
            "avg_win_pct": sum(r[1] for r in wins) / len(wins) if wins else 0,
            "avg_loss_pct": sum(r[1] for r in losses) / len(losses) if losses else 0,
            "snapshots": snapshots,
        }

    def create_strategy(self, name: str, description: str, capital: float) -> int:
        """Create or get strategy"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            # Try to get existing
            cursor.execute("SELECT id FROM strategies WHERE name = ?", (name,))
            row = cursor.fetchone()

            if row:
                strategy_id = row[0]
            else:
                cursor.execute(
                    """
                    INSERT INTO strategies (name, description, capital_allocation, initial_capital)
                    VALUES (?, ?, ?, ?)
                """,
                    (name, description, capital, capital),
                )
                strategy_id = cursor.lastrowid
                conn.commit()

        return strategy_id

    def get_strategy_pnl_stats(self, strategy_id: int) -> dict:
        """Return closed-trade stats for a single strategy from trade_pnl_detail.

        Returns dict with keys: trades, win_rate, avg_win_pct, avg_loss_pct.
        Returns None when trade count < 1.
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT gross_pnl, gross_pnl_pct, is_winner
                FROM trade_pnl_detail
                WHERE strategy_id = ?
                """,
                (strategy_id,),
            )
            rows = cursor.fetchall()
        if not rows:
            return {"trades": 0, "win_rate": None, "avg_win_pct": None, "avg_loss_pct": None}
        wins = [r for r in rows if r[2] == 1]
        losses = [r for r in rows if r[2] == 0]
        return {
            "trades": len(rows),
            "win_rate": len(wins) / len(rows),
            "avg_win_pct": sum(r[1] for r in wins) / len(wins) if wins else 0.0,
            "avg_loss_pct": sum(abs(r[1]) for r in losses) / len(losses) if losses else 0.0,
        }

    def update_strategy_capital_allocation(self, strategy_id: int, capital: float) -> None:
        """Update capital_allocation for an existing strategy."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "UPDATE strategies SET capital_allocation = ? WHERE id = ?",
                (capital, strategy_id),
            )
            conn.commit()

    def log_signal(
        self,
        strategy_id: int,
        symbol: str,
        signal_type: str,
        confidence: float,
        reasoning: str,
        asof_date: str,
    ) -> int:
        """Log a trading signal"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO signals
                (run_id, strategy_id, symbol, signal_type, confidence, reasoning, asof_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (self.run_id, strategy_id, symbol, signal_type, confidence, reasoning, asof_date),
            )

            signal_id = cursor.lastrowid
            conn.commit()

        return signal_id

    def update_signal_terminal_state(self, signal_id: int, terminal_state: str, reason: str):
        """Update signal with terminal state"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE signals
                SET terminal_state = ?, terminal_reason = ?, terminal_at = ?
                WHERE id = ?
            """,
                (terminal_state, reason, datetime.now().isoformat(), signal_id),
            )

            conn.commit()

    def log_trade(
        self,
        strategy_id: int,
        signal_id: Optional[int],
        symbol: str,
        action: str,
        shares: float,
        requested_price: float,
        exec_price: float,
        slippage_cost: float,
        commission_cost: float,
        order_id: str,
        pnl: Optional[float] = None,
    ) -> int:
        """Log a trade with execution costs and P&L"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            total_cost = slippage_cost + commission_cost

            # Calculate notional
            if action == "BUY":
                notional = exec_price * shares + total_cost
            else:  # SELL
                notional = exec_price * shares - total_cost

            cursor.execute(
                """
                INSERT INTO trades
                (run_id, strategy_id, signal_id, symbol, action, shares, requested_price, exec_price,
                 slippage_cost, commission_cost, total_cost, notional, order_id, executed_at, pnl)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    self.run_id,
                    strategy_id,
                    signal_id,
                    symbol,
                    action,
                    shares,
                    requested_price,
                    exec_price,
                    slippage_cost,
                    commission_cost,
                    total_cost,
                    notional,
                    order_id,
                    datetime.now().isoformat(),
                    pnl,
                ),
            )

            trade_id = cursor.lastrowid
            conn.commit()

        return trade_id

    def log_fill_quality(
        self,
        strategy_id: int,
        symbol: str,
        action: str,
        expected_price: float,
        fill_price: float,
        shares: float,
        deviation_bps: int,
    ) -> None:
        """Record fill price vs expected price for slippage monitoring."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO fill_quality
                (run_id, strategy_id, symbol, action, expected_price, fill_price, shares, deviation_bps)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.run_id,
                    strategy_id,
                    symbol,
                    action,
                    expected_price,
                    fill_price,
                    shares,
                    deviation_bps,
                ),
            )
            conn.commit()

    def update_position(
        self,
        strategy_id: int,
        symbol: str,
        shares: float,
        avg_price: float,
        current_price: Optional[float] = None,
        entry_date: Optional[str] = None,
        atr: Optional[float] = None,
    ):
        """Update or create position. entry_date and atr are only written on the
        first insert; subsequent updates preserve the original values via COALESCE."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            market_value = shares * current_price if current_price else shares * avg_price
            unrealized_pnl = (current_price - avg_price) * shares if current_price else 0

            cursor.execute(
                """
                INSERT INTO positions
                (strategy_id, symbol, shares, avg_price, entry_price, current_price, market_value,
                 unrealized_pnl, entry_date, atr, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(strategy_id, symbol) DO UPDATE SET
                    shares = excluded.shares,
                    avg_price = excluded.avg_price,
                    entry_price = COALESCE(positions.entry_price, excluded.entry_price),
                    current_price = excluded.current_price,
                    market_value = excluded.market_value,
                    unrealized_pnl = excluded.unrealized_pnl,
                    entry_date = COALESCE(positions.entry_date, excluded.entry_date),
                    atr = COALESCE(positions.atr, excluded.atr),
                    last_updated = excluded.last_updated
            """,
                (
                    strategy_id,
                    symbol,
                    shares,
                    avg_price,
                    avg_price,
                    current_price,
                    market_value,
                    unrealized_pnl,
                    entry_date,
                    atr,
                    datetime.now().isoformat(),
                ),
            )

            conn.commit()

    def refresh_position_prices(self, price_map: dict) -> int:
        """Bulk-update current_price and unrealized_pnl for all open positions.

        Args:
            price_map: {symbol: latest_close_price}

        Returns:
            Number of positions updated.
        """
        if not price_map:
            return 0
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            updated = 0
            for symbol, price in price_map.items():
                cursor.execute(
                    """UPDATE positions
                       SET current_price  = ?,
                           market_value   = shares * ?,
                           unrealized_pnl = (? - avg_price) * shares,
                           last_updated   = ?
                       WHERE symbol = ? AND shares != 0""",
                    (price, price, price, datetime.now().isoformat(), symbol),
                )
                updated += cursor.rowcount
            conn.commit()
        return updated

    def delete_position(self, strategy_id: int, symbol: str):
        """Delete a position (when fully closed)"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM positions WHERE strategy_id = ? AND symbol = ?", (strategy_id, symbol)
            )

            conn.commit()

    def save_broker_state(
        self,
        snapshot_date: str,
        snapshot_type: str,
        cash: float,
        portfolio_value: float,
        buying_power: float,
        positions: list[dict],
        reconciliation_status: str,
        discrepancies: list[str],
    ):
        """Save broker state snapshot

        Args:
            snapshot_type: 'START', 'RECONCILIATION', or 'END'
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO broker_state
                (run_id, snapshot_date, snapshot_type, cash, portfolio_value, buying_power,
                 positions_json, reconciliation_status, discrepancies_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    self.run_id,
                    snapshot_date,
                    snapshot_type,
                    cash,
                    portfolio_value,
                    buying_power,
                    json.dumps(positions),
                    reconciliation_status,
                    json.dumps(discrepancies),
                ),
            )

            conn.commit()

    def get_all_strategies(self) -> list[dict]:
        """Get all strategies"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM strategies WHERE status = "active" ORDER BY id')
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_positions(self, strategy_id: Optional[int] = None) -> list[dict]:
        """Get positions"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if strategy_id:
                cursor.execute("SELECT * FROM positions WHERE strategy_id = ?", (strategy_id,))
            else:
                cursor.execute("SELECT * FROM positions")

            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_position(self, strategy_id: int, symbol: str) -> Optional[dict]:
        """Get a single position for a strategy and symbol."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM positions WHERE strategy_id = ? AND symbol = ?",
                (strategy_id, symbol),
            )
            row = cursor.fetchone()

        return dict(row) if row else None

    def get_all_open_positions(self) -> list[dict]:
        """Return all open positions (non-zero shares) across all strategies.

        Includes shorts (shares < 0) so reconciliation, P&L refresh, and
        downstream consumers see broker-side state truthfully. The earlier
        `shares > 0` filter silently dropped short positions imported under
        BROKER_SYNC and caused reconciliation to perpetually fail.
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM positions WHERE shares != 0")
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_todays_trades(self, date: str) -> list[dict]:
        """Get trades for a specific date"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT t.*, s.name as strategy_name
                FROM trades t
                JOIN strategies s ON t.strategy_id = s.id
                WHERE DATE(t.executed_at) = ?
                ORDER BY t.executed_at
            """,
                (date,),
            )

            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_signals_without_terminal_state(self, run_id: Optional[str] = None) -> list[dict]:
        """Get signals that haven't reached terminal state for a run"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            rid = run_id or self.run_id
            cursor.execute(
                """
                SELECT * FROM signals
                WHERE run_id = ? AND terminal_state IS NULL
            """,
                (rid,),
            )

            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def verify_terminal_states(self, run_id: Optional[str] = None) -> tuple[int, int]:
        """Verify all signals have terminal states. Returns (total, with_terminal)"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            rid = run_id or self.run_id
            cursor.execute("SELECT COUNT(*) FROM signals WHERE run_id = ?", (rid,))
            total = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*) FROM signals
                WHERE run_id = ? AND terminal_state IS NOT NULL
            """,
                (rid,),
            )
            with_terminal = cursor.fetchone()[0]

        return (total, with_terminal)

    def get_strategy_trades(self, strategy_id: int) -> list[dict]:
        """Get all trades for a strategy"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM trades
                WHERE strategy_id = ?
                ORDER BY executed_at DESC
            """,
                (strategy_id,),
            )

            rows = cursor.fetchall()

        trades = [dict(row) for row in rows]
        for trade in trades:
            if trade.get("price") is None:
                trade["price"] = trade.get("exec_price") or trade.get("requested_price") or 0.0

        return trades

    def get_strategy_performance(self, strategy_id: int, days: int = 30) -> list[dict]:
        """Get strategy performance history for dynamic allocation."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    SELECT snapshot_date, portfolio_value, total_return_pct
                    FROM strategy_performance
                    WHERE strategy_id = ?
                      AND snapshot_date >= date('now', ?)
                    ORDER BY snapshot_date ASC
                    """,
                    (strategy_id, f"-{days} days"),
                ).fetchall()
                return [dict(r) for r in rows]
            except Exception:
                return []

    def get_strategy_trade_returns(self, strategy_id: int, days: int = 30) -> list:
        """Return per-trade gross_pnl_pct values from trade_pnl_detail for Sharpe computation."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT gross_pnl_pct
                    FROM trade_pnl_detail
                    WHERE strategy_id = ?
                      AND exit_date >= date('now', ?)
                    ORDER BY exit_date ASC
                    """,
                    (strategy_id, f"-{days} days"),
                ).fetchall()
                return [float(r[0]) for r in rows]
            except Exception:
                return []

    def get_latest_performance(self, strategy_id: int) -> Optional[dict]:
        """Get the most recent performance snapshot for a strategy."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    """
                    SELECT * FROM strategy_performance
                    WHERE strategy_id = ?
                    ORDER BY snapshot_date DESC, created_at DESC
                    LIMIT 1
                    """,
                    (strategy_id,),
                ).fetchone()
                return dict(row) if row else None
            except Exception:
                return None

    def record_daily_performance(self, strategy_id: int, **kwargs):
        """Record a daily performance snapshot for a strategy."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO strategy_performance
                        (run_id, strategy_id, snapshot_date, portfolio_value, cash,
                         positions_value, total_return_pct, num_positions, num_trades)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.run_id,
                        strategy_id,
                        datetime.now().strftime("%Y-%m-%d"),
                        kwargs.get("portfolio_value", 0.0),
                        kwargs.get("cash", 0.0),
                        kwargs.get("positions_value", 0.0),
                        kwargs.get("total_return_pct", 0.0),
                        kwargs.get("num_positions", 0),
                        kwargs.get("num_trades", 0),
                    ),
                )
                conn.commit()
            except Exception as e:
                logger.warning(
                    "record_daily_performance failed for strategy %s: %s", strategy_id, e
                )

    def save_signal_funnel(
        self,
        strategy_id: int,
        strategy_name: str,
        raw: int,
        regime: int,
        correlation: int,
        risk: int,
        executed: int,
    ):
        """Save signal funnel counts for a strategy"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO signal_funnel
                (run_id, strategy_id, strategy_name, raw_signals_count, after_regime_count,
                 after_correlation_count, after_risk_count, executed_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (self.run_id, strategy_id, strategy_name, raw, regime, correlation, risk, executed),
            )
            conn.commit()

    def log_signal_rejection(
        self,
        strategy_id: int,
        symbol: str,
        stage: str,
        reason_code: str,
        details: dict = None,
        signal_id: int = None,
    ):
        """Log why a signal was rejected"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO signal_rejections
                (run_id, signal_id, strategy_id, symbol, stage, reason_code, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    self.run_id,
                    signal_id,
                    strategy_id,
                    symbol,
                    stage,
                    reason_code,
                    json.dumps(details) if details else None,
                ),
            )
            conn.commit()

    def create_order_intent(
        self, strategy_id: int, symbol: str, side: str, target_qty: float
    ) -> str:
        """Create order intent with deterministic ID"""
        import hashlib

        timestamp_bucket = datetime.now().strftime("%Y%m%d_%H")
        intent_string = (
            f"{self.run_id}_{strategy_id}_{symbol}_{side}_{target_qty}_{timestamp_bucket}"
        )
        intent_id = hashlib.sha256(intent_string.encode()).hexdigest()[:16]

        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT intent_id, status FROM order_intents WHERE intent_id = ?", (intent_id,)
            )
            existing = cursor.fetchone()

            if existing:
                return existing[0]

            cursor.execute(
                """
                INSERT INTO order_intents
                (intent_id, run_id, strategy_id, symbol, side, target_qty, status)
                VALUES (?, ?, ?, ?, ?, ?, 'CREATED')
            """,
                (intent_id, self.run_id, strategy_id, symbol, side, target_qty),
            )
            conn.commit()

        return intent_id

    def update_order_intent_status(
        self, intent_id: str, status: str, broker_order_id: str = None, error: str = None
    ):
        """Update order intent status"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            timestamp_field = {
                "SUBMITTED": "submitted_at",
                "ACKED": "acked_at",
                "FILLED": "filled_at",
            }.get(status)

            if timestamp_field:
                cursor.execute(
                    f"""
                    UPDATE order_intents
                    SET status = ?, broker_order_id = ?, {timestamp_field} = ?
                    WHERE intent_id = ?
                """,
                    (status, broker_order_id, datetime.now().isoformat(), intent_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE order_intents
                    SET status = ?, broker_order_id = ?, error_message = ?
                    WHERE intent_id = ?
                """,
                    (status, broker_order_id, error, intent_id),
                )

            conn.commit()

    def get_intents_for_reconciliation(self, days: int = 7) -> list[dict]:
        """Return order intents from last N days that may need broker reconciliation.

        Returns intents with status in (SUBMITTED, ACKED, FILLED) and a non-null
        broker_order_id. These are intents the bot believes are pending or
        completed but whose actual broker status may have drifted (paper-mode
        OPG orders that expire/cancel before market open, status updates that
        never made it back to the local DB, etc.).

        Caller is expected to poll Alpaca for each broker_order_id and either:
        - Reverse the local state if broker status is canceled/expired/rejected
        - Update local status to FILLED if broker confirms fill
        - Leave alone if broker still pending
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT intent_id, run_id, strategy_id, symbol, side, target_qty,
                       status, broker_order_id, created_at
                FROM order_intents
                WHERE status IN ('SUBMITTED', 'ACKED', 'FILLED')
                  AND broker_order_id IS NOT NULL
                  AND created_at >= datetime('now', ?)
                ORDER BY created_at DESC
                """,
                (f"-{days} days",),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_signal_funnel_summary(self, run_id: str = None) -> list[dict]:
        """Get funnel summary for email reporting"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            rid = run_id or self.run_id
            cursor.execute("SELECT * FROM signal_funnel WHERE run_id = ?", (rid,))
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_signal_rejections_summary(self, run_id: str = None, limit: int = 10) -> list[dict]:
        """Get top rejection reasons for email reporting"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            rid = run_id or self.run_id
            cursor.execute(
                """
                SELECT stage, reason_code, COUNT(*) as count,
                       GROUP_CONCAT(symbol, ', ') as symbols
                FROM signal_rejections
                WHERE run_id = ?
                GROUP BY stage, reason_code
                ORDER BY count DESC
                LIMIT ?
            """,
                (rid, limit),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_order_intent_by_id(self, intent_id: str) -> Optional[dict]:
        """Get order intent by ID"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM order_intents WHERE intent_id = ?", (intent_id,))
            row = cursor.fetchone()

        return dict(row) if row else None

    def check_duplicate_order_intent(
        self, strategy_id: int, symbol: str, side: str, target_qty: float
    ) -> Optional[str]:
        """
        Check if an order intent already exists for this exact order.

        Returns intent_id if duplicate found, None otherwise.
        """
        intent_id = self.create_order_intent(strategy_id, symbol, side, target_qty)

        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT intent_id, status FROM order_intents
                WHERE intent_id = ?
            """,
                (intent_id,),
            )

            result = cursor.fetchone()

        if result and result[1] in ["SUBMITTED", "ACKED", "FILLED"]:
            return result[0]

        return None

    def find_active_order_intent_for_today(
        self, strategy_id: int, symbol: str, side: str
    ) -> Optional[dict]:
        """Return the most recent active (SUBMITTED/ACKED/FILLED) intent for this
        (strategy_id, symbol, side) pair created today, regardless of run_id.

        This is the true idempotency gate: a second run on the same calendar day
        will find the first run's intent and skip re-submitting the order.
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM order_intents
                WHERE strategy_id = ?
                  AND symbol = ?
                  AND side = ?
                  AND status IN ('SUBMITTED', 'ACKED', 'FILLED')
                  AND DATE(created_at, 'localtime') = DATE('now', 'localtime')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (strategy_id, symbol, side),
            )
            row = cursor.fetchone()
        return dict(row) if row else None

    def count_duplicate_order_intents(self, hours: int = 24) -> int:
        """
        Count duplicate order intents in the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            Count of duplicate intents
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()

            cursor.execute(
                """
                SELECT intent_id, COUNT(*) as count
                FROM order_intents
                WHERE created_at >= ?
                GROUP BY intent_id
                HAVING count > 1
            """,
                (cutoff_time,),
            )

            duplicates = cursor.fetchall()

        return len(duplicates)

    def get_system_state(self, key: str) -> Optional[str]:
        """
        Get system state value by key.

        Args:
            key: State key

        Returns:
            State value or None if not found
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT value FROM system_state
                WHERE key = ?
            """,
                (key,),
            )

            result = cursor.fetchone()

        return result[0] if result else None

    def set_system_state(self, key: str, value: str):
        """
        Set system state value.

        Args:
            key: State key
            value: State value
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO system_state (key, value, timestamp)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
                (key, value),
            )

            conn.commit()

    def save_stop_loss(
        self, symbol: str, stop_price: float, entry_price: float, entry_atr: float
    ) -> None:
        """Persist a stop-loss level so it survives across daily runs."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO stop_loss_state (symbol, stop_price, entry_price, entry_atr, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (symbol, stop_price, entry_price, entry_atr),
            )
            conn.commit()

    def load_all_stop_losses(self) -> dict:
        """Return persisted stop-loss levels keyed by symbol."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, stop_price, entry_price, entry_atr FROM stop_loss_state")
            rows = cursor.fetchall()
        return {
            row[0]: {"stop_price": row[1], "entry_price": row[2], "entry_atr": row[3]}
            for row in rows
        }

    def delete_stop_loss(self, symbol: str) -> None:
        """Remove a persisted stop-loss level when a position is closed."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stop_loss_state WHERE symbol = ?", (symbol,))
            conn.commit()
