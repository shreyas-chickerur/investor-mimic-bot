#!/usr/bin/env python3
"""
Export → validate round-trip for short positions: the dashboard snapshot must
carry direction-aware fields (side=COVER, direction=short, sign-correct P&L)
and pass schema validation with negative share counts.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))

import export_snapshot  # noqa: E402  (scripts/export_snapshot.py)
import validate_snapshot  # noqa: E402

from src.core.database import TradingDatabase  # noqa: E402


@pytest.fixture
def conn(tmp_path, monkeypatch):
    """Populated DB with one long, one short, one covered short + long exit."""
    db = TradingDatabase(db_path=str(tmp_path / "test.db"))
    with sqlite3.connect(db.db_path) as c:
        c.execute(
            "INSERT INTO strategies (id, name, capital_allocation, initial_capital) "
            "VALUES (1, 'Pairs Trading', 12500, 12500)"
        )
        c.execute(
            "INSERT INTO positions (strategy_id, symbol, shares, avg_price, current_price, "
            " entry_date, last_updated) "
            "VALUES (1, 'JPM', 10, 180.0, 185.0, '2026-06-01', '2026-06-10')"
        )
        c.execute(
            "INSERT INTO positions (strategy_id, symbol, shares, avg_price, current_price, "
            " entry_date, last_updated) "
            "VALUES (1, 'BAC', -25, 40.0, 38.0, '2026-06-01', '2026-06-10')"
        )
        c.commit()
    db.log_trade_pnl(
        strategy_id=1,
        strategy_name="Pairs Trading",
        symbol="CVX",
        sell_run_id="r1",
        entry_price=150.0,
        exit_price=140.0,
        shares=5.0,
        direction="short",
    )
    db.log_trade_pnl(
        strategy_id=1,
        strategy_name="Pairs Trading",
        symbol="XOM",
        sell_run_id="r1",
        entry_price=100.0,
        exit_price=112.0,
        shares=5.0,
    )

    # Keep the test hermetic: no network sentiment/news, no SPY beta data
    monkeypatch.setattr(export_snapshot, "_fetch_sentiment_batch", lambda symbols: {})
    monkeypatch.setattr(export_snapshot, "_load_spy_data", lambda: {})
    monkeypatch.setattr(export_snapshot, "_price_spark", lambda symbol, n=20: [])

    connection = sqlite3.connect(db.db_path)
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


def test_short_position_exports_with_direction_and_correct_pnl(conn):
    positions = export_snapshot._build_positions(conn)
    by_symbol = {p["symbol"]: p for p in positions}

    short = by_symbol["BAC"]
    assert short["direction"] == "short"
    assert short["shares"] == -25.0
    # Price fell 40 → 38: the short is UP 5%
    assert short["unrealizedPlPct"] == pytest.approx(5.0)
    assert short["unrealizedPlUsd"] == pytest.approx(50.0)

    long_pos = by_symbol["JPM"]
    assert long_pos["direction"] == "long"
    assert long_pos["unrealizedPlPct"] == pytest.approx(180.0 and (5.0 / 180.0 * 100), rel=1e-3)


def test_covered_short_exports_as_cover_side(conn):
    trades = export_snapshot._build_trades(conn)
    by_symbol = {t["symbol"]: t for t in trades}

    assert by_symbol["CVX"]["side"] == "COVER"
    assert by_symbol["CVX"]["realizedPlUsd"] == pytest.approx(50.0)  # (150-140)*5
    assert by_symbol["XOM"]["side"] == "SELL"
    assert by_symbol["XOM"]["realizedPlUsd"] == pytest.approx(60.0)


def test_exported_shorts_pass_schema_validation(conn):
    errors: list = []
    snap = {
        "positions": export_snapshot._build_positions(conn),
        "trades": export_snapshot._build_trades(conn),
    }
    validate_snapshot._validate_positions(errors, snap)
    validate_snapshot._validate_trades(errors, snap)
    assert errors == [], f"schema validation failed: {errors}"


def test_validator_rejects_unflagged_negative_shares():
    errors: list = []
    snap = {
        "positions": [
            {
                "symbol": "BAC",
                "strategy": "Pairs Trading",
                "direction": "long",  # WRONG — negative shares must be short
                "shares": -25.0,
                "value": -950.0,
                "costBasis": -1000.0,
                "unrealizedPlPct": 5.0,
                "unrealizedPlUsd": 50.0,
                "sentimentScore": 0.5,
                "sentimentLabel": "NEUTRAL",
                "detail": {
                    "priceSpark": [],
                    "lots": [],
                    "news": [],
                    "whyHeld": "x",
                    "sentimentMultiplier": "×1.00",
                },
            }
        ]
    }
    validate_snapshot._validate_positions(errors, snap)
    assert any("negative shares" in e for e in errors)
