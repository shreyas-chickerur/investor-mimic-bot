#!/usr/bin/env python3
"""
validate_snapshot.py — Schema validator for the Investor Mimic dashboard snapshot.

Implements the snapshot.types.ts contract in Python so CI can verify the export
without requiring Node/TypeScript.  Fails loudly with a precise error message
rather than silently producing a broken dashboard.

Usage:
    python scripts/validate_snapshot.py                         # validates latest.json
    python scripts/validate_snapshot.py --file path/to/foo.json
    python scripts/validate_snapshot.py --strict                # also flags null values
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List

OUTPUT_FILE = Path("web/public/data/latest.json")

# ---------------------------------------------------------------------------
# Minimal type-checking primitives
# ---------------------------------------------------------------------------

Errors = List[str]


def _require(errors: Errors, path: str, obj: Any, key: str, *types: type) -> Any:
    """Assert obj[key] exists and is one of `types` (or None if nullable)."""
    if not isinstance(obj, dict):
        errors.append(f"{path}: expected dict, got {type(obj).__name__}")
        return None
    if key not in obj:
        errors.append(f"{path}.{key}: MISSING (required key)")
        return None
    val = obj[key]
    if val is None:
        return None  # null is always allowed per contract
    if types and not isinstance(val, types):
        errors.append(
            f"{path}.{key}: expected {' | '.join(t.__name__ for t in types)}, "
            f"got {type(val).__name__} (value={repr(val)[:60]})"
        )
    return val


def _require_list(errors: Errors, path: str, obj: Any, key: str) -> list | None:
    val = _require(errors, path, obj, key, list)
    return val if isinstance(val, list) else None


def _str_enum(errors: Errors, path: str, val: Any, allowed: set[str]) -> None:
    if val is not None and val not in allowed:
        errors.append(f"{path}: '{val}' not in {sorted(allowed)}")


# ---------------------------------------------------------------------------
# Per-section validators
# ---------------------------------------------------------------------------


def _validate_meta(errors: Errors, snap: dict) -> None:
    m = snap.get("meta")
    if not isinstance(m, dict):
        errors.append("meta: MISSING or not a dict")
        return
    _require(errors, "meta", m, "generatedAt", str)
    _require(errors, "meta", m, "tradingDate", str)
    _require(errors, "meta", m, "runId", str)
    # runNumber: int or null
    if "runNumber" not in m:
        errors.append("meta.runNumber: MISSING")
    elif m["runNumber"] is not None and not isinstance(m["runNumber"], int):
        errors.append(f"meta.runNumber: expected int|null, got {type(m['runNumber']).__name__}")
    if m.get("paper") is not True:
        errors.append("meta.paper: must be true")
    if m.get("schemaVersion") != 1:
        errors.append(f"meta.schemaVersion: must be 1, got {m.get('schemaVersion')!r}")


def _validate_portfolio(errors: Errors, snap: dict) -> None:
    p = snap.get("portfolio")
    if not isinstance(p, dict):
        errors.append("portfolio: MISSING or not a dict")
        return
    for key in [
        "totalValue",
        "cash",
        "positionsCount",
        "todayChangeUsd",
        "todayChangePct",
        "allTimePnlUsd",
        "allTimePnlPct",
        "closedTradesCount",
        "heatCapPct",
        "exposurePct",
    ]:
        _require(errors, "portfolio", p, key, int, float)
    # nullable numerics
    for key in [
        "spyTodayPct",
        "vsSpyPct",
        "sharpe",
        "sortino",
        "maxDrawdownPct",
        "volatilityPct",
        "winRatePct",
        "profitFactor",
    ]:
        if key not in p:
            errors.append(f"portfolio.{key}: MISSING")
        elif p[key] is not None and not isinstance(p[key], (int, float)):
            errors.append(f"portfolio.{key}: expected number|null")
    _str_enum(errors, "portfolio.regime", p.get("regime"), {"LOW_VOL", "NORMAL", "HIGH_VOL"})


def _validate_equity_curve(errors: Errors, snap: dict) -> None:
    curve = snap.get("equityCurve")
    if not isinstance(curve, list):
        errors.append("equityCurve: MISSING or not a list")
        return
    for i, pt in enumerate(curve[:3]):  # spot-check first 3
        if not isinstance(pt, dict):
            errors.append(f"equityCurve[{i}]: not a dict")
            continue
        _require(errors, f"equityCurve[{i}]", pt, "date", str)
        _require(errors, f"equityCurve[{i}]", pt, "value", int, float)
        if "spy" not in pt:
            errors.append(f"equityCurve[{i}].spy: MISSING")


def _validate_strategies(errors: Errors, snap: dict) -> None:
    strats = snap.get("strategies")
    if not isinstance(strats, list):
        errors.append("strategies: MISSING or not a list")
        return
    for i, s in enumerate(strats):
        path = f"strategies[{i}]({s.get('name', '?')})"
        for key in ["key", "name", "holdPeriod", "edgeTechnical", "edgePlain"]:
            _require(errors, path, s, key, str)
        for key in ["allocationPct", "returnPct", "tradesCount", "healthScore"]:
            if key not in s:
                errors.append(f"{path}.{key}: MISSING")
            elif s[key] is not None and not isinstance(s[key], (int, float)):
                errors.append(f"{path}.{key}: expected number|null")
        _str_enum(errors, f"{path}.status", s.get("status"), {"ACTIVE", "WATCHING", "DISABLED"})
        fp = s.get("factorProfile")
        if not isinstance(fp, dict):
            errors.append(f"{path}.factorProfile: MISSING or not a dict")
        else:
            for dim in ["momentum", "quality", "reversion", "volume", "volatility"]:
                if dim not in fp:
                    errors.append(f"{path}.factorProfile.{dim}: MISSING")
                elif not isinstance(fp[dim], (int, float)):
                    errors.append(f"{path}.factorProfile.{dim}: must be a number")


def _validate_positions(errors: Errors, snap: dict) -> None:
    positions = snap.get("positions")
    if not isinstance(positions, list):
        errors.append("positions: MISSING or not a list")
        return
    for i, p in enumerate(positions):
        path = f"positions[{i}]({p.get('symbol','?')})"
        for key in ["symbol", "strategy", "sentimentLabel", "direction"]:
            _require(errors, path, p, key, str)
        _str_enum(errors, f"{path}.direction", p.get("direction"), {"long", "short"})
        # Negative shares are valid (short positions) but must be flagged as such
        if isinstance(p.get("shares"), (int, float)) and p["shares"] < 0:
            if p.get("direction") != "short":
                errors.append(f"{path}: negative shares but direction != 'short'")
        for key in [
            "shares",
            "value",
            "costBasis",
            "unrealizedPlPct",
            "unrealizedPlUsd",
            "sentimentScore",
        ]:
            if key not in p:
                errors.append(f"{path}.{key}: MISSING")
        _str_enum(
            errors,
            f"{path}.sentimentLabel",
            p.get("sentimentLabel"),
            {"BULLISH", "NEUTRAL", "BEARISH"},
        )
        detail = p.get("detail")
        if not isinstance(detail, dict):
            errors.append(f"{path}.detail: MISSING or not a dict")
        else:
            for key in ["priceSpark", "lots", "news"]:
                if not isinstance(detail.get(key), list):
                    errors.append(f"{path}.detail.{key}: expected list")
            if "whyHeld" not in detail:
                errors.append(f"{path}.detail.whyHeld: MISSING")
            if "sentimentMultiplier" not in detail:
                errors.append(f"{path}.detail.sentimentMultiplier: MISSING")


def _validate_trades(errors: Errors, snap: dict) -> None:
    trades = snap.get("trades")
    if not isinstance(trades, list):
        errors.append("trades: MISSING or not a list")
        return
    for i, t in enumerate(trades[:5]):  # spot-check first 5
        path = f"trades[{i}]"
        for key in ["date", "symbol", "strategy", "exitReason"]:
            _require(errors, path, t, key, str)
        _str_enum(errors, f"{path}.side", t.get("side"), {"BUY", "SELL", "COVER"})
        for key in ["shares", "entry", "exit", "realizedPlPct", "realizedPlUsd"]:
            if key not in t:
                errors.append(f"{path}.{key}: MISSING")


def _validate_signals(errors: Errors, snap: dict) -> None:
    sigs = snap.get("signals")
    if not isinstance(sigs, dict):
        errors.append("signals: MISSING or not a dict")
        return
    funnel = sigs.get("funnel")
    if not isinstance(funnel, list):
        errors.append("signals.funnel: MISSING or not a list")
    else:
        for i, f in enumerate(funnel):
            path = f"signals.funnel[{i}]"
            _require(errors, path, f, "stage", str)
            _require(errors, path, f, "count", int, float)
            _require(errors, path, f, "note", str)
    explorer = sigs.get("explorer")
    if not isinstance(explorer, list):
        errors.append("signals.explorer: MISSING or not a list")
    else:
        for i, e in enumerate(explorer[:3]):
            path = f"signals.explorer[{i}]"
            for key in ["symbol", "strategy", "multiplier", "reason"]:
                _require(errors, path, e, key, str)
            _str_enum(
                errors, f"{path}.status", e.get("status"), {"EXECUTED", "FILTERED", "DEFERRED"}
            )


def _validate_analytics(errors: Errors, snap: dict) -> None:
    a = snap.get("analytics")
    if not isinstance(a, dict):
        errors.append("analytics: MISSING or not a dict")
        return
    for key in [
        "drawdown",
        "rollingSharpe",
        "monthlyReturns",
        "returnDistribution",
        "backtestVsLive",
    ]:
        if not isinstance(a.get(key), list):
            errors.append(f"analytics.{key}: expected list")
    corr = a.get("strategyCorrelation")
    if not isinstance(corr, dict):
        errors.append("analytics.strategyCorrelation: expected dict")
    else:
        if not isinstance(corr.get("labels"), list):
            errors.append("analytics.strategyCorrelation.labels: expected list")
        if not isinstance(corr.get("matrix"), list):
            errors.append("analytics.strategyCorrelation.matrix: expected list")


def _validate_health(errors: Errors, snap: dict) -> None:
    h = snap.get("health")
    if not isinstance(h, dict):
        errors.append("health: MISSING or not a dict")
        return
    markers = h.get("markers")
    if not isinstance(markers, list):
        errors.append("health.markers: MISSING or not a list")
    else:
        valid_keys = {"broker", "data", "quality", "breaker", "correlation", "regime"}
        seen_keys = set()
        for i, m in enumerate(markers):
            path = f"health.markers[{i}]"
            k = m.get("key")
            if k not in valid_keys:
                errors.append(f"{path}.key: '{k}' not in {sorted(valid_keys)}")
            else:
                seen_keys.add(k)
            if "ok" not in m or not isinstance(m["ok"], bool):
                errors.append(f"{path}.ok: must be bool")
            _require(errors, path, m, "label", str)
            _require(errors, path, m, "detail", str)
        missing_keys = valid_keys - seen_keys
        if missing_keys:
            errors.append(f"health.markers: missing required keys: {sorted(missing_keys)}")
    if "syncWorkflowUrl" not in h:
        errors.append("health.syncWorkflowUrl: MISSING")


# ---------------------------------------------------------------------------
# Top-level validator
# ---------------------------------------------------------------------------


def validate(snapshot: dict, strict: bool = False) -> Errors:
    errors: Errors = []
    top_keys = {
        "meta",
        "portfolio",
        "equityCurve",
        "strategies",
        "positions",
        "trades",
        "signals",
        "analytics",
        "health",
    }
    for key in top_keys:
        if key not in snapshot:
            errors.append(f"TOP-LEVEL key '{key}': MISSING")

    _validate_meta(errors, snapshot)
    _validate_portfolio(errors, snapshot)
    _validate_equity_curve(errors, snapshot)
    _validate_strategies(errors, snapshot)
    _validate_positions(errors, snapshot)
    _validate_trades(errors, snapshot)
    _validate_signals(errors, snapshot)
    _validate_analytics(errors, snapshot)
    _validate_health(errors, snapshot)
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate snapshot.json against snapshot.types.ts contract"
    )
    parser.add_argument("--file", default=str(OUTPUT_FILE))
    parser.add_argument(
        "--strict", action="store_true", help="Also warn on null values for non-nullable fields"
    )
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)

    snapshot = json.loads(path.read_text())
    errors = validate(snapshot, strict=args.strict)

    if errors:
        print(f"❌  Snapshot validation FAILED ({len(errors)} error(s)):")
        for e in errors:
            print(f"    • {e}")
        sys.exit(1)
    else:
        meta = snapshot.get("meta", {})
        print(
            f"✅  Snapshot valid — tradingDate={meta.get('tradingDate')}  "
            f"generatedAt={meta.get('generatedAt')}  "
            f"schemaVersion={meta.get('schemaVersion')}"
        )
        print(
            f"    strategies={len(snapshot.get('strategies',[]))}  "
            f"positions={len(snapshot.get('positions',[]))}  "
            f"trades={len(snapshot.get('trades',[]))}  "
            f"equityCurve={len(snapshot.get('equityCurve',[]))}"
        )


if __name__ == "__main__":
    main()
