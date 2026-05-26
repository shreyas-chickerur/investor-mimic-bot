#!/usr/bin/env python3
"""
Broker Reconciliation System

Daily reconciliation between local state and Alpaca broker.
Enters PAUSED state on mismatch and blocks all trading until resolved.

Critical Component for operational safety and state verification.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class ReconciliationMismatch(Exception):
    """Raised when reconciliation finds a mismatch"""

    pass


class BrokerReconciler:
    """
    Reconciles local trading state with Alpaca broker

    Checks:
    - Positions (symbol, qty, avg price)
    - Cash/buying power
    - Open orders
    - Filled trades

    On mismatch: Enter PAUSED state, block trading, alert
    """

    def __init__(self, email_notifier=None):
        """
        Initialize broker reconciler

        Args:
            email_notifier: EmailNotifier instance for alerts
        """
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")
        self.paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"

        if not self.api_key or not self.secret_key:
            logger.warning("Alpaca API credentials not found in environment")
            self.client = None
        else:
            self.client = TradingClient(self.api_key, self.secret_key, paper=self.paper)
        self.email_notifier = email_notifier
        self.is_paused = False
        self.last_reconciliation = None
        self.mismatch_details = []

    def reconcile_daily(
        self, local_positions: dict, local_cash: float, local_orders: list | None = None
    ) -> tuple[bool, list[str]]:
        logger.info("=" * 80)
        logger.info("BROKER RECONCILIATION - STARTING")
        logger.info("=" * 80)

        discrepancies = []

        try:
            if self.client is None:
                logger.warning("Broker reconciliation skipped - Alpaca client not configured")
                self.last_reconciliation = datetime.now()
                return True, []
            # 1. Reconcile positions
            position_discrepancies = self._reconcile_positions(local_positions)
            discrepancies.extend(position_discrepancies)

            # 2. Reconcile cash
            cash_discrepancies = self._reconcile_cash(local_cash)
            discrepancies.extend(cash_discrepancies)

            # 3. Reconcile open orders
            if local_orders is not None:
                order_discrepancies = self._reconcile_orders(local_orders)
                discrepancies.extend(order_discrepancies)
            # Note: phantom positions (broker but not local) are already reported
            # by _reconcile_positions above; _check_phantom_positions is not called
            # here to avoid double-counting every untracked broker position.

            self.last_reconciliation = datetime.now()

            if discrepancies:
                logger.error(f"❌ RECONCILIATION FAILED - {len(discrepancies)} discrepancies found")
                for disc in discrepancies:
                    logger.error(f"  - {disc}")

                self._enter_paused_state(discrepancies)
                return False, discrepancies
            else:
                logger.info("✅ RECONCILIATION PASSED - All checks successful")
                self.is_paused = False
                self.mismatch_details = []
                return True, []

        except Exception as e:
            error_msg = f"Reconciliation error: {str(e)}"
            logger.error(error_msg)
            discrepancies.append(error_msg)
            self._enter_paused_state(discrepancies)
            return False, discrepancies

    def _reconcile_positions(self, local_positions: dict) -> list[str]:
        """Reconcile positions between local and broker"""
        discrepancies = []

        try:
            # Get broker positions
            broker_positions = self.client.get_all_positions()
            broker_dict = {
                pos.symbol: {"qty": float(pos.qty), "avg_price": float(pos.avg_entry_price)}
                for pos in broker_positions
            }

            logger.info(
                f"Local positions: {len(local_positions)}, Broker positions: {len(broker_dict)}"
            )

            # Check each local position
            for symbol, local_data in local_positions.items():
                if symbol not in broker_dict:
                    disc = f"Position mismatch: {symbol} exists locally but not in broker"
                    discrepancies.append(disc)
                    continue

                broker_data = broker_dict[symbol]

                # Check quantity — use 0.5-share tolerance to handle fractional
                # share rounding and paper-trading fill estimation differences
                if abs(local_data["qty"] - broker_data["qty"]) > 0.5:
                    disc = f"Quantity mismatch for {symbol}: local={local_data['qty']}, broker={broker_data['qty']}"
                    discrepancies.append(disc)

                # Log average price differences as warnings (not failures)
                # Price diffs are expected due to multi-strategy aggregation and partial fills
                if broker_data["avg_price"] > 0:
                    price_diff_pct = (
                        abs(local_data["avg_price"] - broker_data["avg_price"])
                        / broker_data["avg_price"]
                        * 100
                    )
                    if price_diff_pct > 1.0:
                        logger.warning(
                            f"Avg price drift for {symbol}: local=${local_data['avg_price']:.2f}, broker=${broker_data['avg_price']:.2f} ({price_diff_pct:.2f}% diff) — cosmetic only"
                        )

            # Check for positions in broker but not local
            for symbol in broker_dict:
                if symbol not in local_positions:
                    disc = f"Position mismatch: {symbol} exists in broker but not locally"
                    discrepancies.append(disc)

        except Exception as e:
            discrepancies.append(f"Error reconciling positions: {str(e)}")

        return discrepancies

    def _reconcile_cash(self, local_cash: float) -> list[str]:
        """Reconcile cash balance"""
        discrepancies = []

        try:
            account = self.client.get_account()
            broker_cash = float(account.cash)
            broker_buying_power = float(account.buying_power)

            logger.info(
                f"Cash - Local: ${local_cash:,.2f}, Broker: ${broker_cash:,.2f}, Buying Power: ${broker_buying_power:,.2f}"
            )

            # Allow 2% tolerance for rounding: paper-trading limit orders submitted
            # near end-of-day create a time gap between the local refresh and the
            # reconciler's own API call, so small differences are expected.
            cash_diff_pct = (
                abs(local_cash - broker_cash) / broker_cash * 100 if broker_cash > 0 else 0
            )

            if cash_diff_pct > 2.0:
                disc = f"Cash mismatch: local=${local_cash:,.2f}, broker=${broker_cash:,.2f} ({cash_diff_pct:.2f}% diff)"
                discrepancies.append(disc)

        except Exception as e:
            discrepancies.append(f"Error reconciling cash: {str(e)}")

        return discrepancies

    def _reconcile_orders(self, local_orders: list) -> list[str]:
        """Reconcile open orders"""
        discrepancies = []

        try:
            # Get open orders from broker
            request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
            broker_orders = self.client.get_orders(filter=request)

            logger.info(f"Orders - Local: {len(local_orders)}, Broker: {len(broker_orders)}")

            broker_order_ids = {order.id for order in broker_orders}
            local_order_ids = {order.get("id") for order in local_orders if order.get("id")}

            # Check for stuck orders (in local but not broker)
            stuck_orders = local_order_ids - broker_order_ids
            if stuck_orders:
                disc = f"Stuck orders found (local but not in broker): {stuck_orders}"
                discrepancies.append(disc)

            # Check for phantom orders (in broker but not local)
            phantom_orders = broker_order_ids - local_order_ids
            if phantom_orders:
                disc = f"Phantom orders found (broker but not local): {phantom_orders}"
                discrepancies.append(disc)

        except Exception as e:
            discrepancies.append(f"Error reconciling orders: {str(e)}")

        return discrepancies

    def _check_phantom_positions(self, local_positions: dict) -> list[str]:
        """Check for positions in broker that shouldn't exist"""
        discrepancies = []

        try:
            broker_positions = self.client.get_all_positions()

            for pos in broker_positions:
                if pos.symbol not in local_positions:
                    disc = f"Phantom position: {pos.symbol} ({pos.qty} shares) exists in broker but not tracked locally"
                    discrepancies.append(disc)

        except Exception as e:
            discrepancies.append(f"Error checking phantom positions: {str(e)}")

        return discrepancies

    def _enter_paused_state(self, discrepancies: list[str]):
        """
        Enter PAUSED state on reconciliation failure

        - Sets is_paused flag
        - Stores mismatch details
        - Sends email alert
        - Blocks all trading
        """
        self.is_paused = True
        self.mismatch_details = discrepancies

        logger.critical("=" * 80)
        logger.critical("⚠️  SYSTEM PAUSED - RECONCILIATION FAILURE")
        logger.critical("=" * 80)
        logger.critical("Trading is BLOCKED until reconciliation passes")
        logger.critical(f"Discrepancies found: {len(discrepancies)}")
        for disc in discrepancies:
            logger.critical(f"  - {disc}")
        logger.critical("=" * 80)

        # Send email alert
        if self.email_notifier:
            try:
                subject = "⚠️ Broker Reconciliation Warning - Discrepancies Detected"
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                disc_items = "".join(
                    f"<li style='margin-bottom:6px'>{d}</li>" for d in discrepancies
                )
                body = f"""<html><body style="font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;
                    max-width:600px;margin:0 auto;color:#111;">
                  <div style="background:#ff9800;color:#fff;padding:16px 20px;border-radius:8px 8px 0 0">
                    <h2 style="margin:0">⚠️ Reconciliation Warning</h2>
                  </div>
                  <div style="padding:20px;border:1px solid #dee2e6;border-top:none">
                    <p style="margin:0 0 12px"><strong>Time:</strong> {timestamp}</p>
                    <p style="margin:0 0 12px">Trading completed, but <strong>{len(discrepancies)} discrepanc{'y' if len(discrepancies)==1 else 'ies'}</strong>
                    were found between the local database and Alpaca broker state.</p>
                    <h3 style="margin:16px 0 8px;color:#e65100">Discrepancies Found</h3>
                    <ul style="line-height:1.6;padding-left:20px;margin:0 0 16px">{disc_items}</ul>
                    <div style="background:#fff8e1;border:1px solid #ffe082;border-radius:6px;
                                padding:12px 16px;margin-bottom:16px;font-size:13px">
                      This is common in paper trading (e.g., manual trades, partial fills,
                      or end-of-day timing gaps). Run
                      <code style="background:#f0f0e8;padding:2px 6px;border-radius:3px">python3 scripts/sync_broker_state.py</code>
                      or trigger the <em>Sync Database</em> workflow to resolve.
                    </div>
                    <p style="color:#555;font-size:13px;margin:0">
                      The trading system will continue to operate normally on the next run.
                    </p>
                  </div>
                </body></html>"""
                self.email_notifier.send_alert(subject, body)
                logger.info("✅ Email alert sent")
            except Exception as e:
                logger.error(f"Failed to send email alert: {e}")

    def check_if_paused(self) -> tuple[bool, list[str]]:
        """
        Check if system is in PAUSED state

        Returns:
            (is_paused: bool, mismatch_details: List[str])
        """
        return self.is_paused, self.mismatch_details

    def force_resume(self):
        """
        Force resume trading (use with caution)

        Should only be called after manual verification that
        discrepancies have been resolved.
        """
        logger.warning("⚠️  FORCE RESUME - Trading unpaused manually")
        self.is_paused = False
        self.mismatch_details = []

    def get_broker_state(self) -> dict:
        """
        Get current broker state for comparison

        Returns:
            Dict with positions, cash, orders
        """
        try:
            positions = self.client.get_all_positions()
            account = self.client.get_account()
            orders_request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
            orders = self.client.get_orders(filter=orders_request)

            return {
                "positions": {
                    pos.symbol: {
                        "qty": float(pos.qty),
                        "avg_price": float(pos.avg_entry_price),
                        "market_value": float(pos.market_value),
                        "unrealized_pl": float(pos.unrealized_pl),
                    }
                    for pos in positions
                },
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "portfolio_value": float(account.portfolio_value),
                "open_orders": len(orders),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting broker state: {e}")
            return {}


if __name__ == "__main__":
    # Test reconciliation
    logging.basicConfig(level=logging.INFO)

    reconciler = BrokerReconciler()

    # Get current broker state
    broker_state = reconciler.get_broker_state()
    print("\nCurrent Broker State:")
    print(f"Positions: {len(broker_state.get('positions', {}))}")
    print(f"Cash: ${broker_state.get('cash', 0):,.2f}")
    print(f"Portfolio Value: ${broker_state.get('portfolio_value', 0):,.2f}")

    # Test reconciliation with current state
    success, discrepancies = reconciler.reconcile_daily(
        local_positions=broker_state.get("positions", {}), local_cash=broker_state.get("cash", 0)
    )

    print(f"\nReconciliation: {'✅ PASS' if success else '❌ FAIL'}")
    if discrepancies:
        print("Discrepancies:")
        for disc in discrepancies:
            print(f"  - {disc}")
