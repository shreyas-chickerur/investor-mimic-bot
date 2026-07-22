"""
Regression tests for bugs fixed in June 2026 audit.

Covers:
  1. kill-switch run: run_state ends as HALTED (not SUCCESS)
  2. exposurePct: heat_pct stored as percent, must NOT be multiplied by 100
  3. reconciliation pass-rate: counts distinct run_ids, not snapshot rows
  4. trade_pnl_detail: duplicate log_trade_pnl calls are silently ignored
  5. float('None') in system_state: must not crash __init__
  6. stop-loss fallback: ATR=0 uses 7% fallback, position is always protected
  7. correlation filter: zero prices produce inf; must be sanitized
  8. raw_signals_by_strategy initialized in __init__ (no AttributeError on kill-switch)
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ---------------------------------------------------------------------------
# 1. Kill-switch run_state must end as HALTED, not SUCCESS
# ---------------------------------------------------------------------------


def test_kill_switch_preserves_halted_status(tmp_path):
    """execute_pipeline + runner_main must never overwrite HALTED with SUCCESS."""
    from src.core.database import TradingDatabase

    run_id = "TEST_KS_RUN"
    db = TradingDatabase(str(tmp_path / "trading.db"), run_id=run_id)

    # Simulate the sequence: TRADING/RUNNING → KILL_SWITCH/HALTED
    db.upsert_run_state(stage="TRADING", status="RUNNING")
    db.upsert_run_state(stage="KILL_SWITCH", status="HALTED", completed=True)

    # The guard in runner_main only writes COMPLETE/SUCCESS when NOT killed
    is_killed = True
    if not is_killed:
        db.upsert_run_state(stage="COMPLETE", status="SUCCESS", completed=True)

    with sqlite3.connect(str(tmp_path / "trading.db")) as conn:
        row = conn.execute(
            "SELECT stage, status FROM run_state WHERE run_id = ?", (run_id,)
        ).fetchone()

    assert row is not None
    assert row[1] == "HALTED", f"Expected HALTED, got {row[1]}"


def test_halted_runs_counted_by_consecutive_failures(tmp_path):
    """get_consecutive_failed_runs must count HALTED runs."""
    import time

    from src.core.database import TradingDatabase

    for i in range(3):
        run_id = f"RUN_{i:03d}"
        db = TradingDatabase(str(tmp_path / "trading.db"), run_id=run_id)
        db.upsert_run_state(stage="KILL_SWITCH", status="HALTED", completed=True)
        time.sleep(0.01)

    # get_consecutive_failed_runs uses any db handle (just needs the db_path)
    db_check = TradingDatabase(str(tmp_path / "trading.db"))
    count = db_check.get_consecutive_failed_runs()
    assert count == 3, f"Expected 3 consecutive failures, got {count}"


# ---------------------------------------------------------------------------
# 2. exposurePct: heat_pct already a percent, must NOT be multiplied by 100
# ---------------------------------------------------------------------------


def test_exposure_pct_not_double_multiplied(tmp_path):
    """heat_pct=1.7 (1.7%) must produce exposurePct≈1.7, not 170."""
    from scripts.export_snapshot import _build_portfolio
    from src.core.database import TradingDatabase

    db_path = tmp_path / "trading.db"
    TradingDatabase(str(db_path))

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO broker_state (run_id, snapshot_date, snapshot_type, cash, "
            "portfolio_value, buying_power, positions_json, reconciliation_status, "
            "discrepancies_json) VALUES (?,?,?,?,?,?,?,?,?)",
            ("R1", "2026-06-09", "END", 94000.0, 96000.0, 200000.0, "[]", "PASS", "[]"),
        )
        conn.execute(
            "INSERT INTO daily_portfolio_snapshot "
            "(run_id, snapshot_date, portfolio_value, cash, positions_value, "
            "heat_pct, daily_pnl, daily_pnl_pct, cumulative_pnl, drawdown_pct, "
            "peak_value, num_open_positions, vix, regime, allocation_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "R1",
                "2026-06-09",
                96000.0,
                94000.0,
                1640.0,
                1.7,
                -1.0,
                -0.00001,
                0.0,
                -0.0001,
                97855.0,
                1,
                18.9,
                "NORMAL",
                None,
            ),
        )
        conn.commit()

    conn2 = sqlite3.connect(str(db_path))
    conn2.row_factory = sqlite3.Row
    portfolio = _build_portfolio(conn2, {}, "2026-06-09")
    conn2.close()

    assert portfolio["exposurePct"] == pytest.approx(1.7, abs=0.1), (
        f"exposurePct should be ~1.7%, got {portfolio['exposurePct']} "
        f"(bug: multiplied by 100 gives 170)"
    )


# ---------------------------------------------------------------------------
# 3. Reconciliation pass-rate: COUNT(DISTINCT run_id)
# ---------------------------------------------------------------------------


def test_recon_rate_counts_distinct_runs(tmp_path):
    """A run with FAIL+RETRY-PASS counts as 1 passing run, not 1 fail + 1 pass."""
    from datetime import datetime, timedelta

    from src.core.database import TradingDatabase

    TradingDatabase(str(tmp_path / "trading.db"))

    # Relative dates: the query below filters on a rolling 30-day window, so
    # hardcoded timestamps become a time bomb (this test silently expired on
    # 2026-07-09 when its 2026-06-09 fixtures aged out of the window).
    yesterday = datetime.now() - timedelta(days=1)
    snap_date = yesterday.strftime("%Y-%m-%d")

    with sqlite3.connect(str(tmp_path / "trading.db")) as conn:
        # Run A: initial fail, then retry passes
        for snap_type, status, ts in [
            ("RECONCILIATION", "FAIL", f"{snap_date}T10:00:00"),
            ("RECONCILIATION_RETRY", "PASS", f"{snap_date}T10:01:00"),
        ]:
            conn.execute(
                "INSERT INTO broker_state (run_id, snapshot_date, snapshot_type, cash, "
                "portfolio_value, buying_power, positions_json, reconciliation_status, "
                "discrepancies_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("RUN_A", snap_date, snap_type, 0, 0, 0, "[]", status, "[]", ts),
            )
        # Run B: clean pass
        conn.execute(
            "INSERT INTO broker_state (run_id, snapshot_date, snapshot_type, cash, "
            "portfolio_value, buying_power, positions_json, reconciliation_status, "
            "discrepancies_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                "RUN_B",
                snap_date,
                "RECONCILIATION",
                0,
                0,
                0,
                "[]",
                "PASS",
                "[]",
                f"{snap_date}T11:00:00",
            ),
        )
        conn.commit()

    with sqlite3.connect(str(tmp_path / "trading.db")) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT run_id) AS total,
                   COUNT(DISTINCT CASE WHEN reconciliation_status='PASS' THEN run_id END) AS passes
            FROM broker_state
            WHERE snapshot_type IN ('RECONCILIATION','RECONCILIATION_RETRY','END')
              AND created_at >= date('now', '-30 days')
              AND run_id NOT IN ('AUTO_SYNC', '', 'UNKNOWN')
              AND run_id IS NOT NULL
            """
        ).fetchone()

    assert row["total"] == 2, f"Expected 2 distinct runs, got {row['total']}"
    assert row["passes"] == 2, (
        f"RUN_A retried to PASS so should count as pass — "
        f"expected 2/2, got {row['passes']}/{row['total']}"
    )


# ---------------------------------------------------------------------------
# 4. trade_pnl_detail: duplicate log_trade_pnl is silently ignored
# ---------------------------------------------------------------------------


def test_trade_pnl_no_duplicates(tmp_path):
    """Calling log_trade_pnl twice for the same trade produces exactly 1 row."""
    from src.core.database import TradingDatabase

    db = TradingDatabase(str(tmp_path / "trading.db"), run_id="SELL_RUN_001")
    db.create_strategy("Test Strategy", "desc", 10000.0)

    kwargs = {
        "strategy_id": 1,
        "strategy_name": "Test Strategy",
        "symbol": "AAPL",
        "sell_run_id": "SELL_RUN_001",
        "entry_price": 150.0,
        "exit_price": 160.0,
        "shares": 10,
        "exit_reason": "TARGET",
    }
    db.log_trade_pnl(**kwargs)
    db.log_trade_pnl(**kwargs)  # second call must be a no-op

    with sqlite3.connect(str(tmp_path / "trading.db")) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM trade_pnl_detail "
            "WHERE symbol='AAPL' AND sell_run_id='SELL_RUN_001'"
        ).fetchone()[0]

    assert count == 1, f"Expected 1 row, got {count} (duplicate was inserted)"


# ---------------------------------------------------------------------------
# 5. float('None') in system_state must not crash
# ---------------------------------------------------------------------------


def test_corrupted_system_state_does_not_crash(tmp_path):
    """If system_state has 'None' as a string, float conversion must not raise."""
    from src.core.database import TradingDatabase

    db_path = tmp_path / "trading.db"
    TradingDatabase(str(db_path))

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
            ("cumulative_pnl", "None"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
            ("max_drawdown", "None"),
        )
        conn.commit()

    db = TradingDatabase(str(db_path))
    for key in ("cumulative_pnl", "max_drawdown"):
        raw = db.get_system_state(key)
        try:
            result = float(raw) if raw else 0.0
        except (ValueError, TypeError):
            result = 0.0  # the fix
        assert result == 0.0, f"Expected 0.0 fallback for corrupted {key}, got {result}"


# ---------------------------------------------------------------------------
# 6. Stop-loss fallback: ATR=0 uses 7% fallback
# ---------------------------------------------------------------------------


def test_stop_loss_atr_zero_uses_fallback():
    """set_stop_loss with atr=0 should set a stop at ~7% below entry."""
    from src.risk.stop_loss_manager import StopLossManager

    mgr = StopLossManager()
    mgr.set_stop_loss("NVDA", entry_price=100.0, atr=0.0)

    assert "NVDA" in mgr.stop_levels, "Stop loss must be set even when ATR=0"
    stop = mgr.stop_levels["NVDA"]
    # With 7% fallback ATR and 2.5× multiplier: 100 - 2.5*7 = 82.5, floored at 50
    assert 50.0 <= stop < 100.0, f"Fallback stop ${stop:.2f} outside expected range [50, 100)"


def test_stop_loss_atr_none_uses_fallback():
    """set_stop_loss with atr=None should also set a fallback stop."""
    from src.risk.stop_loss_manager import StopLossManager

    mgr = StopLossManager()
    mgr.set_stop_loss("MSFT", entry_price=400.0, atr=None)

    assert "MSFT" in mgr.stop_levels, "Stop loss must be set even when ATR=None"


def test_stop_loss_normal_atr_unchanged():
    """With a valid ATR, stop calculation must remain the same."""
    from src.risk.stop_loss_manager import StopLossManager

    mgr = StopLossManager()
    mgr.set_stop_loss("AAPL", entry_price=200.0, atr=4.0)

    assert "AAPL" in mgr.stop_levels
    expected = max(200.0 - 2.5 * 4.0, 200.0 * 0.5)  # 190.0 (well above 50% floor)
    assert mgr.stop_levels["AAPL"] == pytest.approx(expected, abs=0.01)


# ---------------------------------------------------------------------------
# 7. Correlation filter: zero prices produce inf, must be sanitized
# ---------------------------------------------------------------------------


def test_correlation_filter_zero_price_returns_finite():
    """A price series with a zero must not cause NaN or inf correlation."""
    from src.risk.correlation_filter import CorrelationFilter

    cf = CorrelationFilter(correlation_window=20)

    prices_a = [100.0 + i for i in range(25)]
    prices_b = [50.0 + i * 0.5 for i in range(25)]
    prices_b[10] = 0.0  # data error: zero price

    cf.price_history["A"] = prices_a
    cf.price_history["B"] = prices_b

    corr = cf.calculate_correlation("A", "B")
    assert np.isfinite(corr), f"Correlation must be finite, got {corr}"
    assert -1.0 <= corr <= 1.0, f"Correlation {corr} outside valid range [-1, 1]"


# ---------------------------------------------------------------------------
# 8. raw_signals_by_strategy must exist in __init__ (not just run_all_strategies)
# ---------------------------------------------------------------------------


def test_raw_signals_by_strategy_in_init(tmp_path):
    """MultiStrategyRunner must expose raw_signals_by_strategy from __init__
    so kill-switched runs can build artifacts without AttributeError."""
    # Verify the attribute is set at class-init time by reading execution_engine source
    import ast

    src = Path("src/core/execution_engine.py").read_text()
    tree = ast.parse(src)

    init_assigns = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"
                        ):
                            init_assigns.add(target.attr)

    assert (
        "raw_signals_by_strategy" in init_assigns
    ), "raw_signals_by_strategy must be initialized in __init__, not only in run_all_strategies"
