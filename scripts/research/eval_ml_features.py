#!/usr/bin/env python3
"""
ML Momentum feature-set evaluation — purged/embargoed walk-forward.

Why this exists (EXP-2026-06-22-ml-orthogonal-features, see
docs/research/STRATEGY_CHANGELOG.md): the production ML model reported
near-random purged-OOS accuracy (< 52%) on its 12 mostly-collinear technical
features. The research-backed fix is to add ORTHOGONAL signal — chiefly
cross-sectional rank features, plus distance-from-high and momentum
acceleration (López de Prado, "Advances in Financial ML": cross-sectional and
structural features carry signal that single-name technicals don't).

This harness measures the gate metric directly — mean out-of-sample accuracy
under a purged + embargoed walk-forward (no label leakage across the train/test
boundary) — for BASELINE (12 features) vs ENRICHED (12 + 4 orthogonal). It uses
sklearn's GradientBoostingClassifier (the strategy's own non-LightGBM fallback)
so the result is deterministic and reproducible without libomp.

Usage:
    python3 scripts/research/eval_ml_features.py [--data data/training_data.csv]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sklearn.ensemble import GradientBoostingClassifier  # noqa: E402

HORIZON = 5  # label/holding horizon (days) — also the embargo width
BASELINE_FEATURES = [
    "rsi",
    "rsi_slope_5d",
    "ret_5d",
    "ret_20d",
    "ret_60d",
    "vol_20d",
    "vol_ratio",
    "volume_ratio",
    "price_to_sma20",
    "price_to_sma50",
    "atr_pct",
    "adx",
]
ORTHOGONAL_FEATURES = ["xs_rank_ret20", "xs_rank_ret60", "dist_high_252", "mom_accel"]


def _per_symbol_features(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("date").copy()
    close = g["close"]
    ret = close.pct_change()
    g["rsi_slope_5d"] = g["rsi"] - g["rsi"].shift(5)
    g["ret_5d"] = g.get("returns_5d", close.pct_change(5))
    g["ret_20d"] = g.get("returns_20d", close.pct_change(20))
    g["ret_60d"] = g.get("returns_60d", close.pct_change(60))
    g["vol_20d"] = g.get("volatility_20d", ret.rolling(20).std())
    vol_60d = ret.rolling(60).std()
    g["vol_ratio"] = g["vol_20d"] / vol_60d.replace(0, np.nan)
    g["volume_ratio"] = g["volume"] / g["volume"].rolling(20).mean().replace(0, np.nan)
    sma20 = g.get("sma_20", close.rolling(20).mean())
    sma50 = g.get("sma_50", close.rolling(50).mean())
    g["price_to_sma20"] = (close - sma20) / sma20.replace(0, np.nan)
    g["price_to_sma50"] = (close - sma50) / sma50.replace(0, np.nan)
    atr = g.get("atr_20", (g["high"] - g["low"]).rolling(20).mean())
    g["atr_pct"] = atr / close.replace(0, np.nan)
    if "adx" not in g:
        g["adx"] = 0.0
    # Orthogonal additions
    g["dist_high_252"] = close / close.rolling(252, min_periods=60).max() - 1.0
    g["mom_accel"] = g["ret_5d"] - g["ret_20d"] / 4.0
    # Forward label (beta-adjusted if SPY return supplied later)
    g["fwd_ret"] = close.shift(-HORIZON) / close - 1.0
    return g


def build_dataset(data_path: str) -> pd.DataFrame:
    df = pd.read_csv(data_path)
    if "date" not in df.columns:
        df = df.rename(columns={df.columns[0]: "date"})
    df["date"] = pd.to_datetime(df["date"])
    parts = [_per_symbol_features(g) for _, g in df.groupby("symbol")]
    out = pd.concat(parts, ignore_index=True)

    # Cross-sectional (per-date) percentile ranks — the orthogonal signal.
    out["xs_rank_ret20"] = out.groupby("date")["ret_20d"].rank(pct=True)
    out["xs_rank_ret60"] = out.groupby("date")["ret_60d"].rank(pct=True)

    # Beta-adjusted label: outperform SPY over the horizon (matches the
    # production strategy). Falls back to >0.5% absolute when SPY is absent.
    spy = out[out["symbol"] == "SPY"][["date", "fwd_ret"]].rename(columns={"fwd_ret": "spy_fwd"})
    out = out.merge(spy, on="date", how="left")
    if out["spy_fwd"].notna().any():
        out["label"] = (out["fwd_ret"] > out["spy_fwd"]).astype(int)
    else:
        out["label"] = (out["fwd_ret"] > 0.005).astype(int)
    out = out[out["symbol"] != "SPY"]
    return out


def walk_forward(df: pd.DataFrame, features: list[str], train_days: int, test_days: int) -> dict:
    dates = np.sort(df["date"].unique())
    if len(dates) < train_days + HORIZON + test_days:
        return {"folds": 0, "mean_acc": None, "frac_folds_above_50": None}
    accs: list[float] = []
    start = 0
    while start + train_days + HORIZON + test_days <= len(dates):
        train_end = start + train_days
        # Embargo HORIZON days between train and test so no training label
        # window overlaps the test period (purged walk-forward).
        test_start = train_end + HORIZON
        test_end = test_start + test_days
        train_dates = set(dates[start:train_end])
        test_dates = set(dates[test_start:test_end])

        tr = df[df["date"].isin(train_dates)].dropna(subset=features + ["label"])
        te = df[df["date"].isin(test_dates)].dropna(subset=features + ["label"])
        if len(tr) < 200 or len(te) < 50 or tr["label"].nunique() < 2:
            start += test_days
            continue
        model = GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.03,
            max_depth=3,
            subsample=0.8,
            random_state=0,
        )
        model.fit(tr[features].values, tr["label"].values)
        pred = model.predict(te[features].values)
        accs.append(float((pred == te["label"].values).mean()))
        start += test_days

    if not accs:
        return {"folds": 0, "mean_acc": None, "frac_folds_above_50": None}
    return {
        "folds": len(accs),
        "mean_acc": round(float(np.mean(accs)), 4),
        "std_acc": round(float(np.std(accs)), 4),
        "frac_folds_above_50": round(float(np.mean([a > 0.50 for a in accs])), 3),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/training_data.csv")
    ap.add_argument("--train-days", type=int, default=252)
    ap.add_argument("--test-days", type=int, default=21)
    # Tracked path (not artifacts/, which is gitignored) so the committed
    # snapshot is the evidence the reviewer reads in CI.
    ap.add_argument("--output", default="docs/research/results/ml_feature_eval.json")
    args = ap.parse_args()

    df = build_dataset(args.data)
    base = walk_forward(df, BASELINE_FEATURES, args.train_days, args.test_days)
    enr = walk_forward(df, BASELINE_FEATURES + ORTHOGONAL_FEATURES, args.train_days, args.test_days)
    result = {
        "data": args.data,
        "train_days": args.train_days,
        "test_days": args.test_days,
        "horizon": HORIZON,
        "baseline": base,
        "enriched": enr,
        "delta_mean_acc": (
            round(enr["mean_acc"] - base["mean_acc"], 4)
            if base["mean_acc"] is not None and enr["mean_acc"] is not None
            else None
        ),
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
