#!/usr/bin/env python3
"""
Portfolio-Level Walk-Forward Backtesting Framework

Simulates the full trading pipeline:
  signals → correlation filter → risk limits → ATR sizing → costs → execute

Walk-forward windows: 2yr train / 6mo test / 6mo step
"""
from __future__ import annotations

import logging
from datetime import timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PortfolioBacktester:
    """Walk-forward portfolio backtester with full pipeline simulation."""

    def __init__(
        self,
        initial_capital: float = 100000,
        slippage_bps: float = 5.0,
        commission_per_share: float = 0.0,
        max_portfolio_heat: float = 0.50,
        max_daily_loss_pct: float = 0.05,
        stop_loss_atr_mult: float = 5.0,
        max_positions_per_strategy: int = 5,
        max_correlation: float = 0.80,
        min_hold_days: int = 2,
        cooldown_days: int = 10,
        min_buy_confidence: float = 0.60,
        max_daily_buys: int = 3,
        breakeven_atr: float | None = None,
        lock_atr: float | None = None,
    ):
        self.initial_capital = initial_capital
        self.slippage_bps = slippage_bps
        self.commission_per_share = commission_per_share
        self.max_portfolio_heat = max_portfolio_heat
        self.max_daily_loss_pct = max_daily_loss_pct
        self.stop_loss_atr_mult = stop_loss_atr_mult
        self.max_positions_per_strategy = max_positions_per_strategy
        self.max_correlation = max_correlation
        self.min_hold_days = min_hold_days
        self.cooldown_days = cooldown_days
        self.min_buy_confidence = min_buy_confidence
        self.max_daily_buys = max_daily_buys
        # Production ratchet (stop_loss_manager.update_ratchet_stop): None disables
        self.breakeven_atr = breakeven_atr
        self.lock_atr = lock_atr

    @classmethod
    def from_config(cls, config, initial_capital: float = 100000) -> PortfolioBacktester:
        """Production-parity backtester: gates and stops sourced from the SAME
        trading_config.yaml the live engine reads.

        The legacy defaults diverge from production in ways that invalidate
        evidence: a 0.60 confidence floor and 3-buys/day cap that production
        doesn't have, a 10-day re-entry cooldown, and a 5.0x static ATR stop
        vs production's 2.5x with breakeven/lock ratchet. Parity mode removes
        the synthetic gates and replicates the production stop geometry.
        """
        return cls(
            initial_capital=initial_capital,
            slippage_bps=float(config.get("execution.slippage_bps", 5.0)),
            commission_per_share=float(config.get("execution.commission_per_share", 0.0)),
            max_portfolio_heat=float(config.get("risk.max_portfolio_heat", 0.40)),
            max_daily_loss_pct=float(config.get("risk.max_daily_loss_pct", 0.05)),
            stop_loss_atr_mult=float(config.get("risk.stop_loss_atr_multiplier", 2.5)),
            cooldown_days=0,
            min_buy_confidence=0.0,
            max_daily_buys=10_000,  # production gates on funnel/risk, not a daily cap
            breakeven_atr=float(config.get("risk.trailing_breakeven_atr", 1.0)),
            lock_atr=float(config.get("risk.trailing_lock_atr", 2.0)),
        )

    # ------------------------------------------------------------------
    # Walk-forward driver
    # ------------------------------------------------------------------
    def run_walk_forward(
        self,
        market_data: pd.DataFrame,
        strategy_classes: list,
        train_days: int = 504,
        test_days: int = 126,
        step_days: int = 126,
    ) -> dict:
        """
        Run walk-forward backtest as a continuous simulation.

        Positions carry across windows. Only ML models retrain at
        window boundaries. No forced closes.

        Args:
            market_data: Full historical data (DatetimeIndex, 'symbol' column)
            strategy_classes: List of strategy *classes* (not instances)
            train_days / test_days / step_days: walk-forward params

        Returns:
            Dict with overall metrics, per-window metrics, equity curve
        """
        dates = sorted(market_data.index.unique())

        # Build window schedule
        windows = []
        wid = 0
        while True:
            train_start_idx = wid * step_days
            train_end_idx = train_start_idx + train_days
            test_end_idx = train_end_idx + test_days
            if test_end_idx > len(dates):
                break
            windows.append(
                {
                    "train_start": dates[train_start_idx],
                    "train_end": dates[train_end_idx - 1],
                    "test_start": dates[train_end_idx],
                    "test_end": dates[min(test_end_idx - 1, len(dates) - 1)],
                }
            )
            wid += 1

        if not windows:
            return {"error": "Not enough data for even one window"}

        # Continuous simulation state
        cash: float = self.initial_capital
        positions: dict = {}  # carried across windows
        stop_levels: dict = {}
        # OPG order queues: signals generated at day t's close fill at day
        # t+1's OPEN (production semantics — limit-on-open; a gap through the
        # limit leaves the order unfilled and it expires, like a real OPG).
        pending_buys: list = []
        pending_sells: list = []
        cooldowns = {}  # {symbol: last_sell_date} — prevent re-entry churn
        equity_curve = []
        all_trades = []
        window_results = []

        # Create strategy instances — each gets half of capital for sizing;
        # the portfolio heat limit (50%) prevents actual over-allocation.
        strategies = []
        for i, cls in enumerate(strategy_classes):
            strat = cls(
                strategy_id=i + 1,
                capital=self.initial_capital / 2,
            )
            strategies.append(strat)

        # Initial training on first window's train data
        first_train = market_data[
            (market_data.index >= windows[0]["train_start"])
            & (market_data.index <= windows[0]["train_end"])
        ]
        for strat in strategies:
            if hasattr(strat, "_train_model"):
                try:
                    strat._train_model(first_train)
                except Exception as e:
                    logger.warning(f"Training failed for {strat.name}: {e}")

        # Determine full test date range
        sim_start = windows[0]["test_start"]
        sim_end = windows[-1]["test_end"]
        sim_dates = [d for d in dates if sim_start <= d <= sim_end]

        # Track which window we're in for retraining
        current_window_idx = 0
        day_start_value = self.initial_capital

        for day_idx, date in enumerate(sim_dates):
            # -- Retrain at window boundaries --
            if (
                current_window_idx + 1 < len(windows)
                and date >= windows[current_window_idx + 1]["test_start"]
            ):
                # Record window result
                pos_val = self._mark_to_market(positions, market_data[market_data.index == date])
                pv = cash + pos_val
                window_results.append(
                    {
                        "window_id": current_window_idx + 1,
                        "train_period": (
                            f"{windows[current_window_idx]['train_start'].date()} to "
                            f"{windows[current_window_idx]['train_end'].date()}"
                        ),
                        "test_period": (
                            f"{windows[current_window_idx]['test_start'].date()} to "
                            f"{windows[current_window_idx]['test_end'].date()}"
                        ),
                        "final_value": pv,
                        "trades": [],  # trades tracked globally
                    }
                )

                current_window_idx += 1

                # Retrain ML strategies on new training data
                train_data = market_data[
                    (market_data.index >= windows[current_window_idx]["train_start"])
                    & (market_data.index <= windows[current_window_idx]["train_end"])
                ]
                for strat in strategies:
                    if hasattr(strat, "_train_model"):
                        try:
                            strat.is_trained = False
                            strat._train_model(train_data)
                        except Exception as e:
                            logger.warning(f"Retrain failed for {strat.name}: {e}")

                logger.info(
                    f"Window {current_window_idx + 1}: retrained, "
                    f"capital ${pv:,.0f}, {len(positions)} open positions"
                )

            day_data = market_data[market_data.index == date]
            if day_data.empty:
                continue

            # -- Mark-to-market --
            pos_value = self._mark_to_market(positions, day_data)
            portfolio_value = cash + pos_value

            # -- Daily loss circuit breaker --
            if day_idx == 0 or date != sim_dates[max(0, day_idx - 1)]:
                day_start_value = portfolio_value
            daily_pnl_pct = (
                (portfolio_value - day_start_value) / day_start_value if day_start_value > 0 else 0
            )
            if daily_pnl_pct < -self.max_daily_loss_pct:
                equity_curve.append(
                    self._snap(date, portfolio_value, cash, pos_value, len(positions))
                )
                continue

            # -- Fill yesterday's queued OPG orders at TODAY'S open --
            def _open_px(sym, day_data=day_data):  # bind loop var (B023)
                row = day_data[day_data["symbol"] == sym]
                if row.empty:
                    return None
                val = row.iloc[0].get("open") if "open" in row.columns else None
                if val is None or pd.isna(val):
                    val = row.iloc[0].get("close")
                return float(val) if val is not None and not pd.isna(val) else None

            for order in pending_sells:
                sym = order["symbol"]
                if sym not in positions:
                    continue
                open_px = _open_px(sym)
                if open_px is None:
                    continue  # no data today — OPG expires
                if open_px < order["signal_price"] * 0.99:
                    continue  # gapped below the sell limit — unfilled, position stays
                pos = positions[sym]
                req = float(order.get("shares") or 0)
                sell_shares = min(req, pos["shares"]) if req > 0 else pos["shares"]
                proceeds = self._sell_price(open_px, sell_shares)
                pnl = proceeds - pos["entry_price"] * sell_shares
                cash += proceeds
                all_trades.append(
                    {
                        "date": date,
                        "symbol": sym,
                        "action": "SELL",
                        "shares": sell_shares,
                        "price": open_px,
                        "pnl": pnl,
                        "reason": order.get("reason", ""),
                        "hold_days": (date - pos["entry_date"]).days,
                    }
                )
                remaining = pos["shares"] - sell_shares
                strat = pos.get("strategy_obj")
                if remaining > 0:
                    # Partial exit (50% tranche): position, stop, and entry
                    # price are preserved — previously the backtester dumped
                    # the WHOLE position on any SELL signal.
                    pos["shares"] = remaining
                    if strat:
                        strat.positions[sym] = remaining
                else:
                    positions.pop(sym)
                    stop_levels.pop(sym, None)
                    if strat:
                        strat.positions.pop(sym, None)
                        strat.entry_dates.pop(sym, None)
                    cooldowns[sym] = date
            pending_sells = []

            _fill_pos_value = self._mark_to_market(positions, day_data)
            _fill_portfolio = cash + _fill_pos_value
            current_exposure = sum(p["shares"] * p["entry_price"] for p in positions.values())
            for order in pending_buys:
                sym = order["symbol"]
                if sym in positions:
                    continue
                open_px = _open_px(sym)
                if open_px is None or open_px <= 0:
                    continue
                if open_px > order["signal_price"] * 1.01:
                    continue  # gapped above the buy limit — unfilled (expires)
                shares = order["shares"]
                cost = self._buy_cost(open_px, shares)
                if cost > cash:
                    continue
                new_exposure = current_exposure + cost
                if _fill_portfolio > 0 and new_exposure / _fill_portfolio > self.max_portfolio_heat:
                    continue
                exec_price = open_px * (1 + self.slippage_bps / 10000)
                cash -= cost
                current_exposure += cost
                atr = order.get("atr", 0) or 0
                positions[sym] = {
                    "shares": shares,
                    "entry_price": exec_price,
                    "entry_date": date,
                    "atr": atr,
                    "strategy_obj": order.get("strategy_obj"),
                }
                if atr > 0:
                    stop_levels[sym] = exec_price - self.stop_loss_atr_mult * atr
                all_trades.append(
                    {
                        "date": date,
                        "symbol": sym,
                        "action": "BUY",
                        "shares": shares,
                        "price": exec_price,
                        "pnl": 0,
                        "reason": order.get("reason", ""),
                        "hold_days": 0,
                    }
                )
                strat = order.get("strategy_obj")
                if strat:
                    strat.positions[sym] = shares
                    strat.entry_dates[sym] = date
            pending_buys = []

            # -- Check stop losses (respect min hold period) --
            for sym in list(positions.keys()):
                sym_row = day_data[day_data["symbol"] == sym]
                if sym_row.empty:
                    continue
                price = float(sym_row.iloc[0]["close"])
                days_held = (date - positions[sym]["entry_date"]).days
                # Production-parity ratchet (stop_loss_manager.update_ratchet_stop):
                # +breakeven_atr profit → stop to entry; +lock_atr → entry + 1 ATR,
                # then chandelier extends. Stops never move down.
                if (
                    self.breakeven_atr is not None
                    and sym in stop_levels
                    and positions[sym].get("atr", 0) > 0
                ):
                    entry = positions[sym]["entry_price"]
                    atr = positions[sym]["atr"]
                    open_profit = price - entry
                    new_stop = stop_levels[sym]
                    if self.lock_atr is not None and open_profit >= self.lock_atr * atr:
                        new_stop = max(new_stop, entry + atr)
                        new_stop = max(new_stop, price - self.stop_loss_atr_mult * atr)
                    elif open_profit >= self.breakeven_atr * atr:
                        new_stop = max(new_stop, entry)
                    stop_levels[sym] = new_stop
                if (
                    sym in stop_levels
                    and price <= stop_levels[sym]
                    and days_held >= self.min_hold_days
                ):
                    pos = positions.pop(sym)
                    stop_levels.pop(sym, None)
                    proceeds = self._sell_price(price, pos["shares"])
                    pnl = proceeds - pos["entry_price"] * pos["shares"]
                    cash += proceeds
                    all_trades.append(
                        {
                            "date": date,
                            "symbol": sym,
                            "action": "SELL",
                            "shares": pos["shares"],
                            "price": price,
                            "pnl": pnl,
                            "reason": "STOP_LOSS",
                            "hold_days": days_held,
                        }
                    )
                    strat = pos.get("strategy_obj")
                    if strat:
                        strat.positions.pop(sym, None)
                        strat.entry_dates.pop(sym, None)
                    cooldowns[sym] = date

            # -- Generate signals --
            # 400 calendar days ≈ 270 trading days: enough for the 252-day
            # 12-1 dual-momentum lookback; other strategies tail() shorter
            # windows from precomputed indicator columns, so this is additive.
            lookback_start = date - timedelta(days=400)
            historical = market_data[
                (market_data.index >= lookback_start) & (market_data.index <= date)
            ]

            all_signals = []
            for strat in strategies:
                try:
                    sigs = strat.generate_signals(historical)
                    if sigs:
                        for s in sigs:
                            s["_strategy"] = strat
                        all_signals.extend(sigs)
                except Exception:
                    continue

            # -- Queue SELL signals for tomorrow's open (OPG). Hold-period and
            #    duplicate checks at queue time; partial-exit share counts are
            #    carried so 50% tranches are modeled faithfully. --
            queued_sell_syms: set = set()
            for sig in all_signals:
                if sig.get("action") != "SELL":
                    continue
                sym = sig["symbol"]
                if sym not in positions or sym in queued_sell_syms:
                    continue
                days_held = (date - positions[sym]["entry_date"]).days
                if days_held < self.min_hold_days:
                    continue
                pending_sells.append(
                    {
                        "symbol": sym,
                        "shares": float(sig.get("shares", 0) or 0),
                        "signal_price": float(sig["price"]),
                        "reason": sig.get("reasoning", ""),
                    }
                )
                queued_sell_syms.add(sym)

            # -- Queue BUY signals for tomorrow's open (gates are constructor
            #    params; cash/heat are checked at FILL time with that day's
            #    portfolio state, mirroring production order submission) --
            buy_sigs = sorted(
                [
                    s
                    for s in all_signals
                    if s.get("action") == "BUY"
                    and s.get("confidence", 0) >= self.min_buy_confidence
                    and s["symbol"] not in positions
                    and (
                        self.cooldown_days <= 0
                        or s["symbol"] not in cooldowns
                        or (date - cooldowns[s["symbol"]]).days >= self.cooldown_days
                    )
                ],
                key=lambda s: s.get("confidence", 0),
                reverse=True,
            )[: self.max_daily_buys]

            for sig in buy_sigs:
                shares = sig.get("shares", 0)
                price = float(sig["price"])
                if shares <= 0 or price <= 0:
                    continue
                pending_buys.append(
                    {
                        "symbol": sig["symbol"],
                        "shares": shares,
                        "signal_price": price,
                        "atr": sig.get("atr", 0) or 0,
                        "reason": sig.get("reasoning", ""),
                        "strategy_obj": sig.get("_strategy"),
                    }
                )

            # -- End-of-day snapshot --
            pos_value = self._mark_to_market(positions, day_data)
            portfolio_value = cash + pos_value
            equity_curve.append(self._snap(date, portfolio_value, cash, pos_value, len(positions)))

        # Record final window
        if current_window_idx < len(windows):
            final_pv = cash + self._mark_to_market(
                positions,
                market_data[market_data.index == sim_dates[-1]] if sim_dates else pd.DataFrame(),
            )
            window_results.append(
                {
                    "window_id": current_window_idx + 1,
                    "train_period": (
                        f"{windows[current_window_idx]['train_start'].date()} to "
                        f"{windows[current_window_idx]['train_end'].date()}"
                    ),
                    "test_period": (
                        f"{windows[current_window_idx]['test_start'].date()} to "
                        f"{windows[current_window_idx]['test_end'].date()}"
                    ),
                    "final_value": final_pv,
                    "trades": [],
                }
            )

        # Aggregate
        overall = self._aggregate_results(equity_curve, all_trades, window_results)
        overall["windows"] = window_results
        return overall

    # ------------------------------------------------------------------
    # Single-window simulation
    # ------------------------------------------------------------------
    def _simulate_window(
        self,
        test_data: pd.DataFrame,
        strategies: list,
        starting_capital: float,
    ) -> dict:
        cash: float = starting_capital
        positions: dict = {}  # {symbol: {shares, entry_price, entry_date, atr, strategy}}
        stop_levels: dict = {}  # {symbol: stop_price}
        equity_curve = []
        trades = []
        day_start_value = starting_capital

        test_dates = sorted(test_data.index.unique())

        for day_idx, date in enumerate(test_dates):
            day_data = test_data[test_data.index == date]
            if day_data.empty:
                continue

            # -- Mark-to-market --
            pos_value = self._mark_to_market(positions, day_data)
            portfolio_value = cash + pos_value

            # -- Daily loss circuit breaker --
            if day_idx == 0:
                day_start_value = portfolio_value
            daily_pnl_pct = (portfolio_value - day_start_value) / day_start_value
            if daily_pnl_pct < -self.max_daily_loss_pct:
                equity_curve.append(
                    self._snap(date, portfolio_value, cash, pos_value, len(positions))
                )
                continue

            # -- Check stop losses --
            for sym in list(positions.keys()):
                sym_row = day_data[day_data["symbol"] == sym]
                if sym_row.empty:
                    continue
                price = float(sym_row.iloc[0]["close"])
                if sym in stop_levels and price <= stop_levels[sym]:
                    pos = positions.pop(sym)
                    stop_levels.pop(sym, None)
                    proceeds = self._sell_price(price, pos["shares"])
                    pnl = proceeds - pos["entry_price"] * pos["shares"]
                    cash += proceeds
                    trades.append(
                        {
                            "date": date,
                            "symbol": sym,
                            "action": "SELL",
                            "shares": pos["shares"],
                            "price": price,
                            "pnl": pnl,
                            "reason": "STOP_LOSS",
                            "hold_days": (date - pos["entry_date"]).days,
                        }
                    )
                    # Update strategy positions
                    strat = pos.get("strategy_obj")
                    if strat and sym in strat.positions:
                        del strat.positions[sym]

            # -- Generate signals (use last 150 days of available data) --
            lookback_start = date - timedelta(days=400)  # covers 252d dual-momentum lookback
            historical = test_data[(test_data.index >= lookback_start) & (test_data.index <= date)]

            all_signals = []
            for strat in strategies:
                try:
                    sigs = strat.generate_signals(historical)
                    if sigs:
                        for s in sigs:
                            s["_strategy"] = strat
                        all_signals.extend(sigs)
                except Exception:
                    continue

            # -- Process SELL signals first --
            for sig in all_signals:
                if sig.get("action") != "SELL":
                    continue
                sym = sig["symbol"]
                if sym not in positions:
                    continue
                pos = positions.pop(sym)
                stop_levels.pop(sym, None)
                price = float(sig["price"])
                proceeds = self._sell_price(price, pos["shares"])
                pnl = proceeds - pos["entry_price"] * pos["shares"]
                cash += proceeds
                trades.append(
                    {
                        "date": date,
                        "symbol": sym,
                        "action": "SELL",
                        "shares": pos["shares"],
                        "price": price,
                        "pnl": pnl,
                        "reason": sig.get("reasoning", ""),
                        "hold_days": (date - pos["entry_date"]).days,
                    }
                )

            # -- Process BUY signals (top 3 by confidence, skip existing) --
            buy_sigs = sorted(
                [
                    s
                    for s in all_signals
                    if s.get("action") == "BUY" and s["symbol"] not in positions
                ],
                key=lambda s: s.get("confidence", 0),
                reverse=True,
            )[: self.max_positions_per_strategy * len(strategies)]

            pos_value = self._mark_to_market(positions, day_data)
            portfolio_value = cash + pos_value
            current_exposure = sum(p["shares"] * p["entry_price"] for p in positions.values())

            for sig in buy_sigs:
                sym = sig["symbol"]
                shares = sig.get("shares", 0)
                price = float(sig["price"])
                if shares <= 0 or price <= 0:
                    continue

                cost = self._buy_cost(price, shares)
                if cost > cash:
                    continue

                # Portfolio heat check
                new_exposure = current_exposure + cost
                if portfolio_value > 0 and new_exposure / portfolio_value > self.max_portfolio_heat:
                    continue

                # Execute
                exec_price = price * (1 + self.slippage_bps / 10000)
                cash -= cost
                current_exposure += cost
                atr = sig.get("atr", 0) or 0

                positions[sym] = {
                    "shares": shares,
                    "entry_price": exec_price,
                    "entry_date": date,
                    "atr": atr,
                    "strategy_obj": sig.get("_strategy"),
                }

                # Set stop loss
                if atr > 0:
                    stop_levels[sym] = exec_price - self.stop_loss_atr_mult * atr

                trades.append(
                    {
                        "date": date,
                        "symbol": sym,
                        "action": "BUY",
                        "shares": shares,
                        "price": exec_price,
                        "pnl": 0,
                        "reason": sig.get("reasoning", ""),
                        "hold_days": 0,
                    }
                )

                # Update strategy in-memory positions
                strat = sig.get("_strategy")
                if strat:
                    strat.positions[sym] = shares
                    strat.entry_dates[sym] = date

            # -- End-of-day snapshot --
            pos_value = self._mark_to_market(positions, day_data)
            portfolio_value = cash + pos_value
            equity_curve.append(self._snap(date, portfolio_value, cash, pos_value, len(positions)))

        # Close remaining positions at last price
        last_day = test_data[test_data.index == test_dates[-1]] if test_dates else pd.DataFrame()
        for sym in list(positions.keys()):
            sym_row = last_day[last_day["symbol"] == sym]
            if sym_row.empty:
                continue
            pos = positions.pop(sym)
            price = float(sym_row.iloc[0]["close"])
            proceeds = self._sell_price(price, pos["shares"])
            pnl = proceeds - pos["entry_price"] * pos["shares"]
            cash += proceeds
            trades.append(
                {
                    "date": test_dates[-1],
                    "symbol": sym,
                    "action": "SELL",
                    "shares": pos["shares"],
                    "price": price,
                    "pnl": pnl,
                    "reason": "WINDOW_END",
                    "hold_days": (test_dates[-1] - pos["entry_date"]).days,
                }
            )

        final_value = cash
        return {
            "final_value": final_value,
            "equity_curve": equity_curve,
            "trades": trades,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _buy_cost(self, price: float, shares: int) -> float:
        exec_price = price * (1 + self.slippage_bps / 10000)
        return exec_price * shares + self.commission_per_share * shares

    def _sell_price(self, price: float, shares: int) -> float:
        exec_price = price * (1 - self.slippage_bps / 10000)
        return exec_price * shares - self.commission_per_share * shares

    @staticmethod
    def _mark_to_market(positions: dict, day_data: pd.DataFrame) -> float:
        total = 0.0
        for sym, pos in positions.items():
            row = day_data[day_data["symbol"] == sym]
            if not row.empty:
                total += pos["shares"] * float(row.iloc[0]["close"])
        return total

    @staticmethod
    def _snap(date, pv, cash, pos_val, n_pos) -> dict:
        return {
            "date": date,
            "portfolio_value": pv,
            "cash": cash,
            "positions_value": pos_val,
            "num_positions": n_pos,
        }

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    def _aggregate_results(
        self,
        equity_curve: list[dict],
        trades: list[dict],
        window_results: list[dict],
    ) -> dict:
        if not equity_curve:
            return {"error": "No data"}

        eq = pd.DataFrame(equity_curve)
        pv = eq["portfolio_value"]
        returns = pv.pct_change().dropna()

        final = float(pv.iloc[-1])
        total_ret = (final / self.initial_capital - 1) * 100
        days = len(eq)
        years = days / 252
        cagr = ((final / self.initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

        vol = float(returns.std() * np.sqrt(252)) if len(returns) > 1 else 0
        sharpe = float(returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

        down = returns[returns < 0]
        sortino = (
            float(returns.mean() / down.std() * np.sqrt(252))
            if len(down) > 0 and down.std() > 0
            else 0
        )

        cummax = pv.cummax()
        dd = (pv - cummax) / cummax * 100
        max_dd = float(dd.min())
        calmar = cagr / abs(max_dd) if max_dd < -0.01 else 0

        sell_trades = [t for t in trades if t["action"] == "SELL"]
        wins = [t for t in sell_trades if t.get("pnl", 0) > 0]
        losses = [t for t in sell_trades if t.get("pnl", 0) <= 0]
        win_rate = len(wins) / len(sell_trades) * 100 if sell_trades else 0
        avg_win = float(np.mean([t["pnl"] for t in wins])) if wins else 0
        avg_loss = float(np.mean([t["pnl"] for t in losses])) if losses else 0
        profit_factor = (
            abs(sum(t["pnl"] for t in wins) / sum(t["pnl"] for t in losses))
            if losses and sum(t["pnl"] for t in losses) != 0
            else 0
        )

        return {
            "initial_capital": self.initial_capital,
            "final_value": final,
            "total_return_pct": total_ret,
            "cagr_pct": cagr,
            "annual_volatility": vol * 100,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown_pct": max_dd,
            "calmar_ratio": calmar,
            "total_trades": len(trades),
            "sell_trades": len(sell_trades),
            "win_rate_pct": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "num_windows": len(window_results),
            "equity_curve": eq,
            "all_trades": pd.DataFrame(trades) if trades else pd.DataFrame(),
        }

    @staticmethod
    def print_results(results: dict):
        """Print formatted backtest results."""
        print("\n" + "=" * 70)
        print("  WALK-FORWARD PORTFOLIO BACKTEST RESULTS")
        print("=" * 70)
        if "error" in results:
            print(f"  ERROR: {results['error']}")
            print("  Tip: reduce --train-days or fetch more history with")
            print("       python scripts/fetch_historical_data.py --years 5")
            print("=" * 70)
            return
        print(f"  Windows:          {results.get('num_windows', 0)}")
        print(f"  Initial Capital:  ${results['initial_capital']:>12,.2f}")
        print(f"  Final Value:      ${results['final_value']:>12,.2f}")
        print(f"  Total Return:     {results['total_return_pct']:>11.2f}%")
        print(f"  CAGR:             {results['cagr_pct']:>11.2f}%")
        print(f"  Annual Vol:       {results['annual_volatility']:>11.2f}%")
        print("-" * 70)
        print(f"  Sharpe Ratio:     {results['sharpe_ratio']:>11.2f}")
        print(f"  Sortino Ratio:    {results['sortino_ratio']:>11.2f}")
        print(f"  Max Drawdown:     {results['max_drawdown_pct']:>11.2f}%")
        print(f"  Calmar Ratio:     {results['calmar_ratio']:>11.2f}")
        print("-" * 70)
        print(f"  Total Trades:     {results['total_trades']:>11}")
        print(f"  Closed Trades:    {results['sell_trades']:>11}")
        print(f"  Win Rate:         {results['win_rate_pct']:>11.1f}%")
        print(f"  Avg Win:          ${results['avg_win']:>11,.2f}")
        print(f"  Avg Loss:         ${results['avg_loss']:>11,.2f}")
        print(f"  Profit Factor:    {results['profit_factor']:>11.2f}")
        print("=" * 70)

        # Per-window summary
        if "windows" in results and results["windows"]:
            print("\n  Per-Window Summary:")
            print(f"  {'#':>3}  {'Test Period':<27} {'Return':>8}  {'Trades':>6}")
            print("  " + "-" * 52)
            for w in results["windows"]:
                ret = (w["final_value"] / results["initial_capital"] - 1) * 100
                n_trades = len(w.get("trades", []))
                print(f"  {w['window_id']:>3}  {w['test_period']:<27} {ret:>+7.2f}%  {n_trades:>6}")
            print()
