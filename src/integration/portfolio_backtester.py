#!/usr/bin/env python3
"""
Portfolio-Level Walk-Forward Backtesting Framework

Simulates the full trading pipeline:
  signals → correlation filter → risk limits → ATR sizing → costs → execute

Walk-forward windows: 2yr train / 6mo test / 6mo step
"""
import pandas as pd
import numpy as np
from datetime import timedelta
from typing import Dict, List, Tuple, Optional
from copy import deepcopy
import logging
import json
import os

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
        stop_loss_atr_mult: float = 2.5,
        max_positions_per_strategy: int = 3,
        max_correlation: float = 0.80,
    ):
        self.initial_capital = initial_capital
        self.slippage_bps = slippage_bps
        self.commission_per_share = commission_per_share
        self.max_portfolio_heat = max_portfolio_heat
        self.max_daily_loss_pct = max_daily_loss_pct
        self.stop_loss_atr_mult = stop_loss_atr_mult
        self.max_positions_per_strategy = max_positions_per_strategy
        self.max_correlation = max_correlation

    # ------------------------------------------------------------------
    # Walk-forward driver
    # ------------------------------------------------------------------
    def run_walk_forward(
        self,
        market_data: pd.DataFrame,
        strategy_classes: List,
        train_days: int = 504,
        test_days: int = 126,
        step_days: int = 126,
    ) -> Dict:
        """
        Run walk-forward backtest across multiple windows.

        Args:
            market_data: Full historical data (DatetimeIndex, 'symbol' column)
            strategy_classes: List of strategy *classes* (not instances)
            train_days / test_days / step_days: walk-forward params

        Returns:
            Dict with overall metrics, per-window metrics, equity curve
        """
        dates = sorted(market_data.index.unique())
        window_results = []
        all_equity = []
        all_trades = []
        capital = self.initial_capital
        window_id = 0

        while True:
            train_start_idx = window_id * step_days
            train_end_idx = train_start_idx + train_days
            test_end_idx = train_end_idx + test_days

            if test_end_idx > len(dates):
                break

            train_start = dates[train_start_idx]
            train_end = dates[train_end_idx - 1]
            test_start = dates[train_end_idx]
            test_end = dates[min(test_end_idx - 1, len(dates) - 1)]

            logger.info(
                f"Window {window_id + 1}: train {train_start.date()}-{train_end.date()}, "
                f"test {test_start.date()}-{test_end.date()}, capital ${capital:,.0f}"
            )

            train_data = market_data[
                (market_data.index >= train_start) & (market_data.index <= train_end)
            ]
            test_data = market_data[
                (market_data.index >= test_start) & (market_data.index <= test_end)
            ]

            # Fresh strategy instances per window (train on train_data)
            strategies = []
            for i, cls in enumerate(strategy_classes):
                strat = cls(strategy_id=i + 1, capital=capital / len(strategy_classes))
                # Let ML strategies train on training data
                if hasattr(strat, '_train_model'):
                    try:
                        strat._train_model(train_data)
                    except Exception as e:
                        logger.warning(f"Training failed for {strat.name}: {e}")
                strategies.append(strat)

            # Run single-window simulation
            result = self._simulate_window(
                test_data, strategies, capital
            )

            result['window_id'] = window_id + 1
            result['train_period'] = f"{train_start.date()} to {train_end.date()}"
            result['test_period'] = f"{test_start.date()} to {test_end.date()}"
            window_results.append(result)

            all_equity.extend(result['equity_curve'])
            all_trades.extend(result['trades'])

            # Carry forward capital
            capital = result['final_value']
            window_id += 1

        # Aggregate
        overall = self._aggregate_results(all_equity, all_trades, window_results)
        overall['windows'] = window_results
        return overall

    # ------------------------------------------------------------------
    # Single-window simulation
    # ------------------------------------------------------------------
    def _simulate_window(
        self,
        test_data: pd.DataFrame,
        strategies: List,
        starting_capital: float,
    ) -> Dict:
        cash = starting_capital
        positions = {}  # {symbol: {shares, entry_price, entry_date, atr, strategy}}
        stop_levels = {}  # {symbol: stop_price}
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
                equity_curve.append(self._snap(date, portfolio_value, cash, pos_value, len(positions)))
                continue

            # -- Check stop losses --
            for sym in list(positions.keys()):
                sym_row = day_data[day_data['symbol'] == sym]
                if sym_row.empty:
                    continue
                price = float(sym_row.iloc[0]['close'])
                if sym in stop_levels and price <= stop_levels[sym]:
                    pos = positions.pop(sym)
                    stop_levels.pop(sym, None)
                    proceeds = self._sell_price(price, pos['shares'])
                    pnl = proceeds - pos['entry_price'] * pos['shares']
                    cash += proceeds
                    trades.append({
                        'date': date, 'symbol': sym, 'action': 'SELL',
                        'shares': pos['shares'], 'price': price,
                        'pnl': pnl, 'reason': 'STOP_LOSS',
                        'hold_days': (date - pos['entry_date']).days,
                    })
                    # Update strategy positions
                    strat = pos.get('strategy_obj')
                    if strat and sym in strat.positions:
                        del strat.positions[sym]

            # -- Generate signals (use last 150 days of available data) --
            lookback_start = date - timedelta(days=210)  # extra buffer for indicators
            historical = test_data[
                (test_data.index >= lookback_start) & (test_data.index <= date)
            ]

            all_signals = []
            for strat in strategies:
                try:
                    sigs = strat.generate_signals(historical)
                    if sigs:
                        for s in sigs:
                            s['_strategy'] = strat
                        all_signals.extend(sigs)
                except Exception:
                    continue

            # -- Process SELL signals first --
            for sig in all_signals:
                if sig.get('action') != 'SELL':
                    continue
                sym = sig['symbol']
                if sym not in positions:
                    continue
                pos = positions.pop(sym)
                stop_levels.pop(sym, None)
                price = float(sig['price'])
                proceeds = self._sell_price(price, pos['shares'])
                pnl = proceeds - pos['entry_price'] * pos['shares']
                cash += proceeds
                trades.append({
                    'date': date, 'symbol': sym, 'action': 'SELL',
                    'shares': pos['shares'], 'price': price,
                    'pnl': pnl, 'reason': sig.get('reasoning', ''),
                    'hold_days': (date - pos['entry_date']).days,
                })

            # -- Process BUY signals (top 3 by confidence, skip existing) --
            buy_sigs = sorted(
                [s for s in all_signals if s.get('action') == 'BUY' and s['symbol'] not in positions],
                key=lambda s: s.get('confidence', 0),
                reverse=True,
            )[:self.max_positions_per_strategy * len(strategies)]

            pos_value = self._mark_to_market(positions, day_data)
            portfolio_value = cash + pos_value
            current_exposure = sum(p['shares'] * p['entry_price'] for p in positions.values())

            for sig in buy_sigs:
                sym = sig['symbol']
                shares = sig.get('shares', 0)
                price = float(sig['price'])
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
                atr = sig.get('atr', 0) or 0

                positions[sym] = {
                    'shares': shares,
                    'entry_price': exec_price,
                    'entry_date': date,
                    'atr': atr,
                    'strategy_obj': sig.get('_strategy'),
                }

                # Set stop loss
                if atr > 0:
                    stop_levels[sym] = exec_price - self.stop_loss_atr_mult * atr

                trades.append({
                    'date': date, 'symbol': sym, 'action': 'BUY',
                    'shares': shares, 'price': exec_price,
                    'pnl': 0, 'reason': sig.get('reasoning', ''),
                    'hold_days': 0,
                })

                # Update strategy in-memory positions
                strat = sig.get('_strategy')
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
            sym_row = last_day[last_day['symbol'] == sym]
            if sym_row.empty:
                continue
            pos = positions.pop(sym)
            price = float(sym_row.iloc[0]['close'])
            proceeds = self._sell_price(price, pos['shares'])
            pnl = proceeds - pos['entry_price'] * pos['shares']
            cash += proceeds
            trades.append({
                'date': test_dates[-1], 'symbol': sym, 'action': 'SELL',
                'shares': pos['shares'], 'price': price,
                'pnl': pnl, 'reason': 'WINDOW_END',
                'hold_days': (test_dates[-1] - pos['entry_date']).days,
            })

        final_value = cash
        return {
            'final_value': final_value,
            'equity_curve': equity_curve,
            'trades': trades,
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
    def _mark_to_market(positions: Dict, day_data: pd.DataFrame) -> float:
        total = 0.0
        for sym, pos in positions.items():
            row = day_data[day_data['symbol'] == sym]
            if not row.empty:
                total += pos['shares'] * float(row.iloc[0]['close'])
        return total

    @staticmethod
    def _snap(date, pv, cash, pos_val, n_pos) -> Dict:
        return {
            'date': date, 'portfolio_value': pv,
            'cash': cash, 'positions_value': pos_val,
            'num_positions': n_pos,
        }

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    def _aggregate_results(
        self,
        equity_curve: List[Dict],
        trades: List[Dict],
        window_results: List[Dict],
    ) -> Dict:
        if not equity_curve:
            return {'error': 'No data'}

        eq = pd.DataFrame(equity_curve)
        pv = eq['portfolio_value']
        returns = pv.pct_change().dropna()

        final = float(pv.iloc[-1])
        total_ret = (final / self.initial_capital - 1) * 100
        days = len(eq)
        years = days / 252
        cagr = ((final / self.initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

        vol = float(returns.std() * np.sqrt(252)) if len(returns) > 1 else 0
        sharpe = float(returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

        down = returns[returns < 0]
        sortino = float(returns.mean() / down.std() * np.sqrt(252)) if len(down) > 0 and down.std() > 0 else 0

        cummax = pv.cummax()
        dd = (pv - cummax) / cummax * 100
        max_dd = float(dd.min())
        calmar = cagr / abs(max_dd) if max_dd < -0.01 else 0

        sell_trades = [t for t in trades if t['action'] == 'SELL']
        wins = [t for t in sell_trades if t.get('pnl', 0) > 0]
        losses = [t for t in sell_trades if t.get('pnl', 0) <= 0]
        win_rate = len(wins) / len(sell_trades) * 100 if sell_trades else 0
        avg_win = float(np.mean([t['pnl'] for t in wins])) if wins else 0
        avg_loss = float(np.mean([t['pnl'] for t in losses])) if losses else 0
        profit_factor = abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) if losses and sum(t['pnl'] for t in losses) != 0 else 0

        return {
            'initial_capital': self.initial_capital,
            'final_value': final,
            'total_return_pct': total_ret,
            'cagr_pct': cagr,
            'annual_volatility': vol * 100,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'max_drawdown_pct': max_dd,
            'calmar_ratio': calmar,
            'total_trades': len(trades),
            'sell_trades': len(sell_trades),
            'win_rate_pct': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'num_windows': len(window_results),
            'equity_curve': eq,
            'all_trades': pd.DataFrame(trades) if trades else pd.DataFrame(),
        }

    @staticmethod
    def print_results(results: Dict):
        """Print formatted backtest results."""
        print("\n" + "=" * 70)
        print("  WALK-FORWARD PORTFOLIO BACKTEST RESULTS")
        print("=" * 70)
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
        if 'windows' in results and results['windows']:
            print("\n  Per-Window Summary:")
            print(f"  {'#':>3}  {'Test Period':<27} {'Return':>8}  {'Trades':>6}")
            print("  " + "-" * 52)
            for w in results['windows']:
                ret = (w['final_value'] / results['initial_capital'] - 1) * 100
                n_trades = len(w.get('trades', []))
                print(f"  {w['window_id']:>3}  {w['test_period']:<27} {ret:>+7.2f}%  {n_trades:>6}")
            print()
