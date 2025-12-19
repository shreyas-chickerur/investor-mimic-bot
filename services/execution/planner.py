from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Dict, Tuple

from services.execution.models import TradeOrder, TradePlan


@dataclass(frozen=True)
class TradePlannerConfig:
    share_increment: Decimal = Decimal("0.0001")
    min_trade_notional: Decimal = Decimal("10")


class TradePlanner:
    def __init__(self, cfg: TradePlannerConfig | None = None):
        self.cfg = cfg or TradePlannerConfig()

    def generate_buy_plan(
        self,
        *,
        target_weights: Dict[str, Decimal],
        prices: Dict[str, Decimal],
        current_positions: Dict[str, Decimal],
        total_equity: Decimal,
        limit_offset_bps: int = 10,
    ) -> TradePlan:
        orders = []
        skipped = []

        if total_equity <= 0:
            return TradePlan(
                created_at=self._now(),
                total_equity=total_equity,
                orders=[],
                skipped=list(target_weights.keys()),
            )

        for sym, w in target_weights.items():
            if not sym or sym.upper() == "CASH":
                continue
            if w is None or w <= 0:
                continue

            px = prices.get(sym)
            if px is None or px <= 0:
                skipped.append(sym)
                continue

            cur_qty = current_positions.get(sym, Decimal("0"))
            cur_val = cur_qty * px
            tgt_val = w * total_equity
            delta_val = tgt_val - cur_val

            if delta_val <= self.cfg.min_trade_notional:
                continue

            raw_qty = delta_val / px
            qty = self._round_down(raw_qty, self.cfg.share_increment)
            if qty <= 0:
                continue

            notional = (qty * px).quantize(Decimal("0.01"))
            if notional < self.cfg.min_trade_notional:
                continue

            limit_mult = Decimal("1") + (Decimal(limit_offset_bps) / Decimal("10000"))
            limit_price = (px * limit_mult).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            if limit_price <= 0:
                skipped.append(sym)
                continue

            orders.append(
                TradeOrder(
                    symbol=sym,
                    side="buy",
                    qty=qty,
                    limit_price=limit_price,
                    notional=notional,
                )
            )

        return TradePlan(
            created_at=self._now(), total_equity=total_equity, orders=orders, skipped=skipped
        )

    def _round_down(self, value: Decimal, increment: Decimal) -> Decimal:
        if increment <= 0:
            return value
        q = (value / increment).quantize(Decimal("1"), rounding=ROUND_DOWN)
        return q * increment

    def _now(self):
        from datetime import datetime

        return datetime.utcnow()
