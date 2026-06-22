#!/usr/bin/env python3
"""
Pairs Trading validation — cointegration + dollar-neutral simulation.

The portfolio backtester has no short-leg support, so Pairs Trading is
validated here instead: for each configured pair over the longest available
history, report (a) Engle-Granger cointegration p-value on log prices,
(b) spread half-life from an AR(1) fit, and (c) a dollar-neutral two-leg
simulation using the production strategy's exact rules (60d ratio z-score,
enter long-numerator/short-denominator at z < -1.5, exit at z >= -0.3 or
20-day max hold, 5bps slippage per leg per side).

Acceptance gates (per docs/research): cointegration p < 0.05 AND
half-life < 20 trading days AND simulation profit factor >= 1.1 over
>= 10 round-trips.

Usage:
    python3 scripts/research/validate_pairs.py [--data data/extended_historical_data.csv]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.strategies.strategy_pairs_trading import _DEFAULT_PAIRS  # noqa: E402

ENTRY_Z = 1.5
EXIT_Z = 0.3
LOOKBACK = 60
MAX_HOLD = 20
SLIPPAGE_BPS = 5.0
NOTIONAL_PER_LEG = 10_000.0


# MacKinnon (1991) critical values for the Engle-Granger ADF statistic,
# 2 variables, constant term: reject "no cointegration" if tstat < critical.
EG_CRITICAL = {"1%": -3.90, "5%": -3.34, "10%": -3.04}


def engle_granger_tstat(log_a: pd.Series, log_b: pd.Series, lags: int = 1) -> float | None:
    """Self-contained Engle-Granger step-2 ADF t-statistic.

    (statsmodels 0.11 in this environment is broken against current numpy —
    np.long removal — so the ADF regression is implemented directly.)
    Step 1: OLS hedge a = alpha + beta*b → residual spread.
    Step 2: ADF on the spread: Δs_t = c + γ·s_{t-1} + Σ φ_k·Δs_{t-k}; return
    the t-stat on γ. Compare against EG_CRITICAL (more negative = cointegrated).
    """
    a, b = log_a.values, log_b.values
    beta, alpha = np.polyfit(b, a, 1)
    s = a - (alpha + beta * b)

    ds = np.diff(s)
    y = ds[lags:]
    cols = [np.ones_like(y), s[lags:-1]]
    for k in range(1, lags + 1):
        cols.append(ds[lags - k : -k])
    X = np.column_stack(cols)
    coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = len(y) - X.shape[1]
    if dof <= 0:
        return None
    sigma2 = float(resid @ resid) / dof
    xtx_inv = np.linalg.inv(X.T @ X)
    se_gamma = math.sqrt(sigma2 * xtx_inv[1, 1])
    if se_gamma <= 0:
        return None
    return float(coef[1] / se_gamma)


def spread_half_life(log_a: pd.Series, log_b: pd.Series) -> float | None:
    """Half-life of mean reversion of the OLS-hedged spread (AR(1) fit)."""
    a, b = log_a.values, log_b.values
    beta, alpha = np.polyfit(b, a, 1)
    spread = a - (alpha + beta * b)
    ds = np.diff(spread)
    s_lag = spread[:-1]
    s_lag_c = s_lag - s_lag.mean()
    denom = float((s_lag_c**2).sum())
    if denom <= 0:
        return None
    phi = float((s_lag_c * (ds - ds.mean())).sum()) / denom
    if phi >= 0:
        return None  # not mean-reverting
    return float(-math.log(2) / phi)


def simulate_pair(
    num_close: pd.Series,
    den_close: pd.Series,
    max_hold: int = MAX_HOLD,
    lookback: int = LOOKBACK,
    entry_z: float = ENTRY_Z,
    exit_z: float = EXIT_Z,
) -> dict:
    """Dollar-neutral simulation of the production z-score rules.

    ``max_hold``/``lookback``/thresholds are parameters (defaults reproduce the
    production config) so the universe screener can align the force-exit horizon
    to each pair's measured half-life — a 20-day exit on a 100-day half-life is
    the structural break that sank the original 5 pairs.
    """
    df = pd.DataFrame({"num": num_close, "den": den_close}).dropna()
    ratio = df["num"] / df["den"]
    mean = ratio.rolling(lookback).mean()
    std = ratio.rolling(lookback).std()
    z = (ratio - mean) / std

    slip = SLIPPAGE_BPS / 10_000.0
    trades: list[dict] = []
    daily_pnl: list[float] = []
    in_pos = False
    entry_idx = 0
    num_sh = den_sh = 0.0
    entry_num = entry_den = 0.0
    prev_num = prev_den = 0.0

    dates = df.index
    for i in range(len(df)):
        p_num, p_den, zi = df["num"].iloc[i], df["den"].iloc[i], z.iloc[i]
        if in_pos:
            daily_pnl.append(num_sh * (p_num - prev_num) - den_sh * (p_den - prev_den))
            held = i - entry_idx
            if (not np.isnan(zi) and zi >= -exit_z) or held >= max_hold:
                exit_num = p_num * (1 - slip)
                exit_den = p_den * (1 + slip)
                pnl = num_sh * (exit_num - entry_num) - den_sh * (exit_den - entry_den)
                trades.append(
                    {
                        "entry": str(dates[entry_idx].date()),
                        "exit": str(dates[i].date()),
                        "hold_days": held,
                        "pnl": round(pnl, 2),
                        "exit_reason": "max_hold" if held >= max_hold else "reversion",
                    }
                )
                in_pos = False
        elif not np.isnan(zi) and zi < -entry_z:
            entry_num = p_num * (1 + slip)
            entry_den = p_den * (1 - slip)
            num_sh = NOTIONAL_PER_LEG / entry_num
            den_sh = NOTIONAL_PER_LEG / entry_den
            entry_idx = i
            in_pos = True
        prev_num, prev_den = p_num, p_den

    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    arr = np.array(daily_pnl) / (2 * NOTIONAL_PER_LEG)
    sharpe = (
        float(np.sqrt(252) * arr.mean() / arr.std(ddof=1))
        if len(arr) > 20 and arr.std(ddof=1) > 0
        else None
    )
    equity = np.cumsum(pnls) if pnls else np.array([0.0])
    peak = np.maximum.accumulate(equity)
    max_dd = float((peak - equity).max()) if len(equity) else 0.0
    return {
        "n_trades": len(trades),
        "total_pnl": round(float(sum(pnls)), 2),
        "win_rate_pct": round(len(wins) / len(pnls) * 100, 1) if pnls else None,
        "profit_factor": (
            round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None
        ),
        "sharpe_in_market": round(sharpe, 2) if sharpe is not None else None,
        "max_drawdown_usd": round(max_dd, 2),
        "avg_hold_days": round(float(np.mean([t["hold_days"] for t in trades])), 1)
        if trades
        else None,
        "max_hold_exits_pct": (
            round(sum(1 for t in trades if t["exit_reason"] == "max_hold") / len(trades) * 100, 1)
            if trades
            else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate pairs-trading pairs")
    parser.add_argument("--data", default="data/extended_historical_data.csv")
    args = parser.parse_args()

    print(f"Loading {args.data}...")
    df = pd.read_csv(args.data, index_col=0)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    results = []
    print(
        f"\n{'Pair':<12} {'EG tstat':>8} {'halflife':>9} {'trades':>7} "
        f"{'PnL $':>9} {'PF':>6} {'win%':>6} {'verdict':>8}"
    )
    print("-" * 72)
    for num, den in _DEFAULT_PAIRS:
        a = df[df["symbol"] == num]["close"]
        b = df[df["symbol"] == den]["close"]
        a, b = a.align(b, join="inner")
        if len(a) < 252:
            print(f"{num}/{den:<7} insufficient overlapping history ({len(a)} rows)")
            results.append({"pair": f"{num}/{den}", "error": "insufficient history"})
            continue
        log_a, log_b = np.log(a), np.log(b)
        tstat = engle_granger_tstat(log_a, log_b)
        coint_5pct = tstat is not None and tstat < EG_CRITICAL["5%"]
        halflife = spread_half_life(log_a, log_b)
        sim = simulate_pair(a, b)

        passes = (
            coint_5pct
            and halflife is not None
            and halflife < 20
            and sim["n_trades"] >= 10
            and (sim["profit_factor"] or 0) >= 1.1
        )
        entry = {
            "pair": f"{num}/{den}",
            "rows": len(a),
            "date_range": f"{a.index.min().date()} to {a.index.max().date()}",
            "eg_tstat": round(tstat, 2) if tstat is not None else None,
            "coint_5pct": bool(coint_5pct),
            "half_life_days": round(halflife, 1) if halflife is not None else None,
            "passes_gates": bool(passes),
            **sim,
        }
        results.append(entry)
        print(
            f"{num}/{den:<7} "
            f"{entry['eg_tstat'] if entry['eg_tstat'] is not None else '—':>8} "
            f"{entry['half_life_days'] if entry['half_life_days'] is not None else '—':>9} "
            f"{sim['n_trades']:>7} {sim['total_pnl']:>9} "
            f"{sim['profit_factor'] if sim['profit_factor'] is not None else '—':>6} "
            f"{sim['win_rate_pct'] if sim['win_rate_pct'] is not None else '—':>6} "
            f"{'PASS' if passes else 'FAIL':>8}"
        )

    os.makedirs("artifacts/research", exist_ok=True)
    out = "artifacts/research/pairs_validation.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    n_pass = sum(1 for r in results if r.get("passes_gates"))
    print(f"\n{n_pass}/{len(results)} pairs pass all gates. Saved to {out}")


if __name__ == "__main__":
    main()
