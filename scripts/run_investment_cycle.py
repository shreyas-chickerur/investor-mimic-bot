#!/usr/bin/env python3
"""
Semi-automated investment cycle for the Investor Mimic Bot.

This script implements a deposit-driven investment workflow that:
1. Checks for new deposits in the Alpaca account
2. Calculates the available investment amount based on risk controls
3. Generates a proposed trade plan
4. Optionally executes the trades after manual confirmation
5. Logs all actions for ML training and auditing
"""
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from config.risk_controls import RiskControls, default_risk_controls  # noqa: E402
from services.funding.calculator import FundingCalculator, FundingRule  # noqa: E402
from services.funding.types import InvestmentDecision  # noqa: E402
from utils.alerting import AlertManager, alert_manager  # noqa: E402
from utils.logging_config import setup_logger  # noqa: E402

# Configure logging
logger = setup_logger(__name__, "investment_cycle.log")


# Initialize Alpaca client
def get_alpaca_client():
    """Initialize and return Alpaca trading client"""
    return TradingClient(
        os.getenv("ALPACA_API_KEY"),
        os.getenv("ALPACA_SECRET_KEY"),
        paper=True,  # Use paper trading by default
    )


class InvestmentCycle:
    """Manages the investment cycle from funding to execution"""

    def __init__(self, risk_controls: Optional[RiskControls] = None):
        """Initialize with risk controls"""
        self.risk_controls = risk_controls or default_risk_controls
        self.alpaca = get_alpaca_client()
        self.funding_calc = FundingCalculator()
        self.last_processed_deposit = None

    async def check_new_deposits(self) -> Optional[Decimal]:
        """Check for new deposits in the Alpaca account"""
        try:
            # Get account information (result not used but kept for potential future use)
            _ = self.alpaca.get_account()

            # Get recent transfers (deposits)
            transfers = self.alpaca.get_transfers(
                direction="inbound",
                status="COMPLETE",
                after=datetime.utcnow() - timedelta(days=7),  # Last 7 days
            )

            if not transfers:
                logger.info("No recent deposits found")
                return None

            # Get the most recent deposit
            latest_deposit = max(transfers, key=lambda x: x.created_at)

            # Check if we've already processed this deposit
            if self.last_processed_deposit == latest_deposit.id:
                logger.info("No new deposits since last check")
                return None

            self.last_processed_deposit = latest_deposit.id
            deposit_amount = Decimal(str(latest_deposit.amount))

            logger.info(f"Found new deposit: ${deposit_amount:,.2f}")
            return deposit_amount

        except Exception as e:
            logger.error(f"Error checking deposits: {e}", exc_info=True)
            await alert_manager.alert(
                "Failed to check for deposits", level="error", data={"error": str(e)}
            )
            return None

    async def calculate_investment_amount(self, deposit_amount: Decimal) -> InvestmentDecision:
        """Calculate how much to invest based on risk controls and deposit amount"""
        try:
            # Create funding rules from risk controls
            funding_rules = FundingRule(
                allocation_percent=Decimal(str(self.risk_controls.allocation_percent)),
                min_investment=self.risk_controls.min_investment,
                cash_buffer=self.risk_controls.cash_buffer,
                round_to_nearest=self.risk_controls.round_to_nearest,
            )

            # Calculate investment amount using just the deposit amount
            # We're not using the full account balance to avoid investing the entire $100k
            decision = self.funding_calc.calculate_investment(
                paycheck_amount=deposit_amount,
                current_cash_balance=deposit_amount,  # Treat deposit as the available cash
                rules=funding_rules,
            )

            logger.info(
                f"Investment decision: ${decision.investment_amount:,.2f} to invest "
                f"(from ${deposit_amount:,.2f} deposit)"
            )

            return decision

        except Exception as e:
            logger.error(f"Error calculating investment amount: {e}", exc_info=True)
            await alert_manager.alert(
                "Failed to calculate investment amount",
                level="error",
                data={"error": str(e), "deposit_amount": str(deposit_amount)},
            )
            raise

    async def generate_trade_plan(self, investment_amount: Decimal) -> List[Dict]:
        """
        Generate a proposed trade plan based on available funds and current portfolio.
        This is a placeholder - implement your actual strategy here.
        """
        try:
            # This is a simplified example - replace with your actual strategy
            # that determines which assets to buy based on your investment thesis

            # Get current positions (result not used but kept for potential future use)
            _ = self.alpaca.get_all_positions()

            # Example: Distribute funds across top 5 positions with smaller allocations
            # Using smaller allocations since we're working with a $1000 deposit
            target_positions = [
                {"symbol": "VTI", "allocation": 0.40},  # 40% to VTI
                {"symbol": "VXUS", "allocation": 0.30},  # 30% to VXUS
                {"symbol": "BND", "allocation": 0.20},  # 20% to BND
                {"symbol": "GLD", "allocation": 0.10},  # 10% to GLD
                # Remaining 0% kept as cash
            ]

            # Filter out positions with 0 allocation
            target_positions = [p for p in target_positions if p["allocation"] > 0]

            # Calculate dollar amounts for each position
            trade_plan = []
            for pos in target_positions:
                amount = (investment_amount * Decimal(str(pos["allocation"]))).quantize(
                    Decimal("0.01")
                )
                trade_plan.append(
                    {
                        "symbol": pos["symbol"],
                        "side": "BUY",
                        "amount": float(amount),
                        "allocation_pct": float(pos["allocation"] * 100),
                    }
                )

            logger.info("Generated trade plan: %s", json.dumps(trade_plan, indent=2))
            return trade_plan

        except Exception as e:
            logger.error(f"Error generating trade plan: {e}", exc_info=True)
            await alert_manager.alert(
                "Failed to generate trade plan",
                level="error",
                data={"error": str(e), "investment_amount": str(investment_amount)},
            )
            raise

    async def execute_trades(self, trade_plan: List[Dict]) -> Dict:
        """Execute the trades in the trade plan"""
        if not trade_plan:
            logger.warning("No trades to execute")
            return {"status": "skipped", "message": "No trades to execute"}

        results = {
            "total_orders": 0,
            "successful_orders": 0,
            "failed_orders": 0,
            "order_details": [],
        }

        try:
            for trade in trade_plan:
                if trade["symbol"] == "CASH":
                    logger.info("Skipping CASH allocation")
                    continue

                try:
                    # Prepare market order - use notional (dollar amount) instead of qty
                    order_data = MarketOrderRequest(
                        symbol=trade["symbol"],
                        notional=float(trade["amount"]),  # Dollar amount to invest
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY,
                    )

                    # Submit order
                    if not self.risk_controls.trading_enabled:
                        logger.info(
                            "[DRY RUN] Would submit order: %s",
                            order_data
                        )
                        status = "dry_run"
                        order_id = "dry_run_" + str(uuid.uuid4())
                    else:
                        order = self.alpaca.submit_order(order_data)
                        status = order.status
                        order_id = order.id

                    # Record result
                    result = {
                        "symbol": trade["symbol"],
                        "amount": trade["amount"],
                        "status": status,
                        "order_id": order_id,
                        "error": None,
                    }
                    results["successful_orders"] += 1

                except Exception as e:
                    logger.error(
                        f"Error submitting order for {trade['symbol']}: {e}",
                        exc_info=True
                    )
                    log_method = getattr(logger, "error", logger.info)
                    log_data = {
                        "alert": True,
                        "level": "error",
                        "data": {"error": str(e), "symbol": trade["symbol"]},
                    }
                    log_method(
                        "Error submitting order for %s",
                        trade["symbol"],
                        extra={"data": log_data},
                    )

                    # Log to alert history
                    self._log_alert(
                        "error",
                        "Error submitting order",
                        {"error": str(e), "symbol": trade["symbol"]},
                    )

                    result = {
                        "symbol": trade["symbol"],
                        "amount": trade["amount"],
                        "status": "failed",
                        "order_id": None,
                        "error": str(e),
                    }
                    results["failed_orders"] += 1

                results["order_details"].append(result)
                results["total_orders"] += 1

            # Log and alert on results
            if results["failed_orders"] > 0:
                await alert_manager.alert(
                    "Some trades failed to execute",
                    level="warning" if results["successful_orders"] > 0 else "error",
                    data=results,
                )
            else:
                await alert_manager.alert(
                    "All trades executed successfully", level="info", data=results
                )

            return results

        except Exception as e:
            logger.error(f"Unexpected error executing trades: {e}", exc_info=True)
            await alert_manager.alert(
                "Unexpected error executing trades", level="error", data={"error": str(e)}
            )
            raise

    async def run_cycle(self, manual_deposit_amount: Decimal = None) -> Dict:
        """Run a complete investment cycle"""
        cycle_id = str(uuid.uuid4())
        logger.info(f"Starting investment cycle {cycle_id}")

        try:
            # Check for new deposits or use manual amount
            if manual_deposit_amount is not None:
                deposit_amount = Decimal(str(manual_deposit_amount))
                logger.info(f"Using manual deposit amount: ${deposit_amount:,.2f}")
            else:
                deposit_amount = await self.check_new_deposits()
                if deposit_amount is None:
                    return {"status": "no_deposits", "message": "No new deposits found"}

            # Calculate investment amount
            decision = await self.calculate_investment_amount(deposit_amount)

            if decision.investment_amount <= 0:
                logger.info("No funds available for investment after applying rules")
                return {
                    "status": "no_investment",
                    "message": "No funds available for investment after applying rules",
                    "decision": decision.dict(),
                }

            # Generate trade plan
            trade_plan = await self.generate_trade_plan(decision.investment_amount)

            # If in manual confirmation mode, display plan and wait for approval
            if self.risk_controls.require_manual_confirmation:
                print("\n" + "=" * 50)
                print("INVESTMENT PLAN")
                print("=" * 50)
                print(f"Available to invest: ${decision.investment_amount:,.2f}")
                print("\nProposed trades:")
                for trade in trade_plan:
                    print(
                        f"  - {trade['symbol']}: ${trade['amount']:,.2f} ({trade['allocation_pct']:.1f}%)"
                    )

                if not self.risk_controls.trading_enabled:
                    print("\nWARNING: Trading is currently disabled in risk controls")

                print("\nOptions:")
                print("  1. Execute trades")
                print("  2. Skip this cycle")
                print("  3. Abort and exit")

                choice = input("\nEnter your choice (1-3): ").strip()

                if choice == "3":
                    logger.info("Investment cycle aborted by user")
                    return {"status": "aborted", "message": "User aborted the investment cycle"}
                elif choice != "1":
                    logger.info("Investment cycle skipped by user")
                    return {"status": "skipped", "message": "User skipped the investment cycle"}

            # Execute trades
            execution_results = await self.execute_trades(trade_plan)

            # Log cycle completion
            logger.info(f"Completed investment cycle {cycle_id}")

            # Convert decision to dict with string values for JSON serialization
            decision_dict = {
                "investment_amount": str(decision.investment_amount),
                "remaining_cash": str(decision.remaining_cash),
                "deposit_amount": str(deposit_amount),
            }

            # Convert execution results to be JSON serializable
            serialized_results = {
                "total_orders": execution_results.get("total_orders", 0),
                "successful_orders": execution_results.get("successful_orders", 0),
                "failed_orders": execution_results.get("failed_orders", 0),
                "order_details": [
                    {
                        k: (
                            str(v)
                            if hasattr(v, "__str__") and not isinstance(v, (str, int, float, bool))
                            else v
                        )
                        for k, v in order.items()
                    }
                    for order in execution_results.get("order_details", [])
                ],
            }

            return {
                "status": "completed",
                "cycle_id": str(cycle_id),  # Convert UUID to string
                "deposit_amount": str(deposit_amount),
                "decision": decision_dict,
                "trade_plan": trade_plan,
                "execution_results": serialized_results,
            }

        except Exception as e:
            logger.error(f"Error in investment cycle {cycle_id}: {e}", exc_info=True)
            await alert_manager.alert(
                "Investment cycle failed",
                level="error",
                data={"cycle_id": cycle_id, "error": str(e)},
            )
            return {"status": "error", "cycle_id": cycle_id, "error": str(e)}


async def main():
    """Main entry point for the investment cycle script"""
    try:
        # Initialize investment cycle with default risk controls
        investment_cycle = InvestmentCycle()

        # Check for manual deposit amount from command line
        manual_deposit_amount = None
        if len(sys.argv) > 1:
            try:
                manual_deposit_amount = Decimal(sys.argv[1])
                logger.info(
                    f"Using manual deposit amount from command line: ${manual_deposit_amount:,.2f}"
                )
            except (ValueError, IndexError):
                logger.warning(f"Invalid manual deposit amount: {sys.argv[1]}")
                print(f"Usage: {sys.argv[0]} [deposit_amount]")
                return 1

        # Run the investment cycle
        result = await investment_cycle.run_cycle(manual_deposit_amount)

        # Print summary
        print("\n" + "=" * 50)
        print("INVESTMENT CYCLE COMPLETE")
        print("=" * 50)
        print(f"Status: {result.get('status', 'unknown')}")

        if "decision" in result:
            # Print results
            print("\nInvestment Decision:")
            print(f"  - Deposit Amount: ${float(result['decision'].get('deposit_amount', 0)):,.2f}")
            print(
                f"  - Investment Amount: ${float(result['decision'].get('investment_amount', 0)):,.2f}"
            )
            print(f"  - Remaining Cash: ${float(result['decision'].get('remaining_cash', 0)):,.2f}")

        if "execution_results" in result:
            exec_results = result["execution_results"]
            print(f"\nExecution Results:")
            print(f"  - Successful Orders: {exec_results.get('successful_orders', 0)}")
            print(f"  - Failed Orders: {exec_results.get('failed_orders', 0)}")

        print("\nCheck the logs for more details.")

        return 0

    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)
        await alert_manager.alert(
            "Fatal error in investment cycle", level="critical", data={"error": str(e)}
        )
        return 1


if __name__ == "__main__":
    # Run the async main function
    sys.exit(asyncio.run(main()))
