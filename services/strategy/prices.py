# Standard library imports
import logging
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Optional, List

# Third-party imports
import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PriceConfig:
    cache_dir: str = "data/backtest/price_cache"


class PriceProvider:
    def get_prices(self, tickers: List[str], start: date, end: date) -> pd.DataFrame:
        raise NotImplementedError


class StooqPriceProvider(PriceProvider):
    """Download daily prices from Stooq (free, no API key).

    Symbols use `.us` suffix for US equities. We try both raw + `.us`.
    """

    def __init__(self, cfg: Optional[PriceConfig] = None):
        self.cfg = cfg or PriceConfig()
        self.cache_path = Path(self.cfg.cache_dir)
        self.cache_path.mkdir(parents=True, exist_ok=True)

    def _cache_file(self, symbol: str) -> Path:
        safe = symbol.replace("/", "_").replace(":", "_")
        return self.cache_path / f"stooq_{safe}.parquet"

    def _download_symbol(self, symbol: str) -> pd.DataFrame:
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            resp.raise_for_status()
            df = pd.read_csv(StringIO(resp.text))
        except Exception as e:
            raise RuntimeError(f"Failed downloading {symbol} from stooq: {e}")

        if df.empty or "Date" not in df.columns:
            raise RuntimeError(f"No data for {symbol} from stooq")

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).set_index("Date").sort_index()
        # Prefer Close; fall back to other if missing
        col = "Close" if "Close" in df.columns else ("close" if "close" in df.columns else None)
        if col is None:
            raise RuntimeError(f"Unexpected columns for {symbol}: {list(df.columns)}")
        return df[[col]].rename(columns={col: symbol})

    def _load_or_download(self, symbol: str) -> pd.DataFrame:
        cache = self._cache_file(symbol)
        if cache.exists():
            try:
                return pd.read_parquet(cache)
            except Exception:
                pass

        df = self._download_symbol(symbol)
        try:
            df.to_parquet(cache)
        except Exception:
            # caching isn't critical
            pass
        return df

    def get_prices(self, tickers: List[str], start: date, end: date) -> pd.DataFrame:
        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)

        frames = []
        for t in sorted(set([x for x in tickers if x])):
            candidates = [t.lower(), f"{t.lower()}.us"]
            got = None
            for sym in candidates:
                try:
                    df = self._load_or_download(sym)
                    got = df
                    break
                except Exception:
                    continue

            if got is None:
                logger.warning("No stooq price data for %s", t)
                continue

            # Rename column back to ticker
            got = got.rename(columns={got.columns[0]: t})
            frames.append(got)

        if not frames:
            return pd.DataFrame()

        prices = pd.concat(frames, axis=1)
        prices = prices.loc[(prices.index >= start_dt) & (prices.index <= end_dt)]
        prices = prices.sort_index()
        prices = prices.ffill()
        return prices


class SyntheticPriceProvider(PriceProvider):
    """Deterministic synthetic prices so the backtest can always run.

    This is a fallback when no external price source is available.
    """

    def __init__(self, seed: int = 7):
        self.seed = seed

    def get_prices(self, tickers: List[str], start: date, end: date) -> pd.DataFrame:
        tickers = sorted(set([t for t in tickers if t]))
        if not tickers:
            return pd.DataFrame()

        idx = pd.date_range(start=start, end=end, freq="B")
        if len(idx) == 0:
            return pd.DataFrame(index=idx)

        rng = np.random.default_rng(self.seed)
        prices = pd.DataFrame(index=idx)

        for i, t in enumerate(tickers):
            # Small drift + noise
            daily = rng.normal(loc=0.0002, scale=0.02, size=len(idx))
            series = 100.0 * np.exp(np.cumsum(daily))
            prices[t] = series

        return prices


def default_price_provider() -> PriceProvider:
    # Prefer Stooq, but fall back to synthetic if it fails at runtime.
    return StooqPriceProvider()
