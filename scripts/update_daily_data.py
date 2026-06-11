#!/usr/bin/env python3
"""
Daily Data Update Script
Fetches latest market data and appends to training_data.csv
Ensures data is always fresh for trading strategies
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Import universe from config
from src.data.universe_provider import UniverseProvider


def select_backfill_symbols(
    existing_df,
    universe,
    latest_date,
    min_rows: int = 350,
    min_recent: int = 60,
    max_backfills: int | None = None,
):
    """Pick symbols needing a full-history backfill, capped per run.

    Returns (backfill, deferred): `backfill` is fetched with 730 days this
    run; `deferred` (overflow beyond max_backfills, sorted alphabetically so
    onboarding progresses deterministically across runs) is skipped entirely
    this run and picked up on subsequent runs. Capping keeps a large universe
    expansion from blowing the API budget / run time in a single morning.
    """
    if existing_df is None:
        candidates = sorted(universe)
    else:
        rows_per_symbol = existing_df.groupby("symbol").size()
        recent_cutoff = latest_date - timedelta(days=150) if latest_date is not None else None
        if recent_cutoff is not None:
            recent_counts = (
                existing_df[existing_df["date"] >= recent_cutoff].groupby("symbol").size()
            )
        else:
            recent_counts = pd.Series(dtype=int)
        candidates = sorted(
            s
            for s in universe
            if rows_per_symbol.get(s, 0) < min_rows or recent_counts.get(s, 0) < min_recent
        )
    if max_backfills is None or len(candidates) <= max_backfills:
        return set(candidates), set()
    return set(candidates[:max_backfills]), set(candidates[max_backfills:])


class DailyDataUpdater:
    """Update training data with latest market data"""

    def __init__(self, api_key: str | None = None, symbols: list[str] | None = None):
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY not set")

        self.base_url = "https://www.alphavantage.co/query"
        # Premium keys allow 75 req/min — pace at 1s; free tier stays at 12s
        _premium = os.getenv("ALPHA_VANTAGE_PREMIUM", "false").lower() == "true"
        self.request_interval = 1.0 if _premium else 12.0
        self.max_backfills_per_run = int(os.getenv("MAX_BACKFILLS_PER_RUN", "25"))
        self.universe = UniverseProvider().get_universe()
        self._subset_mode = False
        if symbols:
            allowed = {s.upper() for s in symbols}
            self.universe = [s for s in self.universe if s.upper() in allowed]
            self._subset_mode = True
            logger.info(f"Initialized updater for {len(self.universe)} symbol(s): {self.universe}")
        else:
            logger.info(f"Initialized updater for {len(self.universe)} symbols")

    def fetch_latest_data(self, symbol: str, days: int = 5) -> pd.DataFrame:
        """
        Fetch latest data for a symbol

        Args:
            symbol: Stock symbol
            days: Number of days to fetch (default 5 to ensure we get latest)

        Returns:
            DataFrame with latest OHLCV data
        """
        outputsize = "full" if days > 100 else "compact"
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": outputsize,  # compact ~100 days, full for deep backfills
            "apikey": self.api_key,
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "Time Series (Daily)" not in data:
                logger.warning(
                    f"{symbol}: No data - {data.get('Note', data.get('Error Message', 'Unknown error'))}"
                )
                return None

            ts_data = data["Time Series (Daily)"]

            records = []
            for date_str, values in ts_data.items():
                records.append(
                    {
                        "date": date_str,
                        "symbol": symbol,
                        "open": float(values["1. open"]),
                        "high": float(values["2. high"]),
                        "low": float(values["3. low"]),
                        "close": float(values["4. close"]),
                        "adjusted_close": float(values["5. adjusted close"]),
                        "volume": int(values["6. volume"]),
                    }
                )

            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")

            # Use split/dividend-adjusted OHLC — unadjusted prices make stock
            # splits appear as -75% to -95% crashes and inflate ATR by the
            # split factor for all pre-split historical rows.
            df["raw_close"] = df["close"]
            adj_factor = df["adjusted_close"] / df["raw_close"].replace(0, float("nan"))
            df["close"] = df["adjusted_close"]
            df["open"] = df["open"] * adj_factor
            df["high"] = df["high"] * adj_factor
            df["low"] = df["low"] * adj_factor

            # Get only the latest days
            cutoff = datetime.now() - timedelta(days=days)
            df = df[df["date"] >= cutoff]

            return df

        except Exception as e:
            logger.error(f"Error fetching {symbol} from Alpha Vantage: {e}")
            return self._fetch_fallback_yfinance(symbol, days)

    def _fetch_fallback_yfinance(self, symbol: str, days: int):
        """Fetch OHLCV from yfinance when Alpha Vantage is unavailable.

        yfinance uses Yahoo Finance public endpoints and requires no API key.
        Used as secondary source on rate-limit errors or quota exhaustion.
        """
        try:
            import yfinance as yf  # optional dependency; in requirements.txt
        except ImportError:
            logger.warning("yfinance not installed — cannot use fallback source for %s", symbol)
            return None

        try:
            end = datetime.now()
            start = end - timedelta(days=max(days + 5, 10))  # slight buffer for weekends
            ticker = yf.Ticker(symbol)
            df_raw = ticker.history(start=start.strftime("%Y-%m-%d"), auto_adjust=True)
            if df_raw.empty:
                logger.warning("yfinance returned no data for %s", symbol)
                return None

            df_raw = df_raw.reset_index().rename(
                columns={
                    "Date": "date",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )
            df_raw["date"] = pd.to_datetime(df_raw["date"]).dt.tz_localize(None)
            df_raw["symbol"] = symbol
            df_raw["adjusted_close"] = df_raw["close"]
            df_raw["raw_close"] = df_raw["close"]
            cols = [
                "date",
                "symbol",
                "open",
                "high",
                "low",
                "close",
                "adjusted_close",
                "raw_close",
                "volume",
            ]
            df_raw = df_raw[[c for c in cols if c in df_raw.columns]].sort_values("date")
            cutoff = datetime.now() - timedelta(days=days)
            df_raw = df_raw[df_raw["date"] >= pd.Timestamp(cutoff)]
            logger.info("yfinance fallback: fetched %d rows for %s", len(df_raw), symbol)
            return df_raw
        except Exception as exc:
            logger.error("yfinance fallback failed for %s: %s", symbol, exc)
            return None

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators for new data"""
        df = df.copy()
        df = df.sort_values(["symbol", "date"])

        for symbol in df["symbol"].unique():
            mask = df["symbol"] == symbol
            symbol_data = df[mask].copy()

            # RSI
            delta = symbol_data["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            symbol_data["rsi"] = 100 - (100 / (1 + rs))

            # RSI slope
            symbol_data["rsi_slope"] = symbol_data["rsi"].diff()

            # Moving averages
            symbol_data["sma_20"] = symbol_data["close"].rolling(window=20).mean()
            symbol_data["sma_50"] = symbol_data["close"].rolling(window=50).mean()
            symbol_data["sma_100"] = symbol_data["close"].rolling(window=100).mean()
            symbol_data["sma_200"] = symbol_data["close"].rolling(window=200).mean()

            # Bollinger Bands
            symbol_data["bb_middle"] = symbol_data["close"].rolling(window=20).mean()
            bb_std = symbol_data["close"].rolling(window=20).std()
            symbol_data["bb_upper"] = symbol_data["bb_middle"] + (bb_std * 2)
            symbol_data["bb_lower"] = symbol_data["bb_middle"] - (bb_std * 2)

            # ATR
            high_low = symbol_data["high"] - symbol_data["low"]
            high_close = abs(symbol_data["high"] - symbol_data["close"].shift())
            low_close = abs(symbol_data["low"] - symbol_data["close"].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            symbol_data["atr_20"] = tr.rolling(window=20).mean()

            # Volatility
            returns = symbol_data["close"].pct_change()
            symbol_data["volatility_20d"] = returns.rolling(window=20).std()

            # Rolling price-weighted average (stored as "vwap" for compatibility).
            # This is a 20-day rolling (close × volume) / volume sum — a smoothed
            # cost-basis proxy, NOT the intraday session VWAP used by day traders.
            # Strategies use it as a medium-term price anchor ("near rolling VWAP"
            # means near the average price paid over the last 20 trading days).
            _tp_vol = symbol_data["close"] * symbol_data["volume"]
            _vol_sum = symbol_data["volume"].rolling(window=20).sum().replace(0, float("nan"))
            symbol_data["vwap"] = _tp_vol.rolling(window=20).sum() / _vol_sum

            # ADX (simplified)
            plus_dm = symbol_data["high"].diff()
            minus_dm = -symbol_data["low"].diff()
            plus_dm[plus_dm < 0] = 0
            minus_dm[minus_dm < 0] = 0
            tr_smooth = tr.rolling(window=14).mean()
            plus_di = 100 * (plus_dm.rolling(window=14).mean() / tr_smooth)
            minus_di = 100 * (minus_dm.rolling(window=14).mean() / tr_smooth)
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, float("nan"))
            symbol_data["adx"] = dx.rolling(window=14).mean()

            # Price returns (required by ML Momentum + Factor Momentum)
            symbol_data["returns_5d"] = symbol_data["close"].pct_change(5)
            symbol_data["returns_20d"] = symbol_data["close"].pct_change(20)
            symbol_data["returns_60d"] = symbol_data["close"].pct_change(60)

            # Volatility (60-day annualised)
            symbol_data["volatility_60d"] = symbol_data["close"].pct_change().rolling(60).std()

            # Volume ratio: current / 20-day average
            vol_sma20 = symbol_data["volume"].rolling(20).mean()
            symbol_data["volume_ratio"] = symbol_data["volume"] / vol_sma20.replace(0, float("nan"))

            # Price relative to moving averages
            symbol_data["price_to_sma20"] = (
                symbol_data["close"] - symbol_data["sma_20"]
            ) / symbol_data["sma_20"].replace(0, float("nan"))
            symbol_data["price_to_sma50"] = (
                symbol_data["close"] - symbol_data["sma_50"]
            ) / symbol_data["sma_50"].replace(0, float("nan"))

            df.loc[mask, symbol_data.columns] = symbol_data

        return df

    def update_training_data(
        self, data_file: str = "data/training_data.csv", output_file: str | None = None
    ):
        """Update training data with latest market data"""
        data_path = Path(data_file)
        output_path = Path(output_file) if output_file else data_path

        # Load existing data
        if data_path.exists():
            logger.info(f"Loading existing data from {data_path}")
            existing_df = pd.read_csv(data_path)
            existing_df["date"] = pd.to_datetime(existing_df["date"])
            latest_date = existing_df["date"].max()
            logger.info(
                f"  Existing data: {len(existing_df)} rows, latest date: {latest_date.date()}"
            )
        else:
            logger.warning(f"No existing data found at {data_path}")
            existing_df = None
            latest_date = None

        # Detect symbols that need a full backfill (new to universe or insufficient history)
        # Use 350 rows to keep 200-day SMA valid inside the last 150-day window.
        _backfill_symbols, _deferred_symbols = select_backfill_symbols(
            existing_df,
            self.universe,
            latest_date,
            min_rows=350,
            min_recent=int(os.getenv("MIN_HISTORY_DAYS", "60")),
            max_backfills=self.max_backfills_per_run,
        )
        if _backfill_symbols:
            logger.info(
                f"\n{len(_backfill_symbols)} symbol(s) need backfill: {sorted(_backfill_symbols)}"
            )
        if _deferred_symbols:
            logger.info(
                f"{len(_deferred_symbols)} symbol(s) deferred to later runs "
                f"(backfill cap {self.max_backfills_per_run}): {sorted(_deferred_symbols)}"
            )

        # Fetch latest data for all symbols except deferred onboarding ones
        fetch_universe = [s for s in self.universe if s not in _deferred_symbols]
        logger.info(f"\nFetching latest data for {len(fetch_universe)} symbols...")
        new_data = []
        failed = []

        if existing_df is None:
            logger.info("No existing data — full backfill (730 days per symbol for indicators)")

        for i, symbol in enumerate(fetch_universe, 1):
            days_to_fetch = 730 if symbol in _backfill_symbols else 5
            label = "backfill" if symbol in _backfill_symbols else "update"
            logger.info(f"[{i}/{len(fetch_universe)}] {symbol} ({label}, {days_to_fetch}d)")

            df = self.fetch_latest_data(symbol, days=days_to_fetch)

            if df is not None and len(df) > 0:
                new_data.append(df)
            else:
                failed.append(symbol)

            # Rate limiting: 12s for the 5/min free tier, 1s on premium keys
            if i < len(fetch_universe):
                time.sleep(self.request_interval)

        if failed:
            logger.warning(f"Failed to fetch {len(failed)} symbols: {failed}")

        if not new_data:
            logger.error("No new data fetched!")
            return False

        # Combine new data
        new_df = pd.concat(new_data, ignore_index=True)
        new_df = new_df.sort_values(["date", "symbol"])

        logger.info(f"\nNew data fetched: {len(new_df)} rows")
        logger.info(f"  Date range: {new_df['date'].min().date()} to {new_df['date'].max().date()}")
        logger.info(f"  Symbols: {new_df['symbol'].nunique()}")

        # Merge with existing data
        if existing_df is not None:
            # Remove overlapping dates per symbol (avoid dropping recent history
            # for symbols that are not being backfilled).
            existing_df = existing_df.copy()
            new_min_dates = new_df.groupby("symbol")["date"].min().to_dict()
            overlap_mask = existing_df.apply(
                lambda row: row["date"]
                >= new_min_dates.get(row["symbol"], row["date"] + pd.Timedelta(days=1)),
                axis=1,
            )
            existing_df = existing_df[~overlap_mask]

            # Combine
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            combined_df = combined_df.sort_values(["date", "symbol"])

            # Keep last 2 years of data to prevent file from growing too large
            cutoff_date = datetime.now() - timedelta(days=730)
            combined_df = combined_df[combined_df["date"] >= cutoff_date]

            logger.info(f"\nCombined data: {len(combined_df)} rows")
            logger.info(
                f"  Date range: {combined_df['date'].min().date()} to {combined_df['date'].max().date()}"
            )
        else:
            combined_df = new_df

        # Drop orphaned symbols not in the current universe — stale/removed symbols
        # accumulate NaN indicators and trigger EXCESSIVE_NAN / STALE_DATA blocks every run.
        if not self._subset_mode:
            active_symbols = set(self.universe)
            before_count = combined_df["symbol"].nunique()
            combined_df = combined_df[combined_df["symbol"].isin(active_symbols)]
            after_count = combined_df["symbol"].nunique()
            if before_count != after_count:
                logger.info(
                    f"Pruned {before_count - after_count} orphaned symbol(s) not in current universe"
                )

        # Calculate indicators for the combined dataset
        logger.info("\nCalculating technical indicators...")
        combined_df = self.calculate_indicators(combined_df)

        # Save
        output_path.parent.mkdir(exist_ok=True)
        combined_df.to_csv(output_path, index=False)
        logger.info(f"\n✅ Data saved to {output_path}")
        logger.info(f"  File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
        logger.info(f"  Total rows: {len(combined_df):,}")
        logger.info(f"  Latest date: {combined_df['date'].max().date()}")

        return True


def _parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None
    symbols = [s.strip() for s in value.split(",") if s.strip()]
    return symbols or None


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description="Update daily market data")
    parser.add_argument(
        "--symbols",
        help="Comma-separated subset of symbols to update (overrides full universe)",
        default=os.getenv("DATA_UPDATE_SYMBOLS"),
    )
    parser.add_argument(
        "--output",
        help="Output CSV path (defaults to data/training_data.csv; subset runs default to data/training_data_subset.csv)",
        default=os.getenv("DATA_UPDATE_OUTPUT"),
    )
    args = parser.parse_args()
    symbols = _parse_symbols(args.symbols)
    output_path = args.output
    if symbols and not output_path:
        output_path = "data/training_data_subset.csv"

    logger.info("=" * 80)
    logger.info("DAILY DATA UPDATE")
    logger.info("=" * 80)

    updater = DailyDataUpdater(symbols=symbols)
    success = updater.update_training_data(output_file=output_path)

    if success:
        logger.info("\n" + "=" * 80)
        logger.info("✅ DATA UPDATE COMPLETE")
        logger.info("=" * 80)
        sys.exit(0)
    else:
        logger.error("\n" + "=" * 80)
        logger.error("❌ DATA UPDATE FAILED")
        logger.error("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
