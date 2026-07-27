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


def _with_retry(fn, max_attempts: int = 3, base_delay: float = 0.1):
    """Retry ``fn`` on transient SQLite SQLITE_BUSY (database locked) errors.

    Uses exponential backoff with jitter so parallel GHA steps (e.g. the
    portfolio snapshot workflow overlapping the trading run) don't deadlock.
    """
    import random as _random
    import time as _time

    for attempt in range(max_attempts):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if "database is locked" in str(exc) and attempt < max_attempts - 1:
                delay = base_delay * (2**attempt) + _random.uniform(0, 0.05)
                logger.warning(
                    "SQLite locked (attempt %d/%d) — retrying in %.2fs",
                    attempt + 1,
                    max_attempts,
                    delay,
                )
                _time.sleep(delay)
            else:
                raise


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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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

            # One-row-per-run health summary — the cross-run memory that lets
            # `make diagnose` (and Claude Code) spot RECURRING failures in
            # seconds instead of re-deriving them from logs. Written by
            # scripts/diagnostics/build_run_health.py at the end of each run
            # and persisted via the trading-database artifact.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS run_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL UNIQUE,
                    run_date TEXT NOT NULL,
                    overall TEXT NOT NULL,
                    status TEXT,
                    failed_checks_json TEXT,
                    portfolio_value REAL,
                    n_orders INTEGER,
                    data_freshness_hours REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_run_history_date ON run_history(run_date)"
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
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id),
                    UNIQUE(strategy_id, symbol, sell_run_id, exit_date)
                )
            """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_trade_pnl_strategy ON trade_pnl_detail(strategy_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_trade_pnl_exit ON trade_pnl_detail(exit_date)"
            )
            # Dedup guard: CREATE UNIQUE INDEX works on existing tables (unlike UNIQUE in schema).
            # INSERT OR IGNORE respects this index even on DBs created before the column constraint
            # was added, so the protection applies to downloaded artifacts too.
            # Pre-existing duplicate rows (written before the index existed) would make the
            # CREATE UNIQUE INDEX itself fail and abort the trading run — collapse them to the
            # earliest row first.
            cursor.execute(
                "DELETE FROM trade_pnl_detail WHERE id NOT IN ("
                "  SELECT MIN(id) FROM trade_pnl_detail"
                "  GROUP BY strategy_id, symbol, sell_run_id, exit_date)"
            )
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_trade_pnl_no_dup "
                "ON trade_pnl_detail(strategy_id, symbol, sell_run_id, exit_date)"
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

            # Point-in-time news sentiment — one row per (asof_date, symbol).
            # News Sentiment scores LIVE RSS, so it is unbacktestable from
            # history; this table accumulates leak-free observations going
            # forward so the strategy can eventually be validated with a t+1
            # execution lag (EXP-2026-06-22-news-pit-recording).
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sentiment_history (
                    asof_date TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    score REAL NOT NULL,
                    headline_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (asof_date, symbol)
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sentiment_history_date "
                "ON sentiment_history(asof_date)"
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

            # Tax lot tracking: each BUY is a separate lot; SELLs are FIFO-matched
            # so realized P&L can be split into LTCG (>365d) and STCG (<365d).
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tax_lots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    buy_run_id TEXT NOT NULL,
                    buy_date TEXT NOT NULL,
                    buy_price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    remaining_quantity REAL NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tax_lots_symbol ON tax_lots(strategy_id, symbol)"
            )

            # Add tax_treatment column to trade_pnl_detail if it doesn't exist yet
            try:
                cursor.execute(
                    "ALTER TABLE trade_pnl_detail ADD COLUMN tax_treatment TEXT DEFAULT 'STCG'"
                )
            except Exception:
                pass  # column already exists — migration is idempotent

            # Direction columns for short-selling support (pairs trading):
            # stop_loss_state needs it so a short's stop (above entry) survives
            # restarts; trade_pnl_detail needs it so short P&L keeps the right sign.
            for col_sql in [
                "ALTER TABLE stop_loss_state ADD COLUMN direction TEXT DEFAULT 'long'",
                "ALTER TABLE trade_pnl_detail ADD COLUMN direction TEXT DEFAULT 'long'",
            ]:
                try:
                    cursor.execute(col_sql)
                except Exception:
                    pass  # column already exists — migration is idempotent

            # Sentiment per signal — persisted so the dashboard explorer can show
            # accurate historical sentiment scores without re-fetching at export time.
            for col_sql in [
                "ALTER TABLE signals ADD COLUMN sentiment_score REAL",
                "ALTER TABLE signals ADD COLUMN sentiment_multiplier TEXT",
            ]:
                try:
                    cursor.execute(col_sql)
                except Exception:
                    pass  # column already exists — migration is idempotent

            # Immutable trade audit log — append-only ledger for compliance.
            # Triggers prevent DELETE so every executed trade is permanently recorded.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_audit_log (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type   TEXT NOT NULL,
                    run_id       TEXT,
                    strategy_id  INTEGER,
                    symbol       TEXT,
                    action       TEXT,
                    shares       REAL,
                    exec_price   REAL,
                    order_id     TEXT,
                    logged_at    TEXT DEFAULT CURRENT_TIMESTAMP,
                    payload_json TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_trade_audit_insert
                AFTER INSERT ON trades
                BEGIN
                    INSERT INTO trade_audit_log
                        (event_type, run_id, strategy_id, symbol, action,
                         shares, exec_price, order_id, payload_json)
                    VALUES (
                        'INSERT', NEW.run_id, NEW.strategy_id, NEW.symbol,
                        NEW.action, NEW.shares, NEW.exec_price, NEW.order_id,
                        json_object(
                            'run_id', NEW.run_id, 'strategy_id', NEW.strategy_id,
                            'symbol', NEW.symbol, 'action', NEW.action,
                            'shares', NEW.shares, 'exec_price', NEW.exec_price,
                            'order_id', NEW.order_id, 'executed_at', NEW.executed_at
                        )
                    );
                END
                """
            )
            cursor.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_trade_audit_delete
                BEFORE DELETE ON trades
                BEGIN
                    INSERT INTO trade_audit_log
                        (event_type, symbol, action, shares, exec_price, order_id)
                    VALUES (
                        'DELETE_BLOCKED', OLD.symbol, OLD.action,
                        OLD.shares, OLD.exec_price, OLD.order_id
                    );
                    SELECT RAISE(ABORT, 'trades table is immutable — DELETE not allowed');
                END
                """
            )

            # In-house error tracking: persistent log of unhandled exceptions.
            # Replaces Sentry for crash visibility; queryable alongside trade data.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS error_log (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id       TEXT,
                    error_type   TEXT NOT NULL,
                    message      TEXT NOT NULL,
                    stack_trace  TEXT,
                    context_json TEXT,
                    alert_sent   INTEGER DEFAULT 0,
                    occurred_at  TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_log_run ON error_log(run_id)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_error_log_type ON error_log(error_type, occurred_at)"
            )

            # One-time data repair: remove zero-basis trade_pnl_detail rows written
            # when disabled-strategy wind-downs logged exits before avg_price was
            # populated (News Sentiment VZ phantom +$3,486 as of 2026-06-22).
            # entry_price=0 is always a bug (real fills are never free).
            cursor.execute("DELETE FROM trade_pnl_detail WHERE entry_price <= 0")

            # One-time data repair (flag-guarded): re-attribute BROKER_SYNC
            # orphans created after PR #60 back to their originating strategy.
            self._reattribute_broker_sync_orphans(cursor)

            # One-time data repair (flag-guarded): backfill trades.pnl for
            # stop-loss exits that recorded NULL (PR #65). Makes the historical
            # losses visible to the live-readiness gate + performance_tracker.
            self._backfill_stop_loss_trade_pnl(cursor)

            conn.commit()

    # How many days BEFORE a BROKER_SYNC adoption an order intent may have been
    # created and still explain the position. Adoption happens on the morning
    # after the intraday fill, so the real gap is 1 trading day; 5 calendar
    # days covers long weekends and a missed run.
    _ORPHAN_REATTRIBUTION_WINDOW_DAYS = 5
    _ORPHAN_REATTRIBUTION_FLAG = "broker_sync_orphans_reattributed_2026_07"

    def _reattribute_broker_sync_orphans(self, cursor):
        """One-off repair: move BROKER_SYNC orphan positions back to the
        strategy whose order intent bought them.

        After PR #60 switched entries to DAY marketable limits, orders fill
        intraday AFTER the pre-market run ends. When the optimistic local
        position was lost before the next sync (same-day duplicate run's
        "not in broker" sweep), the next morning's broker sync adopted the
        fill under BROKER_SYNC — strategy exit logic never manages it and it
        permanently consumes a max_positions slot (11/16 slots were orphans
        by 2026-07-21, causing 129 max_positions_reached rejections).

        For each BROKER_SYNC long, find the most recent active BUY intent for
        that symbol created in the window before the position's entry_date
        (exact-qty matches preferred) and move the row to that strategy,
        merging into an existing row if the strategy already holds the symbol.
        Keeps the broker fill price as cost basis; restores the intent's fill
        date as entry_date so time-based exits see the true holding period.

        Runs once: guarded by a system_state flag so re-inits are no-ops.
        Idempotent by construction either way (a moved row is no longer under
        BROKER_SYNC).
        """
        cursor.execute(
            "SELECT value FROM system_state WHERE key = ?",
            (self._ORPHAN_REATTRIBUTION_FLAG,),
        )
        if cursor.fetchone():
            return

        cursor.execute("SELECT id FROM strategies WHERE name = 'BROKER_SYNC' LIMIT 1")
        sync_row = cursor.fetchone()
        moves: list[dict] = []
        if sync_row:
            sync_id = sync_row[0]
            cursor.execute(
                "SELECT symbol, shares, avg_price, entry_date FROM positions "
                "WHERE strategy_id = ? AND shares > 0",
                (sync_id,),
            )
            orphans = cursor.fetchall()
            for symbol, shares, avg_price, entry_date in orphans:
                cursor.execute(
                    """
                    SELECT oi.strategy_id, s.name,
                           DATE(COALESCE(oi.filled_at, oi.submitted_at, oi.created_at))
                    FROM order_intents oi
                    JOIN strategies s ON s.id = oi.strategy_id
                    WHERE oi.symbol = ?
                      AND oi.side = 'BUY'
                      AND oi.status IN ('SUBMITTED', 'ACKED', 'FILLED')
                      AND oi.strategy_id != ?
                      AND DATE(oi.created_at) <= DATE(COALESCE(?, 'now'))
                      AND DATE(oi.created_at) >= DATE(COALESCE(?, 'now'), ?)
                    ORDER BY (ABS(oi.target_qty - ?) < 0.001) DESC, oi.created_at DESC
                    LIMIT 1
                    """,
                    (
                        symbol,
                        sync_id,
                        entry_date,
                        entry_date,
                        f"-{self._ORPHAN_REATTRIBUTION_WINDOW_DAYS} days",
                        shares,
                    ),
                )
                match = cursor.fetchone()
                if not match:
                    continue
                target_sid, target_name, fill_date = match

                cursor.execute(
                    "SELECT shares, avg_price, entry_date FROM positions "
                    "WHERE strategy_id = ? AND symbol = ?",
                    (target_sid, symbol),
                )
                existing = cursor.fetchone()
                if existing:
                    # Strategy already holds some — merge shares with a
                    # weighted cost basis, keep the earlier entry_date.
                    ex_shares, ex_avg, ex_entry = existing
                    new_shares = ex_shares + shares
                    new_avg = (
                        (ex_avg * ex_shares + avg_price * shares) / new_shares
                        if new_shares
                        else avg_price
                    )
                    new_entry = (
                        min(d for d in (ex_entry, fill_date) if d)
                        if (ex_entry or fill_date)
                        else None
                    )
                    cursor.execute(
                        "UPDATE positions SET shares = ?, avg_price = ?, entry_date = ?, "
                        "last_updated = ? WHERE strategy_id = ? AND symbol = ?",
                        (
                            new_shares,
                            new_avg,
                            new_entry,
                            datetime.now().isoformat(),
                            target_sid,
                            symbol,
                        ),
                    )
                    cursor.execute(
                        "DELETE FROM positions WHERE strategy_id = ? AND symbol = ?",
                        (sync_id, symbol),
                    )
                else:
                    cursor.execute(
                        "UPDATE positions SET strategy_id = ?, entry_date = ?, "
                        "last_updated = ? WHERE strategy_id = ? AND symbol = ?",
                        (target_sid, fill_date, datetime.now().isoformat(), sync_id, symbol),
                    )
                moves.append(
                    {
                        "symbol": symbol,
                        "shares": shares,
                        "to_strategy": target_name,
                        "entry_date": fill_date,
                        "merged": bool(existing),
                    }
                )
                logger.info(
                    "Re-attributed BROKER_SYNC orphan %s (%.2f sh) → %s (entry %s%s)",
                    symbol,
                    shares,
                    target_name,
                    fill_date,
                    ", merged" if existing else "",
                )

        cursor.execute(
            "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
            (
                self._ORPHAN_REATTRIBUTION_FLAG,
                json.dumps({"date": datetime.now().strftime("%Y-%m-%d"), "moves": moves}),
            ),
        )
        if moves:
            logger.info("BROKER_SYNC orphan re-attribution: %d position(s) moved", len(moves))

    _STOP_LOSS_PNL_BACKFILL_FLAG = "stop_loss_trade_pnl_backfilled_2026_07"

    def _backfill_stop_loss_trade_pnl(self, cursor):
        """One-off repair: populate trades.pnl for exits that recorded NULL.

        Before PR #65 the stop-loss exit path wrote realized P&L into
        trade_pnl_detail but called log_trade without pnl, leaving trades.pnl
        NULL. performance_tracker and check_live_readiness.py read trades.pnl,
        so every stop-loss LOSS was invisible to win-rate / profit-factor — the
        readiness gate over-counted the record in the direction that green-lights
        going live. PR #65 fixes new exits; this backfills the historical ones.

        Each closed round-trip has exactly one trade_pnl_detail row keyed by
        (sell_run_id, strategy_id, symbol); join the NULL-pnl exit trade to it
        and copy gross_pnl. Exits with no matching detail row (sync-churn SELLs,
        disabled-strategy wind-downs with no basis) are left NULL — they
        represent no realized round-trip. Entries (BUY / SHORT_SELL) are
        excluded so a legitimately-NULL entry is never touched.

        Runs once: guarded by a system_state flag so re-inits are no-ops.
        Idempotent by construction either way (only NULL rows are updated, and a
        backfilled row is no longer NULL).
        """
        cursor.execute(
            "SELECT value FROM system_state WHERE key = ?",
            (self._STOP_LOSS_PNL_BACKFILL_FLAG,),
        )
        if cursor.fetchone():
            return

        # Only exit trades whose (run, strategy, symbol) maps to exactly one
        # trade_pnl_detail row — a >1 match would be ambiguous, so skip it.
        cursor.execute(
            """
            SELECT t.id, t.symbol, d.gross_pnl
            FROM trades t
            JOIN trade_pnl_detail d
              ON d.sell_run_id = t.run_id
             AND d.strategy_id = t.strategy_id
             AND d.symbol = t.symbol
            WHERE t.pnl IS NULL
              AND t.action NOT IN ('BUY', 'SHORT_SELL')
            GROUP BY t.id
            HAVING COUNT(*) = 1
            """
        )
        rows = cursor.fetchall()
        backfilled = []
        for trade_id, symbol, gross_pnl in rows:
            cursor.execute(
                "UPDATE trades SET pnl = ? WHERE id = ? AND pnl IS NULL",
                (gross_pnl, trade_id),
            )
            backfilled.append({"symbol": symbol, "pnl": round(gross_pnl, 2)})
            logger.info(
                "Backfilled stop-loss trades.pnl for %s (id=%d): %.2f",
                symbol,
                trade_id,
                gross_pnl,
            )

        cursor.execute(
            "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
            (
                self._STOP_LOSS_PNL_BACKFILL_FLAG,
                json.dumps({"date": datetime.now().strftime("%Y-%m-%d"), "backfilled": backfilled}),
            ),
        )
        if backfilled:
            logger.info("Stop-loss trades.pnl backfill: %d row(s) updated", len(backfilled))

    def record_error(
        self,
        error_type: str,
        message: str,
        stack_trace: str = "",
        context: dict | None = None,
        alert_sent: bool = False,
    ) -> int:
        """Persist an unhandled exception to the error_log table.

        Returns the new row id so the caller can update alert_sent later.
        """
        import json as _json

        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO error_log
                    (run_id, error_type, message, stack_trace, context_json, alert_sent)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    self.run_id,
                    error_type,
                    message[:2000],  # cap to avoid huge DB rows
                    stack_trace[:8000],
                    _json.dumps(context or {}),
                    1 if alert_sent else 0,
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_recent_errors(self, hours: int = 24) -> list[dict]:
        """Return errors from the last N hours (for daily digest / status report)."""
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT error_type, message, occurred_at, alert_sent
                FROM error_log
                WHERE occurred_at >= datetime('now', ?)
                ORDER BY occurred_at DESC
                LIMIT 50
                """,
                (f"-{hours} hours",),
            )
            return [dict(r) for r in cursor.fetchall()]

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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
            if status in ("FAILED", "HALTED"):
                failures += 1
            else:
                break
        return failures

    # ------------------------------------------------------------------
    # Tax lot management
    # ------------------------------------------------------------------

    def record_tax_lot(
        self,
        strategy_id: int,
        symbol: str,
        buy_date: str,
        buy_price: float,
        quantity: float,
    ) -> None:
        """Record a new BUY as a tax lot for future FIFO matching."""
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO tax_lots
                (strategy_id, symbol, buy_run_id, buy_date, buy_price, quantity, remaining_quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (strategy_id, symbol, self.run_id, buy_date, buy_price, quantity, quantity),
            )
            conn.commit()

    def fifo_match_sell(
        self, strategy_id: int, symbol: str, sell_quantity: float, sell_price: float
    ) -> str:
        """FIFO-match a SELL against open lots.  Returns 'LTCG', 'STCG', or 'MIXED'.

        Deducts sold quantity from the oldest lots first and determines
        whether the matched holding period qualifies for long-term treatment
        (>365 days).  Returns the dominant tax treatment.
        """
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, buy_date, buy_price, remaining_quantity
                FROM tax_lots
                WHERE strategy_id = ? AND symbol = ? AND remaining_quantity > 0
                ORDER BY buy_date ASC
                """,
                (strategy_id, symbol),
            )
            lots = cursor.fetchall()

        if not lots:
            return "STCG"

        today = datetime.now().date()
        remaining = sell_quantity
        ltcg_qty = 0.0
        stcg_qty = 0.0

        updates: list[tuple] = []
        for lot in lots:
            if remaining <= 0:
                break
            lot_id = lot["id"]
            lot_date = lot["buy_date"][:10]
            lot_remaining = float(lot["remaining_quantity"])

            try:
                held_days = (today - datetime.strptime(lot_date, "%Y-%m-%d").date()).days
            except ValueError:
                held_days = 0

            used = min(remaining, lot_remaining)
            new_remaining = lot_remaining - used

            if held_days >= 365:
                ltcg_qty += used
            else:
                stcg_qty += used

            remaining -= used
            updates.append((new_remaining, lot_id))

        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            cursor = conn.cursor()
            for new_rem, lot_id in updates:
                cursor.execute(
                    "UPDATE tax_lots SET remaining_quantity = ? WHERE id = ?",
                    (new_rem, lot_id),
                )
            conn.commit()

        if ltcg_qty > 0 and stcg_qty > 0:
            return "MIXED"
        return "LTCG" if ltcg_qty > 0 else "STCG"

    def was_sold_at_loss_recently(self, symbol: str, strategy_id: int, days: int = 30) -> bool:
        """Return True if this symbol was sold at a loss within the last ``days`` calendar days.

        Used for the wash-sale guard: buying a security within 30 days of selling
        it at a loss disallows the loss deduction under IRS wash-sale rules.
        """
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM trade_pnl_detail
                WHERE symbol = ?
                  AND strategy_id = ?
                  AND gross_pnl < 0
                  AND DATE(exit_date) >= DATE('now', ?)
                """,
                (symbol, strategy_id, f"-{days} days"),
            )
            row = cursor.fetchone()
        return bool(row and row[0] > 0)

    def count_day_trades_last_n_days(self, trading_days: int = 5) -> int:
        """Count PDT day trades (same-symbol buy+sell on the same calendar date) in the
        last ``trading_days`` trading days (approximated as trading_days * 1.4 calendar days
        to handle weekends).  Used by the PDT hard-block to enforce the 3-in-5-day rule."""
        calendar_days = int(trading_days * 1.5) + 1  # safe buffer for weekends/holidays
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(DISTINCT symbol || '_' || trade_date) AS day_trades
                FROM (
                    SELECT symbol, DATE(executed_at) AS trade_date
                    FROM trades
                    WHERE DATE(executed_at) >= DATE('now', ?)
                    GROUP BY symbol, DATE(executed_at)
                    HAVING SUM(CASE WHEN action = 'BUY'  THEN 1 ELSE 0 END) > 0
                       AND SUM(CASE WHEN action = 'SELL' THEN 1 ELSE 0 END) > 0
                )
                """,
                (f"-{calendar_days} days",),
            )
            row = cursor.fetchone()
        return int(row[0]) if row else 0

    def save_run_slo_metrics(self, metrics: dict) -> None:
        """Persist per-run SLO metrics for observability dashboards and audits."""
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
            cursor.execute("SELECT COUNT(*) FROM positions WHERE shares != 0")
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
        tax_treatment: str = None,
        direction: str = "long",
    ):
        """Record matched entry→exit P&L for win-rate and profit-factor tracking.

        ``direction="short"`` flips the P&L: a short profits when the exit
        (cover) price is BELOW the entry (short-sale) price.
        """
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            cursor = conn.cursor()

            if direction == "short":
                gross_pnl = (entry_price - exit_price) * shares
                gross_pnl_pct = (entry_price - exit_price) / entry_price if entry_price else 0.0
            else:
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

            # Look up the entry run id from the trades table (the SHORT_SELL row
            # is the entry for a short; BUY is the entry for a long).
            entry_action = "SHORT_SELL" if direction == "short" else "BUY"
            cursor.execute(
                "SELECT run_id FROM trades WHERE strategy_id=? AND symbol=? AND action=? ORDER BY executed_at DESC LIMIT 1",
                (strategy_id, symbol, entry_action),
            )
            buy_row = cursor.fetchone()
            buy_run_id = buy_row[0] if buy_row else None

            # FIFO-match against tax lots to determine LTCG/STCG treatment.
            # Falls back to hold_days-based heuristic when lot data is absent.
            # Short sales are always short-term gains regardless of hold time
            # (IRS rule), and tax lots only track BUYs — skip FIFO entirely.
            if tax_treatment is None:
                if direction == "short":
                    tax_treatment = "STCG"
                else:
                    fifo_result = self.fifo_match_sell(strategy_id, symbol, shares, exit_price)
                    if fifo_result != "MIXED":
                        tax_treatment = fifo_result
                    elif hold_days is not None:
                        tax_treatment = "LTCG" if hold_days >= 365 else "STCG"
                    else:
                        tax_treatment = "STCG"

            cursor.execute(
                """
                INSERT OR IGNORE INTO trade_pnl_detail
                (strategy_id, strategy_name, symbol, buy_run_id, sell_run_id,
                 entry_date, exit_date, entry_price, exit_price, shares,
                 gross_pnl, gross_pnl_pct, hold_days, exit_reason, is_winner,
                 tax_treatment, direction)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    tax_treatment,
                    direction,
                ),
            )
            conn.commit()

    def get_paper_trading_stats(self, days: int = 30) -> dict:
        """Return win rate, profit factor, avg hold days, and streak stats for the last N days."""
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            conn.execute(
                "UPDATE strategies SET capital_allocation = ? WHERE id = ?",
                (capital, strategy_id),
            )
            conn.commit()

    def zero_inactive_strategy_capital(self, active_names: set[str]) -> list[str]:
        """Zero capital_allocation for every strategy NOT in ``active_names``.

        Disabled strategies (ML/News/Pairs) retain whatever allocation they last
        held while active, so the column drifts far above account equity ($92.5k
        of $95k in June 2026) and pollutes the email/dashboard AND the cash
        manager, which trusts sum(allocations) as deployed capital. An inactive
        strategy deploys no capital, so its allocation is 0 by definition.

        This deliberately scans ALL strategies regardless of status — the bug it
        fixes was that get_all_strategies() returns only status='active' rows, so
        the disabled strategies were never visited and never cleared. Returns the
        names that were zeroed.
        """
        zeroed: list[str] = []
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, capital_allocation FROM strategies")
            for sid, name, cap in cursor.fetchall():
                if name not in active_names and (cap or 0) != 0:
                    cursor.execute(
                        "UPDATE strategies SET capital_allocation = 0 WHERE id = ?", (sid,)
                    )
                    zeroed.append(name)
            conn.commit()
        return zeroed

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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM strategies WHERE status = "active" ORDER BY id')
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_positions(self, strategy_id: Optional[int] = None) -> list[dict]:
        """Get positions"""
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM positions WHERE shares != 0")
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_todays_trades(self, date: str) -> list[dict]:
        """Get trades for a specific date"""
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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

        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            rid = run_id or self.run_id
            cursor.execute("SELECT * FROM signal_funnel WHERE run_id = ?", (rid,))
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_signal_rejections_summary(self, run_id: str = None, limit: int = 10) -> list[dict]:
        """Get top rejection reasons for email reporting"""
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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

        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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

    def _conn_execute(self, sql: str, params: tuple = ()) -> None:
        """Fire-and-forget UPDATE/INSERT — best-effort, never raises."""
        try:
            with closing(sqlite3.connect(self.db_path, timeout=5)) as conn:
                conn.execute(sql, params)
                conn.commit()
        except Exception:
            pass

    def set_system_state(self, key: str, value: str):
        """
        Set system state value.

        Args:
            key: State key
            value: State value
        """
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
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
        self,
        symbol: str,
        stop_price: float,
        entry_price: float,
        entry_atr: float,
        direction: str = "long",
    ) -> None:
        """Persist a stop-loss level so it survives across daily runs."""
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO stop_loss_state
                    (symbol, stop_price, entry_price, entry_atr, direction, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (symbol, stop_price, entry_price, entry_atr, direction),
            )
            conn.commit()

    def load_all_stop_losses(self) -> dict:
        """Return persisted stop-loss levels keyed by symbol."""
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT symbol, stop_price, entry_price, entry_atr, direction FROM stop_loss_state"
            )
            rows = cursor.fetchall()
        return {
            row[0]: {
                "stop_price": row[1],
                "entry_price": row[2],
                "entry_atr": row[3],
                "direction": row[4] or "long",
            }
            for row in rows
        }

    def delete_stop_loss(self, symbol: str) -> None:
        """Remove a persisted stop-loss level when a position is closed."""
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stop_loss_state WHERE symbol = ?", (symbol,))
            conn.commit()
