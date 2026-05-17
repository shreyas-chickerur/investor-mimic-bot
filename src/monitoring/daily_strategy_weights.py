"""Daily strategy weighting meta-layer.

Computes per-strategy multipliers based on current market regime
and recent strategy health, then applies those multipliers to signal confidence.
"""

from __future__ import annotations

CANONICAL_STRATEGY_NAMES = (
    "RSI Mean Reversion",
    "ML Momentum",
    "Earnings Drift",
    "Factor Momentum",
)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def compute_strategy_weights(
    strategy_names: list[str],
    regime_adjustments: dict,
    health_by_strategy: dict[str, dict],
    trailing_sharpe_by_strategy: dict[str, float] | None = None,
) -> dict[str, float]:
    """Return a normalized weight for each strategy in [0.5, 1.5]."""
    vol_regime = (regime_adjustments or {}).get("volatility_regime", "normal")
    trend_regime = (regime_adjustments or {}).get("trend_regime", "weak_trend")
    hmm_regime = (regime_adjustments or {}).get("hmm_regime", "unknown")

    weights: dict[str, float] = {}
    for name in strategy_names:
        w = 1.0

        # Regime-based priors
        if vol_regime == "high_volatility":
            if "RSI" in name:
                w += 0.15
            elif "ML" in name:
                w -= 0.10
            elif "Factor" in name:
                w -= 0.05
            elif "Earnings" in name:
                w += 0.05
        elif vol_regime == "low_volatility":
            if "ML" in name:
                w += 0.10
            elif "Factor" in name:
                w += 0.05
            elif "RSI" in name:
                w -= 0.05

        if trend_regime == "strong_trend":
            if "ML" in name:
                w += 0.15
            elif "Factor" in name:
                w += 0.10
            elif "RSI" in name:
                w -= 0.05
        elif trend_regime == "choppy":
            if "RSI" in name:
                w += 0.15
            elif "ML" in name:
                w -= 0.10
            elif "Factor" in name:
                w -= 0.05

        # Existing HMM bear logic already suppresses RSI BUYs; also reduce its priority.
        if hmm_regime == "bear" and "RSI" in name:
            w -= 0.15

        # Health-based adjustment
        h = health_by_strategy.get(name, {}) or {}
        health_score = h.get("health_score")
        rejection_rate_30d = h.get("rejection_rate_30d")

        if isinstance(health_score, (int, float)):
            if health_score >= 80:
                w += 0.10
            elif health_score < 40:
                w -= 0.20
            elif health_score < 60:
                w -= 0.10

        if isinstance(rejection_rate_30d, (int, float)) and rejection_rate_30d > 0.80:
            w -= 0.10

        # Trailing 30-day Sharpe ratio adjustment (portfolio-level conviction weighting).
        # Strategies with strong recent risk-adjusted returns get more capital; cold
        # streaks get less. Clamped so no strategy is ever fully cut or over-leveraged.
        if trailing_sharpe_by_strategy:
            sharpe = trailing_sharpe_by_strategy.get(name)
            if isinstance(sharpe, (int, float)) and not (sharpe != sharpe):  # not NaN
                if sharpe > 1.0:
                    w += 0.15
                elif sharpe > 0.5:
                    w += 0.05
                elif sharpe < 0.0:
                    w -= 0.20
                elif sharpe < 0.5:
                    w -= 0.10

        weights[name] = _clamp(round(w, 3), 0.5, 1.5)

    return weights


def apply_strategy_weight_to_signals(
    strategy_name: str,
    signals: list[dict],
    strategy_weights: dict[str, float],
    min_buy_confidence: float = 0.45,
) -> list[dict]:
    """Apply strategy weight to confidence and drop weak BUYs when strategy is de-prioritized."""
    weight = float(strategy_weights.get(strategy_name, 1.0))
    adjusted: list[dict] = []

    for sig in signals or []:
        clone = dict(sig)
        conf = float(clone.get("confidence", 0.5))
        action = clone.get("action", "BUY")

        weighted_conf = max(0.0, min(1.0, conf * weight))
        clone["strategy_weight"] = weight
        clone["base_confidence"] = conf
        clone["confidence"] = weighted_conf

        if action == "BUY" and weight < 0.8 and weighted_conf < min_buy_confidence:
            continue

        adjusted.append(clone)

    adjusted.sort(key=lambda s: float(s.get("confidence", 0.0)), reverse=True)
    return adjusted
