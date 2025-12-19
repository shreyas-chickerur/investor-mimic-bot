# Standard library imports
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Dict, List, Optional

# Third-party imports
import pandas as pd

# Module-level constants for default values
DEFAULT_SHARE_INCREMENT = Decimal("0.0001")
DEFAULT_MIN_TRADE_DOLLARS = Decimal("1.00")


@dataclass(frozen=True)
class AllocationRow:
    ticker: str
    weight: float
    dollar_amount: Decimal
    price: Optional[Decimal]
    shares: Optional[Decimal]


def weights_to_dollars_and_shares(
    allocations: pd.DataFrame,
    *,
    available_capital: Decimal,
    prices: Optional[Dict[str, Decimal]] = None,
    symbol_col: str = "ticker",
    weight_col: str = "normalized_weight",
    allow_fractional: bool = True,
    share_increment: Decimal = DEFAULT_SHARE_INCREMENT,
    min_trade_dollars: Decimal = DEFAULT_MIN_TRADE_DOLLARS,
) -> pd.DataFrame:
    """Convert target weights to dollar allocations and (optional) share quantities.

    - Dollar amounts are proportional to weights.
    - If prices provided, convert dollars to shares.
    - If allow_fractional, shares are rounded down to the nearest `share_increment`.
    - Rows under `min_trade_dollars` are set to 0 dollars (and 0 shares).

    Returns a DataFrame with: ticker, normalized_weight, dollar_amount, price, shares.
    """

    df = allocations.copy()
    if df.empty:
        return pd.DataFrame(columns=[symbol_col, weight_col, "dollar_amount", "price", "shares"])

    df[weight_col] = pd.to_numeric(df[weight_col], errors="coerce").fillna(0.0)
    df = df[df[weight_col] > 0].copy()
    if df.empty:
        return pd.DataFrame(columns=[symbol_col, weight_col, "dollar_amount", "price", "shares"])

    total_w = float(df[weight_col].sum())
    if total_w <= 0:
        return pd.DataFrame(columns=[symbol_col, weight_col, "dollar_amount", "price", "shares"])

    # Normalize weights as hygiene (no behavior change if already normalized)
    df[weight_col] = df[weight_col] / total_w

    available_capital = Decimal(available_capital)

    df["dollar_amount"] = df[weight_col].apply(
        lambda w: (available_capital * Decimal(str(float(w)))).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )
    )

    # Enforce min trade dollars
    df.loc[df["dollar_amount"] < min_trade_dollars, "dollar_amount"] = Decimal("0.00")

    if prices is None:
        df["price"] = None
        df["shares"] = None
        return df[[symbol_col, weight_col, "dollar_amount", "price", "shares"]]

    def _price_for(sym: str) -> Optional[Decimal]:
        p = prices.get(sym)
        if p is None:
            return None
        try:
            return Decimal(p)
        except Exception:
            return None

    out_prices: List[Optional[Decimal]] = []
    out_shares: List[Optional[Decimal]] = []

    for _, row in df.iterrows():
        sym = row[symbol_col]
        dollars: Decimal = row["dollar_amount"]
        p = _price_for(sym)
        out_prices.append(p)

        if p is None or p <= 0 or dollars <= 0:
            out_shares.append(Decimal("0") if p is not None else None)
            continue

        raw_shares = dollars / p
        if not allow_fractional:
            sh = raw_shares.to_integral_value(rounding=ROUND_DOWN)
        else:
            inc = share_increment if share_increment > 0 else Decimal("0.0001")
            sh = (raw_shares // inc) * inc

        if sh <= 0:
            out_shares.append(Decimal("0"))
            continue

        out_shares.append(sh)

    df["price"] = out_prices
    df["shares"] = out_shares

    return df[[symbol_col, weight_col, "dollar_amount", "price", "shares"]]


def weights_to_dollars(weights: Dict[str, float], total_capital: float) -> Dict[str, float]:
    """
    Simple helper to convert weight dict to dollar amounts.
    
    Args:
        weights: Dictionary of {symbol: weight}
        total_capital: Total capital to allocate
        
    Returns:
        Dictionary of {symbol: dollar_amount}
    """
    return {symbol: weight * total_capital for symbol, weight in weights.items()}
