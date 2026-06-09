#!/usr/bin/env python3
"""
Entry-point orchestrator for the multi-strategy trading system.

The MultiStrategyRunner class lives in execution_engine.py.  This module
contains only the top-level main() function so the class file stays focused
on trading logic and this module handles program lifecycle (arg parsing,
error handling, exit codes).

Invoked via: python3 src/core/execution_engine.py  (which imports this)
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime

from src.core.execution_engine import MultiStrategyRunner
from src.monitoring.artifact_writer import DailyArtifactWriter, create_artifact_data

logger = logging.getLogger(__name__)


def main():
    """Main execution"""
    start_time = time.time()
    print("=" * 80)
    print("MULTI-STRATEGY TRADING SYSTEM")
    print("=" * 80)

    runner = None

    try:
        runner = MultiStrategyRunner()

        # Activate in-house error tracker immediately after the runner is up.
        # sys.excepthook is now pointed at our handler: any unhandled exception
        # from this point forward is persisted to error_log and emailed.
        from src.utils.error_tracker import init_error_tracker

        init_error_tracker(runner.db, runner.email_notifier)

        runner._set_run_stage("LOAD_DATA", "RUNNING")

        # Load market data with validation
        print("\n📊 Loading and validating market data...")
        market_data = runner.load_market_data()

        if market_data is None:
            error_msg = "Failed to load market data"
            logger.error(error_msg)
            runner._set_run_stage("LOAD_DATA", "FAILED", error_message=error_msg)
            if runner:
                runner.email_notifier.send_error_alert(error_msg, "\n".join(runner.errors))
            sys.exit(1)
        runner._set_run_stage("LOAD_DATA", "SUCCESS")

        signals, pnl_metrics = runner.execute_pipeline(market_data)
        slo_metrics = runner.emit_slo_metrics(start_time, signals, pnl_metrics)

        print("\n" + "=" * 80)
        if runner.kill_switch.is_killed:
            print("🛑 KILL SWITCH HALTED - 0 trades executed")
        else:
            print(f"✅ EXECUTION COMPLETE - {len(signals)} trades executed")
        print("=" * 80)

        # Don't overwrite HALTED status with SUCCESS — the kill switch already set it.
        if not runner.kill_switch.is_killed:
            runner._set_run_stage(
                "EXECUTION_COMPLETE",
                "SUCCESS",
                metadata={"trades_executed": len(signals), "slo": slo_metrics},
            )

        # Send email summary
        positions_data: list = []
        try:
            positions = runner.trading_client.get_all_positions()

            # Enrich broker positions with days_held from DB (F3)
            db_positions = {p["symbol"]: p for p in runner.db.get_positions()}
            today = datetime.now().date()
            positions_data = []
            for p in positions:
                db_pos = db_positions.get(p.symbol, {})
                entry_date_str = db_pos.get("entry_date", "") or ""
                days_held = None
                if entry_date_str:
                    try:
                        ed = datetime.strptime(entry_date_str[:10], "%Y-%m-%d").date()
                        days_held = (today - ed).days
                    except ValueError:
                        pass
                positions_data.append(
                    {
                        "symbol": p.symbol,
                        "shares": float(p.qty),
                        "entry_price": float(p.avg_entry_price),
                        "current_price": float(p.current_price),
                        "days_held": days_held,
                        "strategy_name": db_pos.get("strategy_name", ""),
                    }
                )

            logger.info(
                "Skipping runtime notifier daily summary; "
                "digest delivery is unified via scripts/generate_daily_email.py"
            )
        except Exception as e:
            logger.error(f"Failed to send email summary: {e}")

        try:
            runner._set_run_stage("ARTIFACTS", "RUNNING")
            writer = DailyArtifactWriter()
            latest_date = market_data.index.max()
            data_freshness_hours = (datetime.now() - latest_date).total_seconds() / 3600
            data_freshness = f"{data_freshness_hours:.1f}h old"
            regime = runner.regime_detector.get_status(market_data)
            warnings = []
            if runner.pending_orders:
                warnings.append(f"{len(runner.pending_orders)} orders pending confirmation")
            portfolio_heat = 0.0
            if runner.portfolio_value > 0:
                total_exposure = sum(pos["shares"] * pos["current_price"] for pos in positions_data)
                portfolio_heat = (total_exposure / runner.portfolio_value) * 100

            # Paper trading validation: write daily snapshot
            try:
                import json as _json

                _alloc_json = (
                    _json.dumps(
                        {
                            str(s.strategy_id): round(getattr(s, "capital", 0), 2)
                            for s in runner.strategies_cache
                            if hasattr(s, "capital")
                        }
                    )
                    if hasattr(runner, "strategies_cache")
                    else None
                )
                runner.db.log_daily_snapshot(
                    run_id=runner.run_id,
                    portfolio_value=runner.portfolio_value,
                    cash=runner.cash_available,
                    positions_value=total_exposure,
                    heat_pct=portfolio_heat,
                    vix=regime.get("vix"),
                    regime=f"{regime.get('volatility_regime','?')}/{regime.get('trend_regime','?')}",
                    allocation_json=_alloc_json,
                )
                logger.info("Daily portfolio snapshot recorded")
            except Exception as _snap_exc:
                logger.warning("log_daily_snapshot failed: %s", _snap_exc)

            placed_orders = [
                {
                    "symbol": trade["symbol"],
                    "side": trade["action"],
                    "qty": trade["shares"],
                    "price": trade["price"],
                }
                for trade in runner.executed_trades
            ]

            def _to_artifact_fill(trade: dict) -> dict:
                # confirmed_fills entries are raw trade dicts (action/shares)
                # but artifact_writer expects side/qty. Normalize either shape.
                return {
                    "symbol": trade.get("symbol"),
                    "side": trade.get("side") or trade.get("action") or "N/A",
                    "qty": trade.get("qty") or trade.get("shares") or 0,
                    "price": trade.get("price") or trade.get("exec_price") or 0,
                }

            fallback_fills = [_to_artifact_fill(t) for t in runner.executed_trades]
            confirmed_fills_normalized = [
                _to_artifact_fill(t) for t in (runner.confirmed_fills or [])
            ]
            open_positions = [
                {
                    "symbol": pos["symbol"],
                    "qty": pos["shares"],
                    "avg_price": pos["entry_price"],
                    "market_value": pos["shares"] * pos["current_price"],
                    "unrealized_pl": (pos["current_price"] - pos["entry_price"]) * pos["shares"],
                    "exposure_pct": (
                        pos["shares"] * pos["current_price"] / runner.portfolio_value * 100
                    )
                    if runner.portfolio_value > 0
                    else 0,
                }
                for pos in positions_data
            ]

            artifact = create_artifact_data(
                vix=regime.get("vix", 0),
                regime_classification=regime.get("volatility_regime", "UNKNOWN"),
                raw_signals=runner.raw_signals_by_strategy,
                rejected_signals=runner.rejected_signals,
                executed_signals=runner.executed_signals,
                placed_orders=placed_orders,
                filled_orders=confirmed_fills_normalized or fallback_fills,
                rejected_orders=runner.rejected_orders,
                portfolio_heat=portfolio_heat,
                daily_pnl=pnl_metrics["daily_pnl"],
                cumulative_pnl=pnl_metrics["cumulative_pnl"],
                drawdown=pnl_metrics["drawdown"],
                max_drawdown=pnl_metrics["max_drawdown"],
                circuit_breaker_state="ACTIVE"
                if runner.portfolio_risk.trading_halted
                else "INACTIVE",
                open_positions=open_positions,
                runtime_seconds=time.time() - start_time,
                data_freshness=data_freshness,
                errors=runner.errors,
                warnings=warnings,
                reconciliation_status=runner.reconciliation_status,
                portfolio_value=runner.portfolio_value,
                cash=runner.cash_available,
            )
            artifact["system_health"][
                "reconciliation_discrepancies"
            ] = runner.reconciliation_discrepancies
            artifact["system_health"]["slo_metrics"] = slo_metrics
            artifact["system_health"]["alpha_vantage_usage"] = runner.alpha_vantage_usage
            writer.write_daily_artifact(datetime.now().strftime("%Y-%m-%d"), artifact)
            runner._set_run_stage("ARTIFACTS", "SUCCESS")
        except Exception as e:
            logger.error(f"Failed to write daily artifact: {e}")
            runner._set_run_stage("ARTIFACTS", "FAILED", error_message=str(e))

        if runner.kill_switch.is_killed:
            logger.info("Multi-strategy execution completed (halted by kill switch)")
        else:
            logger.info("Multi-strategy execution completed successfully")
            runner._set_run_stage("COMPLETE", "SUCCESS", completed=True)

    except Exception as e:
        import traceback as _tb

        error_msg = f"Fatal error: {e}"
        stack = _tb.format_exc()
        logger.error(error_msg, exc_info=True)
        print(f"\n❌ FATAL ERROR: {e}")
        if runner:
            runner._set_run_stage("FAILED", "FAILED", error_message=error_msg, completed=True)

        # Route through in-house error tracker (persists + emails styled alert).
        # Falls back to the plain send_error_alert if tracker not yet initialised.
        try:
            from src.utils.error_tracker import capture as _capture

            _capture(
                error_type=type(e).__name__,
                message=str(e),
                stack_trace=stack,
                context={"run_id": getattr(runner, "run_id", "UNKNOWN")} if runner else None,
            )
        except Exception:  # nosec B110
            # Tracker failed — try raw email as last resort
            if runner:
                try:
                    runner.email_notifier.send_error_alert(error_msg, stack)
                except Exception:  # nosec B110
                    pass

        sys.exit(1)
