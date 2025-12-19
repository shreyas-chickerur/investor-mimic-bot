# Standard library imports
import logging
import math
from dataclasses import dataclass
from datetime import date
from typing import Optional

# Third-party imports
import pandas as pd
from sqlalchemy import create_engine, text

# Local application imports
try:
    from config import Settings
except ImportError:  # pragma: no cover
    Settings = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConvictionConfig:
    recency_half_life_days: int = 90
    min_weight: float = 0.0
    max_positions: Optional[int] = None


def _normalize_db_url(db_url: str) -> str:
    # Project sometimes uses SQLAlchemy async URLs like postgresql+asyncpg://
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return db_url


class ConvictionEngine:
    """V1 conviction model over 13F holdings.

    Signal:
    - Bigger % of investor filing value => higher conviction
    - Multiple investors => additive
    - Newer filings => higher weight (exponential decay)

    Output:
    - Per-ticker normalized allocation weights that sum to 1.
    """

    def __init__(self, db_url: Optional[str] = None):
        if db_url is None:
            if Settings is None:
                raise RuntimeError("No db_url provided and config.Settings could not be imported")
            db_url = Settings().DATABASE_URL
        self.db_url = _normalize_db_url(db_url)
        self._engine = create_engine(self.db_url)

    def holdings_as_of(self, *, as_of: date, lookback_days: int = 365) -> pd.DataFrame:
        """Return holdings joined with filing_date for filings in [as_of-lookback, as_of].

        Note: We compute portfolio weight from value_usd / total_value within *filing*.
        """

        query = """
        WITH eligible_filings AS (
            SELECT
                f.filing_id,
                f.investor_id,
                f.filing_date
            FROM filings f
            WHERE f.filing_date <= CAST(:as_of AS date)
              AND f.filing_date >= (CAST(:as_of AS date) - (:lookback_days * interval '1 day'))::date
        ),
        filing_totals AS (
            SELECT
                h.filing_id,
                SUM(h.value_usd) AS filing_total_value
            FROM holdings h
            JOIN eligible_filings ef ON ef.filing_id = h.filing_id
            GROUP BY h.filing_id
        )
        SELECT
            i.name AS investor_name,
            ef.investor_id,
            ef.filing_id,
            ef.filing_date,
            COALESCE(NULLIF(s.ticker, ''), s.cusip) AS ticker,
            s.cusip,
            s.name AS security_name,
            h.shares,
            h.value_usd,
            ft.filing_total_value,
            CASE
                WHEN ft.filing_total_value IS NULL OR ft.filing_total_value = 0 THEN NULL
                ELSE (h.value_usd / ft.filing_total_value)
            END AS portfolio_weight,
            (CAST(:as_of AS date) - ef.filing_date)::int AS days_old
        FROM eligible_filings ef
        JOIN investors i ON i.investor_id = ef.investor_id
        JOIN holdings h ON h.filing_id = ef.filing_id
        JOIN securities s ON s.security_id = h.security_id
        JOIN filing_totals ft ON ft.filing_id = ef.filing_id
        WHERE COALESCE(NULLIF(s.ticker, ''), s.cusip) IS NOT NULL
        ;
        """

        with self._engine.connect() as conn:
            df = pd.read_sql_query(
                text(query),
                conn,
                params={"as_of": as_of.isoformat(), "lookback_days": int(lookback_days)},
            )

        return df

    def score(self, holdings: pd.DataFrame, *, cfg: ConvictionConfig) -> pd.DataFrame:
        """Compute per-ticker conviction scores and normalized weights."""

        if holdings.empty:
            return pd.DataFrame(
                columns=[
                    "ticker",
                    "security_name",
                    "raw_conviction",
                    "normalized_weight",
                    "investor_count",
                    "investors",
                ]
            )

        # Ensure numeric
        holdings = holdings.copy()
        holdings["portfolio_weight"] = pd.to_numeric(holdings["portfolio_weight"], errors="coerce")
        holdings["days_old"] = pd.to_numeric(holdings["days_old"], errors="coerce")
        holdings = holdings.dropna(subset=["portfolio_weight", "days_old", "ticker"])

        if holdings.empty:
            return pd.DataFrame(
                columns=[
                    "ticker",
                    "security_name",
                    "raw_conviction",
                    "normalized_weight",
                    "investor_count",
                    "investors",
                ]
            )

        # Exponential decay such that half-life is cfg.recency_half_life_days
        half_life = max(int(cfg.recency_half_life_days), 1)
        holdings["recency_weight"] = holdings["days_old"].apply(
            lambda d: math.exp(-math.log(2) * float(d) / float(half_life))
        )

        holdings["raw_conviction"] = holdings["portfolio_weight"] * holdings["recency_weight"]

        agg = (
            holdings.groupby(["ticker", "security_name"], dropna=False)
            .agg(
                raw_conviction=("raw_conviction", "sum"),
                investor_count=("investor_id", "nunique"),
                investors=("investor_name", lambda x: sorted(set(x))),
            )
            .reset_index()
        )

        if cfg.min_weight > 0:
            agg = agg[agg["raw_conviction"] >= float(cfg.min_weight)]

        agg = agg.sort_values("raw_conviction", ascending=False)

        if cfg.max_positions is not None:
            agg = agg.head(int(cfg.max_positions))

        total = float(agg["raw_conviction"].sum()) if not agg.empty else 0.0
        if total > 0:
            agg["normalized_weight"] = agg["raw_conviction"] / total
        else:
            agg["normalized_weight"] = 0.0

        return agg[
            [
                "ticker",
                "security_name",
                "raw_conviction",
                "normalized_weight",
                "investor_count",
                "investors",
            ]
        ]

    def allocations(
        self,
        *,
        as_of: date,
        lookback_days: int = 365,
        cfg: Optional[ConvictionConfig] = None,
    ) -> pd.DataFrame:
        """Convenience: fetch holdings as-of date and return scored allocations."""

        if cfg is None:
            cfg = ConvictionConfig()

        holdings = self.holdings_as_of(as_of=as_of, lookback_days=lookback_days)
        return self.score(holdings, cfg=cfg)
