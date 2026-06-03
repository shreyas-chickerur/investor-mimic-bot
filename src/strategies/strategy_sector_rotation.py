#!/usr/bin/env python3
"""
Strategy: Explicit Sector Rotation

Ranks the 7 sector ETFs in the existing universe by 20-day momentum, then
buys the top 1-2 individual stocks from each outperforming sector.  This is
an explicit rotation strategy (rotate capital toward leading sectors) vs the
Factor Momentum strategy which takes a multi-factor cross-sectional approach.

Academic basis:
  Moskowitz & Grinblatt (1999) — "Do Industries Explain Momentum?"
  Sector momentum persists 3-12 months; inter-sector dispersion creates alpha.
  Faber (2010) — "Relative Strength Strategies for Investing."

Mechanics:
  1. Rank sector ETFs by 20-day price return.
  2. Select top N sectors (default 2).
  3. Within each selected sector, pick the top 1 stock by individual momentum
     (returns_20d), avoiding stocks already held by other strategies.
  4. Standard exits: profit target, time limit, or re-rank rotation.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd

from src.core.strategy_base import TradingStrategy
from src.utils.config_loader import get_config

logger = logging.getLogger(__name__)

# Sector ETF → list of constituent stock symbols (from the tradeable universe)
_SECTOR_CONSTITUENTS: dict[str, list[str]] = {
    "XLK": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "ADBE", "CRM", "AMD", "AVGO", "ACN"],
    "XLV": ["JNJ", "ABBV", "MRK", "UNH", "LLY", "TMO", "DHR", "ABT"],
    "XLF": ["JPM", "V", "MA", "BAC"],
    "XLY": ["TSLA", "NFLX", "COST", "MCD", "NKE", "WMT", "HD", "DIS"],
    "XLP": ["KO", "PEP", "PG"],
    "XLE": ["XOM", "CVX"],
}


class SectorRotationStrategy(TradingStrategy):
    """Sector momentum rotation: overweight stocks in the strongest sectors."""

    def __init__(self, strategy_id: int, capital: float):
        super().__init__(strategy_id=strategy_id, name="Sector Rotation", capital=capital)
        cfg = get_config()
        sr_cfg = cfg.get("strategies.sector_rotation", {}) or {}
        self.top_sectors: int = sr_cfg.get("top_sectors", 2)
        self.stocks_per_sector: int = sr_cfg.get("stocks_per_sector", 1)
        self.sector_lookback: int = sr_cfg.get("sector_lookback_days", 20)
        self.hold_days: int = sr_cfg.get("hold_days", 20)
        self.max_hold_days: int = sr_cfg.get("max_hold_days", 35)
        self.profit_target_pct: float = sr_cfg.get("profit_target_pct", 0.12)
        self.entry_dates: dict = {}
        self._partial_exit_done: set = set()

    def _spy_above_sma50(self, market_data: pd.DataFrame) -> bool:
        spy = (
            market_data[market_data["symbol"] == "SPY"]
            if "symbol" in market_data.columns
            else pd.DataFrame()
        )
        if len(spy) < 50:
            return True
        prices = spy["close"].values
        return float(prices[-1]) > float(np.mean(prices[-50:]))

    def _sector_momentum(self, sym_map: dict[str, pd.DataFrame]) -> dict[str, float]:
        """Return a dict of sector ETF → recent N-day return, for ranking."""
        momentum = {}
        for etf in _SECTOR_CONSTITUENTS:
            if etf not in sym_map:
                continue
            prices = sym_map[etf]["close"].tail(self.sector_lookback + 1)
            if len(prices) < self.sector_lookback + 1:
                continue
            ret = float((prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0])
            momentum[etf] = ret
        return momentum

    def generate_signals(self, market_data: pd.DataFrame) -> list[dict]:
        signals: list[dict] = []
        if market_data.empty or "symbol" not in market_data.columns:
            return signals

        market_uptrend = self._spy_above_sma50(market_data)
        sym_map = {sym: grp for sym, grp in market_data.groupby("symbol")}
        latest_date = market_data.index[-1] if len(market_data) > 0 else None

        # --- Exits for held positions ---
        for symbol in list(self.positions.keys()):
            if symbol not in sym_map:
                continue
            sym_data = sym_map[symbol]
            price = float(sym_data.iloc[-1]["close"])
            days_held = self.get_days_held(symbol, latest_date)
            entry_price = getattr(self, "entry_prices", {}).get(symbol)

            exit_reason = None
            exit_shares = self.positions[symbol]
            partial_exit = False

            if entry_price and entry_price > 0:
                pnl_pct = (price - entry_price) / entry_price
                if pnl_pct >= self.profit_target_pct and symbol not in self._partial_exit_done:
                    exit_shares = max(1, self.positions[symbol] // 2)
                    exit_reason = f"Sector rotation profit target: {pnl_pct:.1%} → selling 50%"
                    partial_exit = True

            if exit_reason is None and days_held >= self.hold_days:
                exit_reason = f"Sector rebalance: held {days_held}d"

            if exit_reason:
                signals.append(
                    {
                        "symbol": symbol,
                        "action": "SELL",
                        "shares": exit_shares,
                        "price": price,
                        "value": exit_shares * price,
                        "confidence": 0.80,
                        "reasoning": exit_reason,
                        "asof_date": latest_date,
                        "partial_exit": partial_exit,
                    }
                )
                if partial_exit:
                    self._partial_exit_done.add(symbol)

        if not market_uptrend:
            logger.info("Sector Rotation: market downtrend — skipping new entries")
            return signals

        # --- New entries: rotate into top-sector stocks ---
        sector_rets = self._sector_momentum(sym_map)
        if not sector_rets:
            return signals

        # Rank sectors by momentum, pick top N
        ranked_sectors = sorted(sector_rets.items(), key=lambda x: x[1], reverse=True)
        top_sectors = [
            s for s, _ in ranked_sectors[: self.top_sectors] if sector_rets.get(s, 0) > 0
        ]

        capacity = max(0, (self.top_sectors * self.stocks_per_sector) - len(self.positions))
        if capacity <= 0:
            return signals

        for sector_etf in top_sectors:
            if capacity <= 0:
                break
            constituents = _SECTOR_CONSTITUENTS.get(sector_etf, [])
            # Rank constituents within the sector by individual 20d momentum
            ranked_stocks = []
            for sym in constituents:
                if sym in self.positions:
                    continue  # already holding
                if sym not in sym_map:
                    continue
                ret20 = sym_map[sym].iloc[-1].get("returns_20d", None)
                if ret20 is None or pd.isna(ret20):
                    continue
                ranked_stocks.append((sym, float(ret20)))
            ranked_stocks.sort(key=lambda x: x[1], reverse=True)

            for sym, sym_ret in ranked_stocks[: self.stocks_per_sector]:
                if capacity <= 0:
                    break
                sym_data = sym_map[sym]
                price = float(sym_data.iloc[-1]["close"])
                atr = sym_data.iloc[-1].get("atr_20", None)
                if atr is not None and pd.isna(atr):
                    atr = None
                shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.08)
                if shares <= 0:
                    continue
                sector_ret = sector_rets[sector_etf]
                confidence = min(0.85, 0.55 + sector_ret * 2)
                signals.append(
                    {
                        "symbol": sym,
                        "action": "BUY",
                        "shares": shares,
                        "price": price,
                        "value": shares * price,
                        "confidence": confidence,
                        "reasoning": (
                            f"Sector rotation: {sector_etf} rank #{ranked_sectors.index((sector_etf, sector_ret)) + 1}"
                            f" ({sector_ret:+.1%} 20d), {sym} 20d ret {sym_ret:+.1%}"
                        ),
                        "atr": atr,
                        "asof_date": latest_date,
                    }
                )
                capacity -= 1

        return signals

    def get_description(self) -> str:
        return (
            f"Sector rotation: top {self.top_sectors} sectors by {self.sector_lookback}d momentum, "
            f"{self.stocks_per_sector} stock(s) per sector"
        )
