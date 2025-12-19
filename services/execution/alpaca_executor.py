from __future__ import annotations

# Standard library imports
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

# Third-party imports
from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, OrderStatus, OrderType, TimeInForce
from alpaca.trading.models import Order
from alpaca.trading.requests import LimitOrderRequest

from services.execution.models import TradeOrder, TradePlan


@dataclass(frozen=True)
class AlpacaExecutionConfig:
    require_market_open: bool = True
    poll_interval_seconds: float = 2.0
    fill_timeout_seconds: float = 90.0
    max_retries: int = 3
    kill_switch_env: str = "TRADING_KILL_SWITCH"
    kill_switch_file: str = "data/trading_kill_switch"


class AlpacaExecutionService:
    def __init__(
        self,
        trading: TradingClient,
        *,
        cfg: AlpacaExecutionConfig | None = None,
    ):
        self.trading = trading
        self.cfg = cfg or AlpacaExecutionConfig()

    @classmethod
    def from_env(cls, *, paper: bool) -> "AlpacaExecutionService":
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            raise RuntimeError("Missing ALPACA_API_KEY/ALPACA_SECRET_KEY")
        trading = TradingClient(api_key, secret_key, paper=paper)
        return cls(trading)

    def is_market_open(self) -> bool:
        clock = self.trading.get_clock()
        return bool(getattr(clock, "is_open", False))

    def kill_switch_active(self) -> bool:
        v = os.getenv(self.cfg.kill_switch_env)
        if v and v.strip().lower() in {"1", "true", "yes", "y", "on"}:
            return True
        try:
            return os.path.exists(self.cfg.kill_switch_file)
        except Exception:
            return False

    def cancel_all_open_orders(self) -> None:
        try:
            self.trading.cancel_orders()
        except Exception:
            return

    def place_limit_buy_orders(
        self,
        plan: TradePlan,
        *,
        max_orders: int = 50,
        confirm_market_open: bool = True,
    ) -> List[Dict[str, str]]:
        if self.kill_switch_active():
            raise RuntimeError("Kill switch active")

        if confirm_market_open and self.cfg.require_market_open and not self.is_market_open():
            raise RuntimeError("Market is closed")

        orders = [o for o in plan.orders if o.side == "buy"]
        if len(orders) > max_orders:
            raise RuntimeError(f"Refusing to place {len(orders)} orders > max_orders={max_orders}")

        results: List[Dict[str, str]] = []
        for o in orders:
            if self.kill_switch_active():
                self.cancel_all_open_orders()
                raise RuntimeError("Kill switch active")

            order = self._submit_with_retry(o)
            results.append(
                {
                    "symbol": o.symbol,
                    "id": str(getattr(order, "id", "")),
                    "status": str(getattr(order, "status", "")),
                }
            )

        return results

    def _submit_with_retry(self, o: TradeOrder) -> Order:
        last_err: Optional[Exception] = None
        limit_price = o.limit_price

        for attempt in range(1, self.cfg.max_retries + 1):
            if self.kill_switch_active():
                raise RuntimeError("Kill switch active")

            try:
                submitted = self._submit_limit_buy(
                    symbol=o.symbol, qty=o.qty, limit_price=limit_price
                )
                order_id = str(getattr(submitted, "id", ""))

                filled = self._wait_for_fill(order_id)
                if filled is not None:
                    return filled

                self._cancel(order_id)
                limit_price = (limit_price * Decimal("1.002")).quantize(Decimal("0.01"))

            except Exception as e:
                last_err = e
                time.sleep(min(2.0 * attempt, 10.0))
                continue

        raise RuntimeError(f"Failed to place/fill limit order for {o.symbol}: {last_err}")

    def _submit_limit_buy(self, *, symbol: str, qty: Decimal, limit_price: Decimal) -> Order:
        req = LimitOrderRequest(
            symbol=symbol,
            qty=float(qty),
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            time_in_force=TimeInForce.DAY,
            limit_price=float(limit_price),
        )
        return self.trading.submit_order(order_data=req)

    def _cancel(self, order_id: str) -> None:
        try:
            self.trading.cancel_order_by_id(order_id)
        except Exception:
            return

    def _wait_for_fill(self, order_id: str) -> Optional[Order]:
        start = time.time()
        while True:
            if self.kill_switch_active():
                self._cancel(order_id)
                return None

            o = self.trading.get_order_by_id(order_id)
            status = getattr(o, "status", None)
            if status in {OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED}:
                return o
            if status in {OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED}:
                return None

            if (time.time() - start) >= float(self.cfg.fill_timeout_seconds):
                return None

            time.sleep(float(self.cfg.poll_interval_seconds))
