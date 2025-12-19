from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd


@dataclass(frozen=True)
class RiskConstraints:
    max_position_weight: float = 0.10
    max_sector_weight: float = 0.30
    cash_buffer_weight: float = 0.10
    cash_symbol: str = "CASH"


def apply_risk_constraints(
    allocations: pd.DataFrame,
    *,
    constraints: RiskConstraints,
    sector_map: Optional[Dict[str, str]] = None,
    symbol_col: str = "ticker",
    weight_col: str = "normalized_weight",
) -> pd.DataFrame:
    df = allocations.copy()

    if df.empty:
        return pd.DataFrame([{symbol_col: constraints.cash_symbol, weight_col: 1.0, "sector": None}])

    if "sector" not in df.columns:
        df["sector"] = None

    if sector_map:
        df["sector"] = df[symbol_col].map(sector_map).fillna(df["sector"])

    df[weight_col] = pd.to_numeric(df[weight_col], errors="coerce").fillna(0.0)
    df = df[df[weight_col] > 0].copy()
    if df.empty:
        return pd.DataFrame([{symbol_col: constraints.cash_symbol, weight_col: 1.0, "sector": None}])

    total = float(df[weight_col].sum())
    if total <= 0:
        return pd.DataFrame([{symbol_col: constraints.cash_symbol, weight_col: 1.0, "sector": None}])

    df["_base"] = df[weight_col] / total

    investable = max(0.0, 1.0 - float(constraints.cash_buffer_weight))
    df[weight_col] = df["_base"] * investable

    max_pos = float(constraints.max_position_weight)
    if max_pos < 1.0:
        clipped = df[weight_col].clip(upper=max_pos)
        excess = float(df[weight_col].sum() - clipped.sum())
        df[weight_col] = clipped
    else:
        excess = 0.0

    max_sector = float(constraints.max_sector_weight)
    if max_sector < 1.0 and df["sector"].notna().any():
        for sector, sector_sum in df.groupby("sector")[weight_col].sum().to_dict().items():
            if sector is None:
                continue
            if float(sector_sum) > max_sector:
                mask = df["sector"] == sector
                factor = max_sector / float(sector_sum)
                new_vals = df.loc[mask, weight_col] * factor
                excess += float(df.loc[mask, weight_col].sum() - new_vals.sum())
                df.loc[mask, weight_col] = new_vals

    eps = 1e-12
    base_order = df.sort_values("_base", ascending=False).index.tolist()

    def _sector_sums() -> Dict[object, float]:
        return df.groupby("sector")[weight_col].sum().to_dict()

    loops = 0
    while excess > eps and loops < 200:
        loops += 1
        sector_sums = _sector_sums()
        made_progress = False

        for idx in base_order:
            w = float(df.at[idx, weight_col])
            pos_room = max(0.0, max_pos - w) if max_pos < 1.0 else excess

            sec = df.at[idx, "sector"]
            if max_sector < 1.0 and sec is not None:
                sec_room = max(0.0, max_sector - float(sector_sums.get(sec, 0.0)))
            else:
                sec_room = excess

            room = min(pos_room, sec_room)
            if room <= eps:
                continue

            add = min(room, excess)
            if add <= eps:
                continue

            df.at[idx, weight_col] = w + add
            excess -= add
            sector_sums[sec] = float(sector_sums.get(sec, 0.0)) + add
            made_progress = True

            if excess <= eps:
                break

        if not made_progress:
            break

    equity_total = float(df[weight_col].sum())
    cash_weight = max(0.0, 1.0 - equity_total)

    out = df.drop(columns=["_base"]).copy()
    out = out[[symbol_col, weight_col, "sector"]]

    out = pd.concat(
        [
            out,
            pd.DataFrame([{symbol_col: constraints.cash_symbol, weight_col: cash_weight, "sector": None}]),
        ],
        ignore_index=True,
    )

    # Renormalize to exactly 1 (floating point hygiene)
    total_out = float(out[weight_col].sum())
    if total_out > 0:
        out[weight_col] = out[weight_col] / total_out

    return out.sort_values(weight_col, ascending=False).reset_index(drop=True)
