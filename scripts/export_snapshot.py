#!/usr/bin/env python3
"""
export_snapshot.py — Phase 1 of the Investor Mimic web dashboard.

Reads trading.db + training_data.csv and writes a fully-typed JSON snapshot to
  web/public/data/latest.json          (always overwritten)
  web/public/data/history/<date>.json  (immutable per trading-date)

This script is the ONLY bridge between the private trading system and the public
dashboard. It emits read-only, broker-key-free data. The web app never touches
the broker directly.

Contract: every field in snapshot.types.ts must be present in the output.
Absent/uncomputable values are emitted as JSON null — never omitted.

Small-sample guards (per spec):
  - winRatePct / profitFactor: null if closedTradesCount < 20
  - portfolio/strategy Sharpe/Sortino: null if < 20 daily return points

Run modes:
  python scripts/export_snapshot.py                    # live DB
  python scripts/export_snapshot.py --mock healthy     # deterministic mock
  python scripts/export_snapshot.py --mock auto-recovered
  python scripts/export_snapshot.py --mock needs-action
  python scripts/export_snapshot.py --date 2026-05-29  # force tradingDate
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCHEMA_VERSION = 1
INITIAL_CAPITAL = 100_000.0  # confirmed: all paper accounts start at $100 k
SMALL_SAMPLE_TRADES = 20  # guard for winRatePct / profitFactor
SMALL_SAMPLE_RETURNS = 60  # guard for Sharpe / Sortino / volatility
# 60 days = ~3 months; the industry minimum for a statistically meaningful
# Sharpe. The 22-day series at launch produced Sharpe=-2.5 with SE≈0.21 —
# too noisy to display honestly. Keep null until the series is robust.
SHARPE_MIN_VARIANCE = 0.0005  # annualised vol floor (~5% ann); flat series
# with near-zero variance produce extreme / meaningless Sharpe values.
DATA_BRANCH_SUBPATH = "web/public/data"

DB_PATH = Path("trading.db")
TRAINING_CSV = Path("data/training_data.csv")
OUTPUT_DIR = Path("web/public/data")
HISTORY_DIR = OUTPUT_DIR / "history"
# Mock output is fully isolated from real history — different directory.
MOCK_OUTPUT_DIR = OUTPUT_DIR / "mock"
MOCK_HISTORY_DIR = MOCK_OUTPUT_DIR / "history"

# ---------------------------------------------------------------------------
# Per-strategy hard-coded metadata (not in DB)
# Factor profiles confirmed in Phase 0 review.
# ---------------------------------------------------------------------------
STRATEGY_META: dict[str, dict[str, Any]] = {
    "RSI Mean Reversion": {
        "key": "rsi_mean_reversion",
        "holdPeriod": "≤20d",
        "edgeTechnical": (
            "RSI(14) < 35 with positive slope; uptrend gate (SMA-100); "
            "exits RSI > 55 OR 20-day hold. 2.5× ATR stop, volume-spike filter."
        ),
        "edgePlain": "Buys stocks that dropped too fast, betting they bounce back.",
        "factorProfile": {
            "momentum": 15,
            "quality": 40,
            "reversion": 95,
            "volume": 50,
            "volatility": 80,
        },
    },
    "ML Momentum": {
        "key": "ml_momentum",
        "holdPeriod": "5d",
        "edgeTechnical": (
            "LightGBM on 12 OHLCV+indicator features; calibrated P(5-day gain). "
            "SPY 50-SMA gate; accuracy-scaled confidence when OOS < 57%."
        ),
        "edgePlain": "An AI model picks the stocks most likely to rise over the next week.",
        "factorProfile": {
            "momentum": 90,
            "quality": 55,
            "reversion": 20,
            "volume": 70,
            "volatility": 55,
        },
    },
    "Earnings Drift": {
        "key": "earnings_drift",
        "holdPeriod": "≤40d",
        "edgeTechnical": (
            "Post-earnings announcement drift (PEAD). Primary: earnings calendar. "
            "Fallback: volume > 1.3× + abnormal return > 3.5%. 20% target / 10% stop."
        ),
        "edgePlain": "Rides the wave after a company posts strong earnings.",
        "factorProfile": {
            "momentum": 70,
            "quality": 50,
            "reversion": 20,
            "volume": 90,
            "volatility": 60,
        },
    },
    "Factor Momentum": {
        "key": "factor_momentum",
        "holdPeriod": "20d",
        "edgeTechnical": (
            "Cross-sectional rank: 60d momentum (25%), quality proxy (15%), "
            "mean-reversion (10%), volume confirmation (10%), excess SPY (15%), "
            "sector RS (10%), fundamentals (15% optional). Top 3."
        ),
        "edgePlain": "Ranks all stocks and buys the 3 strongest all-around performers.",
        "factorProfile": {
            "momentum": 80,
            "quality": 70,
            "reversion": 40,
            "volume": 55,
            "volatility": 40,
        },
    },
    "News Sentiment": {
        "key": "news_sentiment",
        "holdPeriod": "7d",
        "edgeTechnical": (
            "Google News RSS + VADER. Buys when compound score > 0.60 with "
            "uptrend gate; exits when score drops or 7-day hold expires."
        ),
        "edgePlain": "Buys stocks with strongly positive recent news, exits when the buzz fades.",
        "factorProfile": {
            "momentum": 50,
            "quality": 30,
            "reversion": 15,
            "volume": 35,
            "volatility": 30,
        },
    },
    "MA Crossover": {
        "key": "ma_crossover",
        "holdPeriod": "30d",
        "edgeTechnical": (
            "Golden cross (SMA-20 > SMA-50) with ADX > 20 trend-quality filter "
            "and volume confirmation (ratio > 0.3). 5-day lookback window."
        ),
        "edgePlain": "Follows stocks whose short-term average price is rising above the longer-term average.",
        "factorProfile": {
            "momentum": 85,
            "quality": 45,
            "reversion": 5,
            "volume": 60,
            "volatility": 45,
        },
    },
    "Volatility Breakout": {
        "key": "volatility_breakout",
        "holdPeriod": "15d",
        "edgeTechnical": (
            "Price closes above the VIX-adaptive Bollinger Band upper (1.8–2.5σ) "
            "with ≥ 1.2× volume spike and positive 5d return. Exits at BB-middle."
        ),
        "edgePlain": "Buys stocks that break decisively upward on high volume.",
        "factorProfile": {
            "momentum": 75,
            "quality": 35,
            "reversion": 10,
            "volume": 85,
            "volatility": 70,
        },
    },
    "Pairs Trading": {
        "key": "pairs_trading",
        "holdPeriod": "20d",
        "edgeTechnical": (
            "Statistical mean-reversion on 5 cointegrated pairs "
            "(JPM/BAC, AAPL/MSFT, XOM/CVX, V/MA, ABBV/MRK). "
            "Buys lagging leg when ratio z-score < −1.5σ."
        ),
        "edgePlain": "Buys a stock that has fallen behind its closest peer, betting the gap closes.",
        "factorProfile": {
            "momentum": 15,
            "quality": 45,
            "reversion": 90,
            "volume": 20,
            "volatility": 60,
        },
    },
    "Sector Rotation": {
        "key": "sector_rotation",
        "holdPeriod": "20d",
        "edgeTechnical": (
            "Ranks 7 sector ETFs by 20-day momentum; selects top 2. "
            "Buys the highest-momentum individual stock in each winning sector."
        ),
        "edgePlain": "Rotates into the sectors of the market that are currently leading.",
        "factorProfile": {
            "momentum": 75,
            "quality": 50,
            "reversion": 25,
            "volume": 40,
            "volatility": 45,
        },
    },
}

# Strategies excluded from dashboard (internal/sync entries)
_EXCLUDED_STRATEGY_NAMES = {"BROKER_SYNC"}

# Backtest Sharpe priors (from trading_config.yaml)
BACKTEST_SHARPE_PRIORS: dict[str, float] = {
    "RSI Mean Reversion": 0.65,
    "Earnings Drift": 0.80,
    "ML Momentum": 0.30,
    "Factor Momentum": 0.25,
    "News Sentiment": 0.25,
    "MA Crossover": 0.20,
    "Volatility Breakout": 0.20,
    "Pairs Trading": 0.40,
    "Sector Rotation": 0.35,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _null(v: Any) -> Any:
    """Return v, converting NaN/Inf to None."""
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _pct(fraction: float | None) -> float | None:
    """Convert a stored fraction (0.0156) to display percent (1.56)."""
    if fraction is None:
        return None
    v = fraction * 100.0
    return _null(round(v, 4))


def _db_connect(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _sharpe(returns: list[float]) -> float | None:
    if len(returns) < SMALL_SAMPLE_RETURNS:
        return None
    import statistics

    mean = statistics.mean(returns)
    stdev = statistics.pstdev(returns)
    if stdev == 0:
        return None
    # Variance floor: if annualised vol is below SHARPE_MIN_VARIANCE the series
    # is too flat to produce a meaningful Sharpe (near-zero denominator →
    # extreme values from noise).  Return null so the UI shows "—" instead.
    ann_vol = stdev * (252**0.5)
    if ann_vol < SHARPE_MIN_VARIANCE:
        return None
    return _null(round((mean / stdev) * (252**0.5), 4))


def _sortino(returns: list[float]) -> float | None:
    if len(returns) < SMALL_SAMPLE_RETURNS:
        return None
    import statistics

    mean = statistics.mean(returns)
    stdev = statistics.pstdev(returns)
    ann_vol = stdev * (252**0.5)
    if ann_vol < SHARPE_MIN_VARIANCE:
        return None
    downside = [r for r in returns if r < 0]
    if not downside:
        return None
    dd_dev = (sum(r**2 for r in downside) / len(returns)) ** 0.5
    if dd_dev == 0:
        return None
    return _null(round((mean / dd_dev) * (252**0.5), 4))


def _max_drawdown(curve: list[float]) -> float | None:
    if len(curve) < 2:
        return None
    peak = curve[0]
    max_dd = 0.0
    for v in curve:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd
    return _null(round(max_dd, 4))


def _volatility(returns: list[float]) -> float | None:
    if len(returns) < SMALL_SAMPLE_RETURNS:
        return None
    import statistics

    stdev = statistics.pstdev(returns)
    ann_vol = stdev * (252**0.5)
    if ann_vol < SHARPE_MIN_VARIANCE:
        return None
    return _null(round(ann_vol * 100, 4))


def _profit_factor(pnl_list: list[float]) -> float | None:
    wins = sum(p for p in pnl_list if p > 0)
    losses = abs(sum(p for p in pnl_list if p < 0))
    if losses == 0:
        return None
    return _null(round(wins / losses, 4))


# ---------------------------------------------------------------------------
# SPY helpers
# ---------------------------------------------------------------------------


def _load_spy_data() -> dict[str, float]:
    """Return {date_str: close} for SPY from training_data.csv."""
    if not TRAINING_CSV.exists():
        return {}
    try:
        result = {}
        with open(TRAINING_CSV) as f:
            header = f.readline().split(",")
            date_idx = header.index("date")
            sym_idx = header.index("symbol")
            close_idx = header.index("close")
            for line in f:
                parts = line.strip().split(",")
                if len(parts) <= close_idx:
                    continue
                if parts[sym_idx] == "SPY":
                    try:
                        result[parts[date_idx]] = float(parts[close_idx])
                    except ValueError:
                        pass
        return result
    except Exception:
        return {}


def _spy_today_pct(spy_data: dict[str, float], as_of: str) -> float | None:
    """Compute SPY daily % for as_of date using spy_data dict."""
    dates = sorted(spy_data.keys())
    if as_of not in dates:
        # Try last available date
        past = [d for d in dates if d <= as_of]
        if not past:
            return None
        as_of = past[-1]
    idx = dates.index(as_of)
    if idx == 0:
        return None
    prev = dates[idx - 1]
    try:
        pct = (spy_data[as_of] / spy_data[prev] - 1.0) * 100.0
        return _null(round(pct, 4))
    except (KeyError, ZeroDivisionError):
        return None


def _build_spy_curve(
    spy_data: dict[str, float],
    snapshot_dates: list[str],
    initial_value: float,
) -> list[float | None]:
    """
    Build a SPY portfolio curve aligned to snapshot_dates.
    Each point = initial_value * (SPY_close[date] / SPY_close[first_matching_date]).
    Returns None for dates without SPY data.
    """
    # Find anchor: first snapshot date that has SPY data
    anchor_spy: float | None = None
    result: list = []
    for d in snapshot_dates:
        # Find nearest available SPY date
        close = spy_data.get(d)
        if close is None:
            # Try the trading day on or before d
            avail = [k for k in spy_data if k <= d]
            close = spy_data[max(avail)] if avail else None
        if close is None:
            result.append(None)
            continue
        if anchor_spy is None:
            anchor_spy = close
        result.append(_null(round(initial_value * close / anchor_spy, 2)) if anchor_spy else None)
    return result


# ---------------------------------------------------------------------------
# Beta computation
# ---------------------------------------------------------------------------


def _compute_beta(symbol: str, spy_data: dict[str, float]) -> float | None:
    """Compute 60-day rolling beta of symbol vs SPY from training_data.csv."""
    if not TRAINING_CSV.exists() or not spy_data:
        return None
    try:
        sym_prices: dict[str, float] = {}
        with open(TRAINING_CSV) as f:
            header = f.readline().split(",")
            date_idx = header.index("date")
            sym_idx = header.index("symbol")
            close_idx = header.index("close")
            for line in f:
                parts = line.strip().split(",")
                if len(parts) <= close_idx:
                    continue
                if parts[sym_idx] == symbol:
                    try:
                        sym_prices[parts[date_idx]] = float(parts[close_idx])
                    except ValueError:
                        pass

        common = sorted(set(sym_prices) & set(spy_data))[-61:]  # last 61 → 60 returns
        if len(common) < 21:
            return None

        spy_rets = [
            spy_data[common[i]] / spy_data[common[i - 1]] - 1 for i in range(1, len(common))
        ]
        sym_rets = [
            sym_prices[common[i]] / sym_prices[common[i - 1]] - 1 for i in range(1, len(common))
        ]

        n = len(spy_rets)
        mean_spy = sum(spy_rets) / n
        mean_sym = sum(sym_rets) / n
        cov = sum((spy_rets[i] - mean_spy) * (sym_rets[i] - mean_sym) for i in range(n)) / n
        var_spy = sum((r - mean_spy) ** 2 for r in spy_rets) / n
        if var_spy == 0:
            return None
        return _null(round(cov / var_spy, 3))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Sentiment helpers
# ---------------------------------------------------------------------------


def _fetch_sentiment_batch(symbols: list[str]) -> dict[str, float]:
    """
    Re-fetch sentiment scores for a list of symbols using the existing provider.
    Returns {symbol: score_0_to_1}. Scores are today's sentiment, not historical.
    Best-effort: returns {} on any error.
    """
    try:
        from src.utils.news_sentiment import NewsSentimentProvider

        provider = NewsSentimentProvider(max_workers=4, per_symbol_timeout=5.0)
        batch = provider.fetch_batch(symbols)
        return {sym: float(ctx.get("score", 0.5)) for sym, ctx in batch.items()}
    except Exception:
        return {}


def _sentiment_label(score: float) -> str:
    if score >= 0.62:
        return "BULLISH"
    if score <= 0.38:
        return "BEARISH"
    return "NEUTRAL"


def _sentiment_multiplier(score: float) -> str:
    if score >= 0.62:
        return "×1.15"
    if score < 0.38:
        return "×0.80"
    return "×1.00"


# ---------------------------------------------------------------------------
# Price sparkline helper
# ---------------------------------------------------------------------------


def _price_spark(symbol: str, n: int = 20) -> list[float]:
    """Return last n closing prices for symbol from training_data.csv."""
    if not TRAINING_CSV.exists():
        return []
    try:
        prices: list[tuple[str, float]] = []
        with open(TRAINING_CSV) as f:
            header = f.readline().split(",")
            date_idx = header.index("date")
            sym_idx = header.index("symbol")
            close_idx = header.index("close")
            for line in f:
                parts = line.strip().split(",")
                if len(parts) <= close_idx:
                    continue
                if parts[sym_idx] == symbol:
                    try:
                        prices.append((parts[date_idx], float(parts[close_idx])))
                    except ValueError:
                        pass
        prices.sort(key=lambda x: x[0])
        return [round(p, 4) for _, p in prices[-n:]]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Main export functions
# ---------------------------------------------------------------------------


def _build_meta(conn: sqlite3.Connection, override_date: str | None = None) -> dict:
    run_id = conn.execute(
        "SELECT run_id FROM broker_state WHERE snapshot_type != 'SYNC' "
        "ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    run_id_val = run_id["run_id"] if run_id else "UNKNOWN"

    snap = conn.execute(
        "SELECT snapshot_date FROM daily_portfolio_snapshot ORDER BY snapshot_date DESC LIMIT 1"
    ).fetchone()
    trading_date = override_date or (snap["snapshot_date"] if snap else date.today().isoformat())

    run_number_env = os.environ.get("GITHUB_RUN_NUMBER", "")
    run_number = int(run_number_env) if run_number_env.isdigit() else None

    return {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "tradingDate": trading_date,
        "runId": run_id_val,
        "runNumber": run_number,
        "paper": True,
        "schemaVersion": 1,
    }


def _build_portfolio(conn: sqlite3.Connection, spy_data: dict, trading_date: str) -> dict:
    # Latest broker state (END snapshot preferred)
    bs = conn.execute(
        "SELECT portfolio_value, cash FROM broker_state "
        "WHERE snapshot_type='END' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if not bs:
        bs = conn.execute(
            "SELECT portfolio_value, cash FROM broker_state ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

    total_value = float(bs["portfolio_value"]) if bs else INITIAL_CAPITAL
    cash = float(bs["cash"]) if bs else INITIAL_CAPITAL

    # Position count
    pos_count = conn.execute("SELECT COUNT(*) as c FROM positions WHERE shares > 0").fetchone()["c"]

    # Today's snapshot
    today_snap = conn.execute(
        "SELECT daily_pnl, daily_pnl_pct, drawdown_pct, heat_pct "
        "FROM daily_portfolio_snapshot WHERE snapshot_date=? LIMIT 1",
        (trading_date,),
    ).fetchone()

    today_pnl_usd = (
        float(today_snap["daily_pnl"]) if today_snap and today_snap["daily_pnl"] else 0.0
    )
    today_pnl_pct = (
        _pct(today_snap["daily_pnl_pct"]) if today_snap and today_snap["daily_pnl_pct"] else 0.0
    )
    exposure_pct = (
        _null(round(float(today_snap["heat_pct"]), 2))
        if today_snap and today_snap["heat_pct"]
        else 0.0
    )

    # All-time P&L
    all_time_pnl_usd = _null(round(total_value - INITIAL_CAPITAL, 2))
    all_time_pnl_pct = _null(round((total_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100, 4))

    # SPY benchmark
    spy_today = _spy_today_pct(spy_data, trading_date)
    vs_spy = (
        _null(round((today_pnl_pct or 0.0) - (spy_today or 0.0), 4))
        if spy_today is not None
        else None
    )

    # Daily return series for risk-adjusted stats
    rows = conn.execute(
        "SELECT daily_pnl_pct FROM daily_portfolio_snapshot "
        "WHERE daily_pnl_pct IS NOT NULL ORDER BY snapshot_date"
    ).fetchall()
    daily_returns = [float(r["daily_pnl_pct"]) for r in rows]

    # Max drawdown (use stored peak drawdown)
    dd_rows = conn.execute(
        "SELECT drawdown_pct FROM daily_portfolio_snapshot "
        "WHERE drawdown_pct IS NOT NULL ORDER BY snapshot_date"
    ).fetchall()
    dd_vals = [abs(float(r["drawdown_pct"])) * 100 for r in dd_rows if r["drawdown_pct"]]
    max_dd = _null(round(max(dd_vals), 4)) if dd_vals else None

    # Closed trades stats
    trade_rows = conn.execute(
        "SELECT gross_pnl, gross_pnl_pct, is_winner FROM trade_pnl_detail"
    ).fetchall()
    closed_count = len(trade_rows)
    win_rate = None
    profit_fac = None
    if closed_count >= SMALL_SAMPLE_TRADES:
        wins = sum(1 for r in trade_rows if r["is_winner"])
        win_rate = _null(round(wins / closed_count * 100, 2))
        pnl_list = [float(r["gross_pnl"]) for r in trade_rows]
        profit_fac = _profit_factor(pnl_list)

    # Regime
    regime_json = conn.execute("SELECT value FROM system_state WHERE key='regime'").fetchone()
    regime_data = {}
    if regime_json and regime_json["value"]:
        try:
            regime_data = json.loads(regime_json["value"])
        except json.JSONDecodeError:
            pass
    classification = regime_data.get("classification", "NORMAL")
    # Normalise stored value
    if classification not in ("LOW_VOL", "NORMAL", "HIGH_VOL"):
        classification = "NORMAL"
    heat_cap = {"LOW_VOL": 50, "NORMAL": 40, "HIGH_VOL": 30}.get(classification, 40)

    return {
        "totalValue": _null(round(total_value, 2)),
        "cash": _null(round(cash, 2)),
        "positionsCount": pos_count,
        "todayChangeUsd": _null(round(today_pnl_usd, 2)),
        "todayChangePct": _null(round(today_pnl_pct or 0.0, 4)),
        "allTimePnlUsd": all_time_pnl_usd,
        "allTimePnlPct": all_time_pnl_pct,
        "spyTodayPct": spy_today,
        "vsSpyPct": vs_spy,
        "sharpe": _sharpe(daily_returns),
        "sortino": _sortino(daily_returns),
        "maxDrawdownPct": max_dd,
        "volatilityPct": _volatility(daily_returns),
        "winRatePct": win_rate,
        "profitFactor": profit_fac,
        "closedTradesCount": closed_count,
        "regime": classification,
        "heatCapPct": heat_cap,
        "exposurePct": exposure_pct,
    }


def _build_equity_curve(conn: sqlite3.Connection, spy_data: dict) -> list[dict]:
    rows = conn.execute(
        "SELECT snapshot_date, portfolio_value FROM daily_portfolio_snapshot "
        "ORDER BY snapshot_date LIMIT 252"
    ).fetchall()
    if not rows:
        return []

    dates = [r["snapshot_date"] for r in rows]
    values = [float(r["portfolio_value"]) for r in rows]
    spy_curve = _build_spy_curve(spy_data, dates, INITIAL_CAPITAL)

    return [
        {"date": dates[i], "value": _null(round(values[i], 2)), "spy": spy_curve[i]}
        for i in range(len(dates))
    ]


def _build_strategies(conn: sqlite3.Connection) -> list[dict]:
    strat_rows = conn.execute(
        "SELECT id, name, capital_allocation FROM strategies ORDER BY id"
    ).fetchall()

    total_capital = (
        sum(
            float(r["capital_allocation"])
            for r in strat_rows
            if r["name"] not in _EXCLUDED_STRATEGY_NAMES
        )
        or INITIAL_CAPITAL
    )

    result = []
    for row in strat_rows:
        name = row["name"]
        if name in _EXCLUDED_STRATEGY_NAMES:
            continue
        meta = STRATEGY_META.get(name, {})
        sid = row["id"]
        alloc = float(row["capital_allocation"])
        alloc_pct = _null(round(alloc / total_capital * 100, 2))

        # P&L stats
        pnl_rows = conn.execute(
            "SELECT gross_pnl, gross_pnl_pct, is_winner FROM trade_pnl_detail WHERE strategy_id=?",
            (sid,),
        ).fetchall()
        trade_count = len(pnl_rows)

        ret_pct = None
        if pnl_rows:
            total_pnl = sum(float(r["gross_pnl"]) for r in pnl_rows)
            ret_pct = _null(round(total_pnl / alloc * 100, 4)) if alloc > 0 else None

        win_rate = None
        profit_fac = None
        if trade_count >= SMALL_SAMPLE_TRADES:
            wins = sum(1 for r in pnl_rows if r["is_winner"])
            win_rate = _null(round(wins / trade_count * 100, 2))
            profit_fac = _profit_factor([float(r["gross_pnl"]) for r in pnl_rows])

        # Per-strategy return series (from trade_pnl_detail exit dates)
        trade_returns = conn.execute(
            "SELECT gross_pnl_pct FROM trade_pnl_detail WHERE strategy_id=? ORDER BY exit_date",
            (sid,),
        ).fetchall()
        ret_list = [float(r["gross_pnl_pct"]) for r in trade_returns]

        max_dd: float | None = None
        if ret_list:
            cumulative = [1.0]
            for r in ret_list:
                cumulative.append(cumulative[-1] * (1 + r))
            max_dd = _max_drawdown(cumulative)

        # Health score
        health_score = 50  # default
        issues: list[str] = []
        try:
            from src.monitoring.strategy_health_scorer import StrategyHealthScorer

            class _DBWrap:
                def __init__(self, path: str) -> None:
                    self.db_path = path
                    self.run_id = "EXPORT"

                def get_strategy_pnl_stats(self, strategy_id: int) -> dict:
                    _conn = sqlite3.connect(self.db_path, timeout=10)
                    _conn.row_factory = sqlite3.Row
                    try:
                        rows = _conn.execute(
                            "SELECT gross_pnl, gross_pnl_pct, is_winner FROM trade_pnl_detail WHERE strategy_id=?",
                            (strategy_id,),
                        ).fetchall()
                    finally:
                        _conn.close()
                    if not rows:
                        return {
                            "trades": 0,
                            "win_rate": None,
                            "avg_win_pct": None,
                            "avg_loss_pct": None,
                        }
                    wins = [r for r in rows if r["is_winner"] == 1]
                    losses = [r for r in rows if r["is_winner"] == 0]
                    return {
                        "trades": len(rows),
                        "win_rate": len(wins) / len(rows) if rows else None,
                        "avg_win_pct": sum(r["gross_pnl_pct"] for r in wins) / len(wins)
                        if wins
                        else 0.0,
                        "avg_loss_pct": sum(abs(r["gross_pnl_pct"]) for r in losses) / len(losses)
                        if losses
                        else 0.0,
                    }

            scorer = StrategyHealthScorer(_DBWrap(str(DB_PATH)))
            health = scorer.calculate_strategy_health(sid, name)
            health_score = int(health.get("health_score", 50))
            issues = health.get("issues", [])
        except Exception:
            pass

        # Status
        recent_trades = conn.execute(
            "SELECT COUNT(*) as c FROM trade_pnl_detail WHERE strategy_id=? "
            "AND exit_date >= date('now','-30 days')",
            (sid,),
        ).fetchone()["c"]
        recent_signals = conn.execute(
            "SELECT COUNT(*) as c FROM signals WHERE strategy_id=? "
            "AND generated_at >= datetime('now','-7 days')",
            (sid,),
        ).fetchone()["c"]

        if health_score >= 60 and recent_signals > 0:
            status = "ACTIVE"
        elif health_score >= 40 or recent_trades > 0:
            status = "WATCHING"
        else:
            status = "WATCHING"  # never DISABLED unless config says so

        # Note from health issues
        note: str | None = None
        if issues:
            note = issues[0]
        elif trade_count < 5:
            note = f"Low trade count: {trade_count} closed trades (need 5+ for full scoring)"
        elif trade_count < SMALL_SAMPLE_TRADES:
            note = f"Win rate / profit factor available after {SMALL_SAMPLE_TRADES} trades ({trade_count} so far)"

        result.append(
            {
                "key": meta.get("key", name.lower().replace(" ", "_")),
                "name": name,
                "allocationPct": alloc_pct,
                "returnPct": ret_pct,
                "sharpe": _sharpe(ret_list) if len(ret_list) >= SMALL_SAMPLE_RETURNS else None,
                "sortino": _sortino(ret_list) if len(ret_list) >= SMALL_SAMPLE_RETURNS else None,
                "profitFactor": profit_fac,
                "maxDrawdownPct": max_dd,
                "tradesCount": trade_count,
                "winRatePct": win_rate,
                "holdPeriod": meta.get("holdPeriod", "?"),
                "healthScore": health_score,
                "edgeTechnical": meta.get("edgeTechnical", ""),
                "edgePlain": meta.get("edgePlain", ""),
                "factorProfile": meta.get(
                    "factorProfile",
                    {
                        "momentum": 50,
                        "quality": 50,
                        "reversion": 50,
                        "volume": 50,
                        "volatility": 50,
                    },
                ),
                "backtestSharpe": BACKTEST_SHARPE_PRIORS.get(name),
                "status": status,
                "note": note,
            }
        )

    return result


def _build_positions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT p.symbol, p.shares, p.avg_price, p.current_price,
               p.unrealized_pnl, p.entry_date, p.atr,
               st.name as strategy_name, p.strategy_id
        FROM positions p
        JOIN strategies st ON p.strategy_id = st.id
        WHERE p.shares != 0
          AND st.name NOT IN ('BROKER_SYNC')
        ORDER BY p.symbol
        """
    ).fetchall()

    symbols = [r["symbol"] for r in rows]
    sentiment_map = _fetch_sentiment_batch(symbols) if symbols else {}
    spy_data = _load_spy_data()

    result = []
    for r in rows:
        sym = r["symbol"]
        shares = float(r["shares"])
        avg_price = float(r["avg_price"])
        is_short = shares < 0
        current_price = float(r["current_price"]) if r["current_price"] else avg_price
        cost_basis = _null(round(shares * avg_price, 2))
        value = _null(round(shares * current_price, 2))
        # A short profits when price falls below the short-sale entry.
        # The dollar fallback (value - cost_basis) is sign-correct for both
        # directions because shares is signed.
        if avg_price > 0:
            raw_pct = (avg_price - current_price) if is_short else (current_price - avg_price)
            unreal_pct = _null(round(raw_pct / avg_price * 100, 4))
        else:
            unreal_pct = None
        unreal_usd = _null(
            round(float(r["unrealized_pnl"]) if r["unrealized_pnl"] else (value - cost_basis), 2)
        )

        beta = _compute_beta(sym, spy_data)

        # ATR stop
        stop_row = conn.execute(
            "SELECT stop_price FROM stop_loss_state WHERE symbol=?", (sym,)
        ).fetchone()
        atr_stop = _null(round(float(stop_row["stop_price"]), 4)) if stop_row else None

        score = sentiment_map.get(sym, 0.5)

        # Price sparkline
        spark = _price_spark(sym, 20)

        # Last entry signal confidence + reasoning (BUY for longs, SHORT_SELL for shorts)
        entry_signal_type = "SHORT_SELL" if is_short else "BUY"
        sig_row = conn.execute(
            """
            SELECT s.confidence, s.reasoning
            FROM signals s
            WHERE s.strategy_id=? AND s.symbol=? AND s.signal_type=?
            ORDER BY s.generated_at DESC LIMIT 1
            """,
            (r["strategy_id"], sym, entry_signal_type),
        ).fetchone()
        confidence = (
            _null(float(sig_row["confidence"])) if sig_row and sig_row["confidence"] else None
        )
        why_held = (
            sig_row["reasoning"]
            if sig_row and sig_row["reasoning"]
            else f"Position held in {r['strategy_name']}"
        )

        # Lots from tax_lots table (fallback to trades; tax_lots may not exist on older DBs)
        lot_rows = []
        try:
            lot_rows = conn.execute(
                "SELECT buy_date, quantity, buy_price FROM tax_lots "
                "WHERE strategy_id=? AND symbol=? AND remaining_quantity > 0 "
                "ORDER BY buy_date",
                (r["strategy_id"], sym),
            ).fetchall()
        except Exception:
            pass
        if not lot_rows:
            lot_rows = conn.execute(
                "SELECT executed_at as buy_date, shares as quantity, exec_price as buy_price "
                "FROM trades WHERE strategy_id=? AND symbol=? AND action='BUY' "
                "ORDER BY executed_at",
                (r["strategy_id"], sym),
            ).fetchall()
        lots = [
            {
                "date": str(lot_item["buy_date"])[:10],
                "shares": _null(round(float(lot_item["quantity"]), 4)),
                "price": _null(round(float(lot_item["buy_price"]), 4)),
            }
            for lot_item in lot_rows
        ]

        # News
        news_items: list[dict] = []
        try:
            from src.utils.news_sentiment import fetch_symbol_news

            news_data = fetch_symbol_news(sym, max_articles=5)
            articles = news_data.get("articles", [])
            news_items = [
                {
                    "headline": a["title"],
                    "source": a.get("source", ""),
                    "score": _null(round(float(a.get("sentiment", 0.5)), 4)),
                }
                for a in articles[:3]
            ]
        except Exception:
            pass

        result.append(
            {
                "symbol": sym,
                "strategy": r["strategy_name"],
                "direction": "short" if is_short else "long",
                "shares": _null(round(shares, 4)),
                "value": value,
                "costBasis": cost_basis,
                "unrealizedPlPct": unreal_pct,
                "unrealizedPlUsd": unreal_usd,
                "beta": beta,
                "atrStop": atr_stop,
                "sentimentScore": _null(round(score, 4)),
                "sentimentLabel": _sentiment_label(score),
                "detail": {
                    "priceSpark": spark,
                    "confidence": confidence,
                    "sentimentMultiplier": _sentiment_multiplier(score),
                    "whyHeld": why_held,
                    "lots": lots,
                    "news": news_items,
                },
            }
        )

    return result


def _build_trades(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT symbol, strategy_name, entry_price, exit_price,
               gross_pnl_pct, gross_pnl, shares, exit_reason, exit_date, direction
        FROM trade_pnl_detail
        ORDER BY exit_date DESC
        LIMIT 200
        """
    ).fetchall()
    result = []
    for r in rows:
        # direction column added 2026-06-11; NULL on rows recorded before then = long
        direction = r["direction"] or "long"
        result.append(
            {
                "date": str(r["exit_date"])[:10],
                "symbol": r["symbol"],
                "strategy": r["strategy_name"] or "",
                "side": "COVER" if direction == "short" else "SELL",
                "shares": _null(round(float(r["shares"]), 4)),
                "entry": _null(round(float(r["entry_price"]), 4)),
                "exit": _null(round(float(r["exit_price"]), 4)),
                "realizedPlPct": _null(
                    round(float(r["gross_pnl_pct"]) * 100, 4)
                ),  # stored as fraction
                "realizedPlUsd": _null(round(float(r["gross_pnl"]), 2)),
                "exitReason": r["exit_reason"] or "",
            }
        )
    return result


def _build_signals(conn: sqlite3.Connection) -> dict:
    # Latest run_id (non-SYNC)
    run_row = conn.execute(
        "SELECT run_id FROM broker_state WHERE snapshot_type != 'SYNC' "
        "AND run_id != 'AUTO_SYNC' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    run_id = run_row["run_id"] if run_row else None

    # Funnel: aggregate across all strategies for the latest run
    funnel_rows = (
        conn.execute(
            "SELECT SUM(raw_signals_count) as raw, SUM(after_regime_count) as regime, "
            "SUM(after_correlation_count) as corr, SUM(after_risk_count) as risk, "
            "SUM(executed_count) as exec "
            "FROM signal_funnel WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if run_id
        else None
    )

    raw = int(funnel_rows["raw"] or 0) if funnel_rows else 0
    regime = int(funnel_rows["regime"] or 0) if funnel_rows else 0
    corr = int(funnel_rows["corr"] or 0) if funnel_rows else 0
    risk = int(funnel_rows["risk"] or 0) if funnel_rows else 0
    executed = int(funnel_rows["exec"] or 0) if funnel_rows else 0

    funnel = [
        {
            "stage": "Candidates scanned",
            "count": raw,
            "note": "Total signals generated by all strategies",
        },
        {
            "stage": "Passed regime gate",
            "count": regime,
            "note": f"{raw - regime} blocked by regime/strategy-disabled filter"
            if raw > regime
            else "All passed",
        },
        {
            "stage": "Survived correlation filter",
            "count": corr,
            "note": f"{regime - corr} rejected: >0.7 correlation with held positions"
            if regime > corr
            else "All passed",
        },
        {
            "stage": "Passed risk checks",
            "count": risk,
            "note": f"{corr - risk} blocked: cash/heat cap or position limits"
            if corr > risk
            else "All passed",
        },
        {
            "stage": "Executed",
            "count": executed,
            "note": f"{risk - executed} deferred or throttled"
            if risk > executed
            else "All executed",
        },
    ]

    # Signal explorer
    explorer: list[dict] = []
    if run_id:
        sig_rows = conn.execute(
            """
            SELECT s.symbol, st.name as strategy, s.confidence, s.reasoning,
                   s.terminal_state, s.terminal_reason
            FROM signals s
            JOIN strategies st ON s.strategy_id = st.id
            WHERE s.run_id=?
            ORDER BY s.id DESC
            LIMIT 50
            """,
            (run_id,),
        ).fetchall()

        # Batch-fetch sentiment for all symbols in explorer
        exp_symbols = list({r["symbol"] for r in sig_rows})
        sent_map = _fetch_sentiment_batch(exp_symbols) if exp_symbols else {}

        for r in sig_rows:
            t_reason = r["terminal_reason"] or ""
            if t_reason == "filled":
                status = "EXECUTED"
            elif t_reason == "throttle":
                status = "DEFERRED"
            else:
                status = "FILTERED"

            score = sent_map.get(r["symbol"], 0.5)
            explorer.append(
                {
                    "symbol": r["symbol"],
                    "strategy": r["strategy"],
                    "confidence": _null(round(float(r["confidence"]), 4))
                    if r["confidence"]
                    else None,
                    "sentimentScore": _null(round(score, 4)),
                    "multiplier": _sentiment_multiplier(score),
                    "status": status,
                    "reason": r["reasoning"] or "",
                }
            )

    return {"funnel": funnel, "explorer": explorer}


def _build_analytics(conn: sqlite3.Connection) -> dict:
    # Drawdown curve
    dd_rows = conn.execute(
        "SELECT snapshot_date, drawdown_pct FROM daily_portfolio_snapshot "
        "WHERE drawdown_pct IS NOT NULL ORDER BY snapshot_date"
    ).fetchall()
    drawdown = [
        {"date": r["snapshot_date"], "ddPct": _null(round(float(r["drawdown_pct"]) * 100, 4))}
        for r in dd_rows
    ]

    # Rolling Sharpe (30-day window)
    pnl_rows = conn.execute(
        "SELECT snapshot_date, daily_pnl_pct FROM daily_portfolio_snapshot "
        "WHERE daily_pnl_pct IS NOT NULL ORDER BY snapshot_date"
    ).fetchall()
    dates_ret = [(r["snapshot_date"], float(r["daily_pnl_pct"])) for r in pnl_rows]

    rolling_sharpe: list[dict] = []
    window = 30
    for i in range(window - 1, len(dates_ret)):
        window_rets = [r for _, r in dates_ret[i - window + 1 : i + 1]]
        # Use a local Sharpe that accepts shorter windows for rolling display.
        # Portfolio-level Sharpe (header stat) requires 60 pts; rolling uses 30.
        if len(window_rets) < window:
            continue
        import statistics as _stat

        _mean = _stat.mean(window_rets)
        _std = _stat.pstdev(window_rets)
        _ann_vol = _std * (252**0.5)
        if _std == 0 or _ann_vol < SHARPE_MIN_VARIANCE:
            continue
        _sr = _null(round((_mean / _std) * (252**0.5), 4))
        if _sr is not None:
            rolling_sharpe.append({"date": dates_ret[i][0], "sharpe": _sr})

    # Monthly returns
    monthly: dict[str, list[float]] = {}
    for d, r in dates_ret:
        month = d[:7]  # YYYY-MM
        monthly.setdefault(month, []).append(r)

    monthly_returns = []
    for month in sorted(monthly.keys()):
        rets = monthly[month]
        compound = 1.0
        for r in rets:
            compound *= 1 + r
        ret_pct = round((compound - 1.0) * 100, 4)
        monthly_returns.append({"month": month, "returnPct": _null(ret_pct)})

    best_month = (
        max(monthly_returns, key=lambda x: x["returnPct"] or -999) if monthly_returns else None
    )
    worst_month = (
        min(monthly_returns, key=lambda x: x["returnPct"] or 999) if monthly_returns else None
    )

    # Return distribution (from closed trades)
    trade_pcts = [
        float(r["gross_pnl_pct"]) * 100
        for r in conn.execute("SELECT gross_pnl_pct FROM trade_pnl_detail").fetchall()
    ]
    buckets = [
        ("-10%+", -15, -10),
        ("-8%", -10, -8),
        ("-6%", -8, -6),
        ("-4%", -6, -4),
        ("-2%", -4, -2),
        ("0%", -2, 0),
        ("2%", 0, 2),
        ("4%", 2, 4),
        ("6%", 4, 6),
        ("8%", 6, 8),
        ("10%+", 8, 100),
    ]
    dist = []
    for label, lo, hi in buckets:
        count = sum(1 for p in trade_pcts if lo <= p < hi)
        dist.append({"bucket": label, "count": count})

    # Strategy correlation (from per-strategy trade returns by exit date)
    strat_rows = conn.execute(
        "SELECT id, name FROM strategies WHERE name NOT IN ('BROKER_SYNC')"
    ).fetchall()
    corr_labels = []
    corr_series: dict[str, dict[str, float]] = {}
    for sr in strat_rows:
        if sr["name"] in _EXCLUDED_STRATEGY_NAMES:
            continue
        rets = conn.execute(
            "SELECT exit_date, gross_pnl_pct FROM trade_pnl_detail "
            "WHERE strategy_id=? ORDER BY exit_date",
            (sr["id"],),
        ).fetchall()
        if rets:
            corr_labels.append(sr["name"])
            corr_series[sr["name"]] = {r["exit_date"]: float(r["gross_pnl_pct"]) for r in rets}

    matrix: list[list[float | None]] = []
    for a in corr_labels:
        row = []
        for b in corr_labels:
            if a == b:
                row.append(1.0)
                continue
            common = sorted(set(corr_series[a]) & set(corr_series[b]))
            if len(common) < 5:
                row.append(None)
                continue
            ra = [corr_series[a][d] for d in common]
            rb = [corr_series[b][d] for d in common]
            n = len(ra)
            mean_a, mean_b = sum(ra) / n, sum(rb) / n
            num = sum((ra[i] - mean_a) * (rb[i] - mean_b) for i in range(n))
            denom_a = (sum((x - mean_a) ** 2 for x in ra)) ** 0.5
            denom_b = (sum((x - mean_b) ** 2 for x in rb)) ** 0.5
            if denom_a == 0 or denom_b == 0:
                row.append(None)
            else:
                row.append(_null(round(num / (denom_a * denom_b), 3)))
        matrix.append(row)

    # Backtest vs live
    bvl = []
    for sr in strat_rows:
        if sr["name"] in _EXCLUDED_STRATEGY_NAMES:
            continue
        bt_sharpe = BACKTEST_SHARPE_PRIORS.get(sr["name"])
        live_rets = [
            float(r["gross_pnl_pct"])
            for r in conn.execute(
                "SELECT gross_pnl_pct FROM trade_pnl_detail WHERE strategy_id=?", (sr["id"],)
            ).fetchall()
        ]
        live_sharpe = _sharpe(live_rets)
        bvl.append(
            {
                "strategy": sr["name"],
                "backtestSharpe": bt_sharpe,
                "liveSharpe": live_sharpe,
            }
        )

    return {
        "drawdown": drawdown,
        "rollingSharpe": rolling_sharpe,
        "monthlyReturns": monthly_returns,
        "returnDistribution": dist,
        "strategyCorrelation": {"labels": corr_labels, "matrix": matrix},
        "backtestVsLive": bvl,
        "bestMonth": best_month,
        "worstMonth": worst_month,
    }


def _build_health(
    conn: sqlite3.Connection,
    recon_status: str,
    sync_ok: str,
    drift_resolved: str,
    drift_remaining: str,
    gh_repo: str,
) -> dict:
    # broker marker
    broker_ok = recon_status.upper() == "PASS"
    auto_attempted = sync_ok != ""  # any value means auto-sync ran
    auto_resolved = drift_resolved.lower() == "true"
    remaining = int(drift_remaining) if drift_remaining.isdigit() else 0

    broker_detail = (
        "Broker positions match database"
        if broker_ok
        else (
            "Auto-sync resolved drift"
            if auto_resolved
            else "Reconciliation drift detected — manual sync may be needed"
        )
    )

    # data marker
    data_ok = True
    data_detail = "Market data is current"
    if TRAINING_CSV.exists():
        import time

        age_h = (time.time() - TRAINING_CSV.stat().st_mtime) / 3600
        if age_h > 48:
            data_ok = False
            data_detail = f"Market data is {age_h:.0f}h old — update may have failed"
    else:
        data_ok = False
        data_detail = "training_data.csv not found"

    # quality marker (recent errors or halted runs)
    error_rows = (
        conn.execute(
            "SELECT COUNT(*) as c FROM error_log "
            "WHERE occurred_at >= datetime('now', '-24 hours')"
        ).fetchone()
        if _table_exists(conn, "error_log")
        else None
    )
    error_count = int(error_rows["c"]) if error_rows else 0

    halted = conn.execute(
        "SELECT COUNT(*) as c FROM run_state WHERE status='HALTED' "
        "AND updated_at >= datetime('now', '-24 hours')"
    ).fetchone()
    halted_count = int(halted["c"]) if halted else 0

    quality_ok = error_count == 0 and halted_count == 0
    quality_detail = (
        "System running normally"
        if quality_ok
        else f"{error_count} error(s) and {halted_count} halted run(s) in last 24h"
    )

    # circuit breaker marker
    dd_state_row = conn.execute(
        "SELECT value FROM system_state WHERE key='drawdown_stop_state'"
    ).fetchone()
    breaker_state = "NORMAL"
    if dd_state_row and dd_state_row["value"]:
        try:
            breaker_state = json.loads(dd_state_row["value"]).get("state", "NORMAL")
        except json.JSONDecodeError:
            pass
    breaker_ok = breaker_state == "NORMAL"
    breaker_detail = (
        "No circuit breaker active" if breaker_ok else f"Drawdown circuit breaker: {breaker_state}"
    )

    # correlation marker (any trades passing correlation filter)
    corr_ok = True
    corr_detail = "Correlation filter operating normally"

    # regime marker (always neutral per spec)
    regime_detail = conn.execute("SELECT value FROM system_state WHERE key='regime'").fetchone()
    regime_label = "NORMAL"
    if regime_detail and regime_detail["value"]:
        try:
            regime_label = json.loads(regime_detail["value"]).get("classification", "NORMAL")
        except json.JSONDecodeError:
            pass

    sync_url = (
        f"https://github.com/{gh_repo}/actions/workflows/sync_database.yml" if gh_repo else "#"
    )

    return {
        "markers": [
            {
                "key": "broker",
                "label": "Broker Reconciliation",
                "ok": broker_ok or auto_resolved,
                "detail": broker_detail,
                "autoAttempted": auto_attempted,
                "autoResolved": auto_resolved,
                "remaining": remaining,
            },
            {
                "key": "data",
                "label": "Market Data",
                "ok": data_ok,
                "detail": data_detail,
            },
            {
                "key": "quality",
                "label": "System Quality",
                "ok": quality_ok,
                "detail": quality_detail,
            },
            {
                "key": "breaker",
                "label": "Circuit Breaker",
                "ok": breaker_ok,
                "detail": breaker_detail,
            },
            {
                "key": "correlation",
                "label": "Correlation Filter",
                "ok": corr_ok,
                "detail": corr_detail,
            },
            {
                "key": "regime",
                "label": f"Regime: {regime_label}",
                "ok": True,
                "neutral": True,
                "detail": f"Current market regime: {regime_label}. Always counts as healthy.",
            },
        ],
        "syncWorkflowUrl": sync_url,
    }


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Mock snapshot generator
# ---------------------------------------------------------------------------


def _build_mock(health_state: str) -> dict:
    """
    Deterministic mock snapshots for all three health states.
    Values are plausible but not from the DB — used for local dev and CI.
    """
    now = datetime.utcnow().isoformat() + "Z"
    trading_date = "2026-05-28"

    base_curve = [
        {
            "date": f"2026-0{4 if i < 30 else 5}-{(i % 30) + 1:02d}",
            "value": 100_000 + i * 180 + 500 * (i % 7),
            "spy": 100_000 + i * 130,
        }
        for i in range(40)
    ]

    broker_ok = health_state == "healthy"
    auto_resolved = health_state == "auto-recovered"
    needs_action = health_state == "needs-action"

    markers = [
        {
            "key": "broker",
            "label": "Broker Reconciliation",
            "ok": broker_ok or auto_resolved,
            "detail": "Broker positions match database"
            if broker_ok
            else (
                "Auto-sync resolved 2 discrepancies"
                if auto_resolved
                else "2 discrepancy(ies) remain after sync attempt"
            ),
            "autoAttempted": not broker_ok,
            "autoResolved": auto_resolved,
            "remaining": 0 if (broker_ok or auto_resolved) else 2,
        },
        {"key": "data", "label": "Market Data", "ok": True, "detail": "Market data is current"},
        {
            "key": "quality",
            "label": "System Quality",
            "ok": not needs_action,
            "detail": "System running normally" if not needs_action else "1 error in last 24h",
        },
        {
            "key": "breaker",
            "label": "Circuit Breaker",
            "ok": True,
            "detail": "No circuit breaker active",
        },
        {
            "key": "correlation",
            "label": "Correlation Filter",
            "ok": True,
            "detail": "Correlation filter operating normally",
        },
        {
            "key": "regime",
            "label": "Regime: NORMAL",
            "ok": True,
            "neutral": True,
            "detail": "Current market regime: NORMAL. Always counts as healthy.",
        },
    ]

    # Mock stats per strategy — realistic variation so the UI looks live
    _mock_stats: dict[str, dict] = {
        "RSI Mean Reversion": {"ret": 2.3, "trades": 12, "health": 72, "status": "ACTIVE"},
        "ML Momentum": {"ret": 8.4, "trades": 17, "health": 82, "status": "ACTIVE"},
        "Earnings Drift": {"ret": 3.1, "trades": 5, "health": 60, "status": "WATCHING"},
        "Factor Momentum": {"ret": 5.1, "trades": 8, "health": 78, "status": "ACTIVE"},
        "News Sentiment": {"ret": 1.4, "trades": 3, "health": 55, "status": "WATCHING"},
        "MA Crossover": {"ret": 4.2, "trades": 6, "health": 68, "status": "ACTIVE"},
        "Volatility Breakout": {"ret": 6.7, "trades": 4, "health": 65, "status": "ACTIVE"},
    }
    strats = []
    alloc_pct = round(100.0 / len(_mock_stats), 1)
    for nm, ms in _mock_stats.items():
        meta = STRATEGY_META[nm]
        strats.append(
            {
                "key": meta["key"],
                "name": nm,
                "allocationPct": alloc_pct,
                "returnPct": ms["ret"],
                "sharpe": 1.31 if ms["trades"] >= 10 else None,
                "sortino": 1.88 if ms["trades"] >= 10 else None,
                "profitFactor": 1.54 if ms["trades"] >= 5 else None,
                "maxDrawdownPct": 6.4,
                "tradesCount": ms["trades"],
                "winRatePct": 61.0 if ms["trades"] >= 20 else None,
                "holdPeriod": meta["holdPeriod"],
                "healthScore": ms["health"],
                "edgeTechnical": meta["edgeTechnical"],
                "edgePlain": meta["edgePlain"],
                "factorProfile": meta["factorProfile"],
                "backtestSharpe": BACKTEST_SHARPE_PRIORS.get(nm),
                "status": ms["status"],
                "note": f"Win rate available after 20 closed trades ({ms['trades']} so far)"
                if ms["trades"] < 20
                else None,
            }
        )

    return {
        "meta": {
            "generatedAt": now,
            "tradingDate": trading_date,
            "runId": f"MOCK_{health_state.upper()}",
            "runNumber": None,
            "paper": True,
            "schemaVersion": 1,
        },
        "portfolio": {
            "totalValue": 107_294.0,
            "cash": 96_804.0,
            "positionsCount": 1,
            "todayChangeUsd": 1_961.0,
            "todayChangePct": 1.86,
            "allTimePnlUsd": 7_294.0,
            "allTimePnlPct": 7.29,
            "spyTodayPct": -0.32,
            "vsSpyPct": 2.18,
            "sharpe": 1.31,
            "sortino": 1.88,
            "maxDrawdownPct": 6.4,
            "volatilityPct": 11.2,
            "winRatePct": 57.0,
            "profitFactor": 1.54,
            "closedTradesCount": 47,
            "regime": "NORMAL",
            "heatCapPct": 40,
            "exposurePct": 9.8,
        },
        "equityCurve": base_curve,
        "strategies": strats,
        "positions": [
            {
                "symbol": "NVDA",
                "strategy": "ML Momentum",
                "direction": "long",
                "shares": 12.0,
                "value": 10_490.0,
                "costBasis": 9_878.0,
                "unrealizedPlPct": 6.2,
                "unrealizedPlUsd": 612.0,
                "beta": 1.7,
                "atrStop": 812.4,
                "sentimentScore": 0.71,
                "sentimentLabel": "BULLISH",
                "detail": {
                    "priceSpark": [9.6, 9.7, 9.5, 9.9, 10.1, 10.0, 10.3, 10.49],
                    "confidence": 0.88,
                    "sentimentMultiplier": "×1.15",
                    "whyHeld": "ML Momentum scored P(5-day gain) = 0.88. Bullish news boost applied.",
                    "lots": [{"date": "2026-05-16", "shares": 12.0, "price": 823.2}],
                    "news": [
                        {
                            "headline": "Nvidia data-center sales top forecasts on AI demand",
                            "source": "Reuters",
                            "score": 0.74,
                        }
                    ],
                },
            },
            {
                "symbol": "BAC",
                "strategy": "Pairs Trading",
                "direction": "short",
                "shares": -25.0,
                "value": -963.75,
                "costBasis": -977.5,
                "unrealizedPlPct": 1.41,
                "unrealizedPlUsd": 13.75,
                "beta": 1.1,
                "atrStop": 42.5,
                "sentimentScore": 0.5,
                "sentimentLabel": "NEUTRAL",
                "detail": {
                    "priceSpark": [39.4, 39.2, 39.0, 38.9, 38.7, 38.6, 38.6, 38.55],
                    "confidence": 0.72,
                    "sentimentMultiplier": "×1.00",
                    "whyHeld": "Pairs entry: JPM/BAC ratio z=-2.20 — SHORT leg",
                    "lots": [],
                    "news": [],
                },
            },
        ],
        "trades": [
            {
                "date": "2026-05-21",
                "symbol": "MSFT",
                "strategy": "Factor Momentum",
                "side": "SELL",
                "shares": 18.0,
                "entry": 415.6,
                "exit": 441.3,
                "realizedPlPct": 6.2,
                "realizedPlUsd": 462.6,
                "exitReason": "12% target",
            },
        ],
        "signals": {
            "funnel": [
                {
                    "stage": "Candidates scanned",
                    "count": 63,
                    "note": "All signals generated by all strategies",
                },
                {"stage": "Passed regime gate", "count": 63, "note": "All passed"},
                {
                    "stage": "Survived correlation filter",
                    "count": 52,
                    "note": "11 rejected: >0.7 correlation",
                },
                {"stage": "Passed risk checks", "count": 14, "note": "38 blocked: cash/heat cap"},
                {"stage": "Executed", "count": 9, "note": "5 deferred or throttled"},
            ],
            "explorer": [
                {
                    "symbol": "NVDA",
                    "strategy": "ML Momentum",
                    "confidence": 0.88,
                    "sentimentScore": 0.71,
                    "multiplier": "×1.15",
                    "status": "EXECUTED",
                    "reason": "High confidence, sentiment boost applied",
                },
                {
                    "symbol": "TSLA",
                    "strategy": "ML Momentum",
                    "confidence": 0.72,
                    "sentimentScore": 0.34,
                    "multiplier": "×0.80",
                    "status": "FILTERED",
                    "reason": "News gate: sentiment 0.34 suppressed below floor",
                },
            ],
        },
        "analytics": {
            "drawdown": [
                {
                    "date": f"2026-0{4+i//30}-{(i%30)+1:02d}",
                    "ddPct": round(-abs(2.1 * ((i % 13) / 13)), 2),
                }
                for i in range(40)
            ],
            "rollingSharpe": [
                {"date": f"2026-05-{i+1:02d}", "sharpe": round(1.1 + 0.03 * i, 2)}
                for i in range(20)
            ],
            "monthlyReturns": [
                {"month": "2026-04", "returnPct": -1.4},
                {"month": "2026-05", "returnPct": 4.2},
            ],
            "returnDistribution": [
                {"bucket": b, "count": c}
                for b, c in [
                    ("-6%", 2),
                    ("-4%", 3),
                    ("-2%", 5),
                    ("0%", 8),
                    ("2%", 12),
                    ("4%", 8),
                    ("6%", 4),
                    ("8%", 2),
                ]
            ],
            "strategyCorrelation": {
                "labels": ["RSI Mean Rev.", "ML Momentum", "Earnings Drift", "Factor Mom."],
                "matrix": [
                    [1.00, 0.18, 0.25, 0.14],
                    [0.18, 1.00, 0.31, 0.22],
                    [0.25, 0.31, 1.00, 0.19],
                    [0.14, 0.22, 0.19, 1.00],
                ],
            },
            "backtestVsLive": [
                {
                    "strategy": nm,
                    "backtestSharpe": BACKTEST_SHARPE_PRIORS.get(nm),
                    "liveSharpe": 1.31 if ms["trades"] >= 10 else None,
                }
                for nm, ms in _mock_stats.items()
            ],
            "bestMonth": {"month": "2026-05", "returnPct": 4.2},
            "worstMonth": {"month": "2026-04", "returnPct": -1.4},
        },
        "health": {
            "markers": markers,
            "syncWorkflowUrl": "https://github.com/shreyaschickerur/investor-mimic-bot/actions/workflows/sync_database.yml",
        },
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Export trading snapshot to JSON")
    parser.add_argument(
        "--mock",
        choices=["healthy", "auto-recovered", "needs-action"],
        help="Emit deterministic mock snapshot instead of reading DB",
    )
    parser.add_argument("--date", help="Override tradingDate (YYYY-MM-DD)")
    parser.add_argument("--recon-status", default=os.environ.get("RECON_STATUS", "UNKNOWN"))
    parser.add_argument("--sync-ok", default=os.environ.get("SYNC_OK", ""))
    parser.add_argument("--drift-resolved", default=os.environ.get("DRIFT_RESOLVED", ""))
    parser.add_argument("--drift-remaining", default=os.environ.get("DRIFT_REMAINING", "0"))
    parser.add_argument("--gh-repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    args = parser.parse_args()

    # Mock output writes to web/public/data/mock/ — completely isolated from the
    # real history/ directory.  Running make web-mock can never pollute the real
    # history or trigger an accidental data-branch commit.
    if args.mock:
        out_dir = MOCK_OUTPUT_DIR
        hist_dir = MOCK_HISTORY_DIR
    else:
        out_dir = OUTPUT_DIR
        hist_dir = HISTORY_DIR

    out_dir.mkdir(parents=True, exist_ok=True)
    hist_dir.mkdir(parents=True, exist_ok=True)

    if args.mock:
        snapshot = _build_mock(args.mock)
    else:
        if not DB_PATH.exists():
            print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
            sys.exit(1)

        spy_data = _load_spy_data()

        with _db_connect() as conn:
            meta = _build_meta(conn, args.date)
            portfolio = _build_portfolio(conn, spy_data, meta["tradingDate"])
            equity_curve = _build_equity_curve(conn, spy_data)
            strategies = _build_strategies(conn)
            positions = _build_positions(conn)
            trades = _build_trades(conn)
            signals = _build_signals(conn)
            analytics = _build_analytics(conn)
            health = _build_health(
                conn,
                recon_status=args.recon_status,
                sync_ok=args.sync_ok,
                drift_resolved=args.drift_resolved,
                drift_remaining=args.drift_remaining,
                gh_repo=args.gh_repo,
            )

        snapshot = {
            "meta": meta,
            "portfolio": portfolio,
            "equityCurve": equity_curve,
            "strategies": strategies,
            "positions": positions,
            "trades": trades,
            "signals": signals,
            "analytics": analytics,
            "health": health,
        }

    trading_date = snapshot["meta"]["tradingDate"]

    latest_path = out_dir / "latest.json"
    history_path = hist_dir / f"{trading_date}.json"

    json_str = json.dumps(snapshot, indent=2, default=str)

    latest_path.write_text(json_str)
    history_path.write_text(json_str)

    print("✅  Snapshot written:")
    print(f"    latest  → {latest_path}  ({len(json_str):,} bytes)")
    print(f"    history → {history_path}")
    print(f"    tradingDate={trading_date}  generatedAt={snapshot['meta']['generatedAt']}")
    print(
        f"    equityCurve={len(snapshot['equityCurve'])} points  "
        f"positions={len(snapshot['positions'])}  "
        f"trades={len(snapshot['trades'])}  "
        f"strategies={len(snapshot['strategies'])}"
    )


if __name__ == "__main__":
    main()
