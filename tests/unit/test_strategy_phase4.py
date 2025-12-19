from decimal import Decimal

import pandas as pd

from services.strategy.allocation import weights_to_dollars_and_shares
from services.strategy.conviction_engine import ConvictionConfig, ConvictionEngine
from services.strategy.risk import RiskConstraints, apply_risk_constraints


def test_conviction_scoring_normalizes_and_is_additive():
    engine = ConvictionEngine(db_url="sqlite:///:memory:")

    holdings = pd.DataFrame(
        [
            {
                "investor_name": "A",
                "investor_id": "inv_a",
                "ticker": "AAA",
                "security_name": "AAA Co",
                "portfolio_weight": 0.20,
                "days_old": 0,
            },
            {
                "investor_name": "A",
                "investor_id": "inv_a",
                "ticker": "BBB",
                "security_name": "BBB Co",
                "portfolio_weight": 0.10,
                "days_old": 0,
            },
            {
                "investor_name": "B",
                "investor_id": "inv_b",
                "ticker": "AAA",
                "security_name": "AAA Co",
                "portfolio_weight": 0.10,
                "days_old": 0,
            },
        ]
    )

    out = engine.score(holdings, cfg=ConvictionConfig(recency_half_life_days=90))
    assert set(out["ticker"]) == {"AAA", "BBB"}

    w = out.set_index("ticker")["normalized_weight"].to_dict()
    assert abs(sum(w.values()) - 1.0) < 1e-9

    # AAA has 0.20 + 0.10 vs BBB 0.10 => AAA should be 0.75
    assert abs(w["AAA"] - 0.75) < 1e-9
    assert abs(w["BBB"] - 0.25) < 1e-9


def test_risk_constraints_max_position_sector_and_cash_buffer():
    alloc = pd.DataFrame(
        [
            {"ticker": "A", "normalized_weight": 0.50, "sector": "Tech"},
            {"ticker": "B", "normalized_weight": 0.30, "sector": "Tech"},
            {"ticker": "C", "normalized_weight": 0.20, "sector": "Health"},
        ]
    )

    constrained = apply_risk_constraints(
        alloc,
        constraints=RiskConstraints(max_position_weight=0.10, max_sector_weight=0.30, cash_buffer_weight=0.10),
    )

    weights = constrained.set_index("ticker")["normalized_weight"].to_dict()
    assert abs(sum(weights.values()) - 1.0) < 1e-9

    # Cash must be at least 10%
    assert weights.get("CASH", 0.0) >= 0.10 - 1e-9

    # Max per stock 10%
    for t, w in weights.items():
        if t == "CASH":
            continue
        assert w <= 0.10 + 1e-9

    # Max sector 30% (only for sector-tagged rows)
    sector_totals = constrained[constrained["ticker"] != "CASH"].groupby("sector")["normalized_weight"].sum().to_dict()
    assert sector_totals.get("Tech", 0.0) <= 0.30 + 1e-9
    assert sector_totals.get("Health", 0.0) <= 0.30 + 1e-9


def test_weights_to_dollars_and_fractional_shares_round_down():
    alloc = pd.DataFrame(
        [
            {"ticker": "AAA", "normalized_weight": 0.60},
            {"ticker": "BBB", "normalized_weight": 0.40},
        ]
    )

    prices = {"AAA": Decimal("10.00"), "BBB": Decimal("20.00")}

    out = weights_to_dollars_and_shares(
        alloc,
        available_capital=Decimal("1000.00"),
        prices=prices,
        allow_fractional=True,
        share_increment=Decimal("0.01"),
    )

    by = out.set_index("ticker")

    # $600 / $10 = 60.00 shares
    assert by.loc["AAA", "dollar_amount"] == Decimal("600.00")
    assert by.loc["AAA", "shares"] == Decimal("60.00")

    # $400 / $20 = 20.00 shares
    assert by.loc["BBB", "dollar_amount"] == Decimal("400.00")
    assert by.loc["BBB", "shares"] == Decimal("20.00")
