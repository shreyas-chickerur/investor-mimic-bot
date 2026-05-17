#!/usr/bin/env python3
"""
Intraday Stop-Loss Monitor (Improvement #10)

Subscribes to Alpaca's WebSocket price stream and checks open positions
against their ATR-based trailing stop levels in real time. When a stop is
hit intraday, submits a DAY market SELL immediately — rather than waiting
until the 4:15 PM EOD run — which can save significant loss on fast moves.

Usage (run as a daemon while market is open):
    python3 scripts/monitor_intraday_stops.py

Requires: ALPACA_API_KEY, ALPACA_SECRET_KEY in .env
          ALPACA_PAPER=true (or false for live)
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from alpaca.data.live import StockDataStream
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from src.core.database import TradingDatabase
from src.risk.stop_loss_manager import StopLossManager
from src.utils.config_loader import get_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/intraday_stops.log")],
)
logger = logging.getLogger(__name__)


class IntradayStopMonitor:
    """Subscribes to live price stream and fires stop-loss sells intraday."""

    def __init__(self):
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            raise ValueError("Missing Alpaca credentials")

        self.paper_mode = os.getenv("ALPACA_PAPER", "true").lower() == "true"
        self.trading_client = TradingClient(api_key, secret_key, paper=self.paper_mode)
        self.stream = StockDataStream(api_key, secret_key, feed="sip")

        config = get_config()
        self.db = TradingDatabase()
        self.stop_manager = StopLossManager(
            atr_multiplier=config.get("risk.stop_loss_atr_multiplier", 2.5),
            breakeven_atr=config.get("risk.trailing_breakeven_atr", 1.0),
            lock_atr=config.get("risk.trailing_lock_atr", 2.0),
        )
        self._fired_stops: set = set()  # prevent double-firing per session

    def _load_open_positions_and_stops(self) -> list[str]:
        """Load all open positions from DB and initialize their stop levels."""
        positions = self.db.get_all_open_positions()
        symbols = []
        for pos in positions:
            sym = pos["symbol"]
            entry_price = float(pos.get("avg_price") or 0)
            atr = float(pos.get("atr") or 0)
            if entry_price <= 0:
                continue
            if atr <= 0:
                atr = entry_price * 0.03  # 3% fallback
            self.stop_manager.set_stop_loss(sym, entry_price, atr)
            symbols.append(sym)
        logger.info("Monitoring %d symbols for intraday stops: %s", len(symbols), symbols)
        return symbols

    async def _on_bar(self, bar):
        """Callback for each 1-minute bar; update trailing stop and check for breach."""
        sym = bar.symbol
        price = float(bar.close)

        if sym in self._fired_stops:
            return

        # Update trailing stop
        atr = self.stop_manager.entry_atrs.get(sym, 0)
        if atr > 0:
            self.stop_manager.update_ratchet_stop(sym, price, atr)

        # Check if stop is breached
        if self.stop_manager.check_stop_loss(sym, price):
            stop_price = self.stop_manager.get_stop_price(sym)
            logger.warning(
                "INTRADAY STOP HIT: %s @ $%.2f (stop $%.2f) — submitting SELL",
                sym,
                price,
                stop_price,
            )
            await self._fire_stop_sell(sym, price)

    async def _fire_stop_sell(self, symbol: str, current_price: float):
        """Submit a DAY market sell for all shares of a position."""
        try:
            pos = self.trading_client.get_open_position(symbol)
            qty = abs(int(float(pos.qty)))
            if qty <= 0:
                logger.info("Intraday stop: %s already flat at broker", symbol)
                return

            order = self.trading_client.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )
            )
            self._fired_stops.add(symbol)
            self.stop_manager.remove_stop_loss(symbol)
            logger.info("Intraday SELL submitted: %s × %d (order %s)", symbol, qty, order.id)
        except Exception as exc:
            logger.error("Failed to fire intraday stop for %s: %s", symbol, exc)

    def run(self):
        """Start the WebSocket stream and block until interrupted."""
        symbols = self._load_open_positions_and_stops()
        if not symbols:
            logger.info("No open positions to monitor — exiting.")
            return

        for sym in symbols:
            self.stream.subscribe_bars(self._on_bar, sym)

        logger.info("Intraday stop monitor running (paper=%s) — Ctrl-C to stop", self.paper_mode)
        self.stream.run()


def main():
    Path("logs").mkdir(exist_ok=True)
    monitor = IntradayStopMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
