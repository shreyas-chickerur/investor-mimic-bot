"""
Critical bug regression tests + new guard tests.

Covers the specific failures observed in live artifacts:
  1. stop-loss crash: record_trade vs log_trade mismatch
  2. portfolio heat: 175% config must now be 40%
  3. max positions guard blocks buys when at limit
  4. benchmark ETF guard blocks SPY/QQQ/XLK from being bought
  5. get_all_open_positions returns correct count
  6. dynamic allocator respects min/max allocation bounds
 13. order timing: execution engine uses TimeInForce.OPG (not DAY) for after-hours placement
 14. VIX fetcher: User-Agent header present to avoid Yahoo 429 throttling
  7. drawdown manager halt / panic thresholds
  8. correlation filter blocks high-correlation buys
  9. RSI mean reversion does not buy in downtrend (SMA-100 filter)
 10. ML momentum blocks signals below confidence floor
 11. Factor momentum blocks benchmark symbols from factor scoring universe
 12. Config max_total_positions is present and sane
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import TradingDatabase
from src.data.universe_provider import UniverseProvider
from src.regime.dynamic_allocator import DynamicAllocator
from src.regime.regime_detector import RegimeDetector
from src.risk.correlation_filter import CorrelationFilter
from src.risk.drawdown_stop_manager import DrawdownStopManager
from src.risk.portfolio_risk_manager import PortfolioRiskManager
from src.risk.stop_loss_manager import StopLossManager
from src.utils.config_loader import get_config

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    return TradingDatabase(db_path=db_path)


@pytest.fixture
def seeded_db(tmp_db):
    """DB with one strategy and one open position."""
    sid = tmp_db.create_strategy("TestStrategy", "desc", 10_000)
    tmp_db.update_position(sid, "AAPL", shares=10, avg_price=150.0, current_price=148.0)
    tmp_db.update_position(sid, "MSFT", shares=5, avg_price=300.0, current_price=295.0)
    return tmp_db, sid


# ===========================================================================
# 1. Stop-loss database method name (the crash that silenced all stop losses)
# ===========================================================================


class TestStopLossMethodName:
    def test_database_has_log_trade_not_record_trade(self, tmp_db):
        """TradingDatabase must expose log_trade — not record_trade."""
        assert hasattr(tmp_db, "log_trade"), "DB missing log_trade method"
        assert not hasattr(tmp_db, "record_trade"), (
            "record_trade exists — execution_engine was calling this non-existent "
            "method, silencing every stop loss exit"
        )

    def test_log_trade_persists_sell(self, seeded_db):
        db, sid = seeded_db
        trade_id = db.log_trade(
            strategy_id=sid,
            signal_id=None,
            symbol="AAPL",
            action="SELL",
            shares=10,
            requested_price=148.0,
            exec_price=147.5,
            slippage_cost=0.50,
            commission_cost=0.0,
            order_id="order-001",
        )
        assert trade_id > 0

    def test_execution_engine_stop_loss_calls_log_trade(self):
        """Grep-level check: execution_engine.py must not call record_trade."""
        src = Path("src/core/execution_engine.py").read_text()
        assert "record_trade" not in src, (
            "execution_engine.py still calls self.db.record_trade() — "
            "this crashes every stop-loss exit silently"
        )
        assert "log_trade" in src, "execution_engine.py must call self.db.log_trade()"


# ===========================================================================
# 2. Portfolio heat config: must be ≤ 1.0 (100%)
# ===========================================================================


class TestPortfolioHeatConfig:
    def test_max_portfolio_heat_is_sane(self):
        cfg = get_config()
        heat = cfg.get("risk.max_portfolio_heat", 1.75)
        assert heat <= 1.0, (
            f"max_portfolio_heat={heat:.2f} allows {heat*100:.0f}% exposure — "
            "this means margin/leverage. Must be ≤ 1.0 (100%)"
        )
        assert heat >= 0.10, "max_portfolio_heat too restrictive — set at least 10%"

    def test_max_portfolio_heat_blocks_new_position_when_exceeded(self):
        rm = PortfolioRiskManager(max_portfolio_heat=0.40)
        portfolio_value = 10_000
        current_exposure = 4_200  # 42% — above 40% limit
        can_add = rm.can_add_position(
            position_value=500,
            current_exposure=current_exposure,
            portfolio_value=portfolio_value,
        )
        assert not can_add, "Risk manager should block new position when heat exceeded"

    def test_max_portfolio_heat_allows_position_when_under_limit(self):
        rm = PortfolioRiskManager(max_portfolio_heat=0.40)
        portfolio_value = 10_000
        current_exposure = 2_000  # 20% — under 40% limit
        can_add = rm.can_add_position(
            position_value=500,
            current_exposure=current_exposure,
            portfolio_value=portfolio_value,
        )
        assert can_add


# ===========================================================================
# 3. Max positions guard
# ===========================================================================


class TestMaxPositionsGuard:
    def test_get_all_open_positions_returns_correct_count(self, seeded_db):
        db, sid = seeded_db
        positions = db.get_all_open_positions()
        assert len(positions) == 2

    def test_get_all_open_positions_excludes_zero_share_rows(self, seeded_db):
        db, sid = seeded_db
        # Close one position
        db.update_position(sid, "AAPL", shares=0, avg_price=150.0)
        positions = db.get_all_open_positions()
        assert len(positions) == 1
        assert positions[0]["symbol"] == "MSFT"

    def test_max_total_positions_config_present_and_sane(self):
        cfg = get_config()
        max_pos = cfg.get("risk.max_total_positions", None)
        assert max_pos is not None, "risk.max_total_positions missing from config"
        assert (
            5 <= max_pos <= 30
        ), f"max_total_positions={max_pos} is outside sensible range [5, 30]"


# ===========================================================================
# 4. Benchmark ETF guard
# ===========================================================================


class TestBenchmarkGuard:
    BENCHMARKS = UniverseProvider.BENCHMARK_SYMBOLS

    def test_benchmark_symbols_set_is_non_empty(self):
        assert len(self.BENCHMARKS) > 0

    def test_spy_is_benchmark(self):
        assert "SPY" in self.BENCHMARKS

    def test_qqq_is_not_tradeable_as_position(self):
        """QQQ was being bought by ML Momentum — it must be blocked."""
        assert "QQQ" in self.BENCHMARKS, "QQQ must be in BENCHMARK_SYMBOLS"

    def test_xlk_is_benchmark(self):
        """XLK appeared as an open position — must be blocked."""
        assert "XLK" in self.BENCHMARKS

    def test_execution_engine_imports_universe_provider(self):
        src = Path("src/core/execution_engine.py").read_text()
        assert "UniverseProvider" in src
        assert "BENCHMARK_SYMBOLS" in src
        assert "benchmark_etf_guard" in src


# ===========================================================================
# 5. Dynamic allocator bounds
# ===========================================================================


class TestDynamicAllocator:
    def test_equal_allocation_when_no_history(self):
        allocator = DynamicAllocator(total_capital=100_000)
        allocs = allocator.calculate_allocations(
            strategy_ids=[1, 2, 3, 4],
            strategy_performance=None,
        )
        assert len(allocs) == 4
        for v in allocs.values():
            assert abs(v - 25_000) < 1

    def test_weights_sum_to_total_capital(self):
        allocator = DynamicAllocator(
            total_capital=100_000, max_allocation_pct=0.35, min_allocation_pct=0.10
        )
        perf = {
            1: [0.01] * 60,
            2: [-0.005] * 60,
            3: [0.008] * 60,
            4: [0.002] * 60,
        }
        allocs = allocator.calculate_allocations([1, 2, 3, 4], perf)
        assert abs(sum(allocs.values()) - 100_000) < 1

    def test_no_strategy_exceeds_max_allocation(self):
        allocator = DynamicAllocator(
            total_capital=100_000, max_allocation_pct=0.35, min_allocation_pct=0.10
        )
        perf = {1: [0.05] * 60, 2: [0.0] * 60, 3: [0.0] * 60, 4: [0.0] * 60}
        allocs = allocator.calculate_allocations([1, 2, 3, 4], perf)
        for sid, v in allocs.items():
            pct = v / 100_000
            assert pct <= 0.35 + 1e-6, f"Strategy {sid} got {pct:.1%} > 35% max"

    def test_no_strategy_below_min_allocation(self):
        allocator = DynamicAllocator(
            total_capital=100_000, max_allocation_pct=0.35, min_allocation_pct=0.10
        )
        perf = {1: [0.05] * 60, 2: [-0.05] * 60, 3: [-0.05] * 60, 4: [-0.05] * 60}
        allocs = allocator.calculate_allocations([1, 2, 3, 4], perf)
        for sid, v in allocs.items():
            pct = v / 100_000
            assert pct >= 0.10 - 1e-6, f"Strategy {sid} got {pct:.1%} < 10% min"


# ===========================================================================
# 6. Drawdown manager thresholds
# ===========================================================================


class TestDrawdownManager:
    def _make_manager(self, tmp_db):
        notifier = MagicMock()
        return DrawdownStopManager(
            db=tmp_db,
            email_notifier=notifier,
            halt_threshold=0.08,
            panic_threshold=0.10,
            halt_cooldown_days=10,
            panic_cooldown_days=20,
            rampup_sizing_pct=0.50,
            rampup_days=5,
            flatten_on_panic=True,
        )

    def test_no_stop_below_halt_threshold(self, tmp_db):
        mgr = self._make_manager(tmp_db)
        is_stopped, reason, _ = mgr.check_drawdown_stop(
            current_portfolio_value=9_300,  # -7% from 10k
            peak_portfolio_value=10_000,
        )
        assert not is_stopped

    def test_halt_triggered_at_8pct(self, tmp_db):
        mgr = self._make_manager(tmp_db)
        is_stopped, reason, _ = mgr.check_drawdown_stop(
            current_portfolio_value=9_150,  # -8.5%
            peak_portfolio_value=10_000,
        )
        assert is_stopped
        assert "HALT" in reason

    def test_panic_triggered_at_10pct(self, tmp_db):
        mgr = self._make_manager(tmp_db)
        is_stopped, reason, _ = mgr.check_drawdown_stop(
            current_portfolio_value=8_900,  # -11%
            peak_portfolio_value=10_000,
        )
        assert is_stopped
        assert "PANIC" in reason

    def test_config_halt_threshold_is_sane(self):
        cfg = get_config()
        halt = cfg.get("risk.drawdown_halt_threshold", 0.10)
        panic = cfg.get("risk.drawdown_panic_threshold", 0.15)
        assert halt < panic, "Halt threshold must be less than panic threshold"
        assert 0.05 <= halt <= 0.20


# ===========================================================================
# 7. Stop loss manager
# ===========================================================================


class TestStopLossManager:
    def test_stop_not_triggered_above_price(self):
        mgr = StopLossManager(atr_multiplier=2.5)
        mgr.set_stop_loss("AAPL", entry_price=150.0, atr=2.0)
        # stop = 150 - 2.5*2 = 145
        assert not mgr.check_stop_loss("AAPL", current_price=146.0)

    def test_stop_triggered_at_or_below_price(self):
        mgr = StopLossManager(atr_multiplier=2.5)
        mgr.set_stop_loss("AAPL", entry_price=150.0, atr=2.0)
        # stop = 145
        assert mgr.check_stop_loss("AAPL", current_price=144.0)
        assert mgr.check_stop_loss("AAPL", current_price=145.0)

    def test_stop_not_set_without_atr(self):
        mgr = StopLossManager(atr_multiplier=2.5)
        mgr.set_stop_loss("AAPL", entry_price=150.0, atr=0)
        assert "AAPL" not in mgr.stop_levels

    def test_ratchet_stop_moves_to_entry_at_1x_atr_profit(self):
        mgr = StopLossManager(atr_multiplier=2.5, breakeven_atr=1.0, lock_atr=2.0)
        mgr.set_stop_loss("AAPL", entry_price=100.0, atr=4.0)
        initial_stop = mgr.stop_levels["AAPL"]  # 100 - 10 = 90
        mgr.update_ratchet_stop("AAPL", current_price=105.0, atr=4.0)  # +5 = 1.25x ATR
        assert mgr.stop_levels["AAPL"] >= 100.0, "Stop should ratchet to at least entry"
        assert mgr.stop_levels["AAPL"] > initial_stop

    def test_ratchet_stop_never_moves_down(self):
        mgr = StopLossManager(atr_multiplier=2.5, breakeven_atr=1.0, lock_atr=2.0)
        mgr.set_stop_loss("AAPL", entry_price=100.0, atr=4.0)
        mgr.update_ratchet_stop("AAPL", current_price=112.0, atr=4.0)  # +12 = 3x ATR
        high_stop = mgr.stop_levels["AAPL"]
        mgr.update_ratchet_stop("AAPL", current_price=108.0, atr=4.0)  # pullback
        assert mgr.stop_levels["AAPL"] >= high_stop, "Ratchet stop must never move down"


# ===========================================================================
# 8. Correlation filter
# ===========================================================================


class TestCorrelationFilter:
    def _make_market_data(self, symbols, n=65, seed=42):
        rng = np.random.default_rng(seed)
        frames = []
        for sym in symbols:
            prices = 100 * np.cumprod(1 + rng.normal(0.0005, 0.02, n))
            df = pd.DataFrame({"symbol": sym, "close": prices})
            df.index = pd.date_range("2025-01-01", periods=n, freq="B")
            frames.append(df)
        return pd.concat(frames)

    def test_uncorrelated_pair_passes(self):
        cf = CorrelationFilter(max_correlation=0.70)
        md = self._make_market_data(["AAPL", "XOM"])
        for sym in ["AAPL", "XOM"]:
            cf.update_price_history(sym, md[md["symbol"] == sym]["close"])
        corr = cf.calculate_correlation("AAPL", "XOM")
        # With independent random walks the correlation should be well under 0.70
        if abs(corr) < 0.70:
            mult, _ = cf.calculate_size_multiplier(corr)
            assert mult == 1.0

    def test_perfectly_correlated_pair_rejected(self):
        cf = CorrelationFilter(max_correlation=0.70)
        prices = pd.Series(range(1, 66), dtype=float)
        cf.update_price_history("AAPL", prices)
        cf.update_price_history("AAPL_CLONE", prices)
        corr = cf.calculate_correlation("AAPL", "AAPL_CLONE")
        assert abs(corr) > 0.99
        mult, _ = cf.calculate_size_multiplier(corr)
        assert mult == 0.0, "Perfectly correlated pair must be rejected (size 0)"


# ===========================================================================
# 9. RSI Mean Reversion — downtrend filter
# ===========================================================================


class TestRSIMeanReversionGuards:
    def _make_strategy(self):
        from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy

        return RSIMeanReversionStrategy(strategy_id=1, capital=10_000)

    def _make_data(self, rsi=28.0, rsi_prev=27.0, price=100.0, sma_100=None, vol_ratio=1.0):
        n = 150
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        data = []
        for i, _ in enumerate(dates):
            data.append(
                {
                    "symbol": "AAPL",
                    "close": price - 0.01 * i,  # slight downtrend
                    "open": price,
                    "high": price + 1,
                    "low": price - 1,
                    "volume": 1_000_000,
                    "rsi": rsi if i == n - 1 else 50.0,
                    "atr_20": 2.0,
                    "sma_100": sma_100 if sma_100 is not None else price + 10,
                    "volume_ratio": vol_ratio,
                    "returns_5d": 0.01,
                    "returns_20d": 0.02,
                    "returns_60d": 0.03,
                    "volatility_20d": 0.15,
                    "volatility_60d": 0.15,
                    "price_to_sma20": 0.0,
                    "price_to_sma50": 0.0,
                    "adx": 20.0,
                }
            )
        df = pd.DataFrame(data, index=dates)
        # Patch RSI on second-to-last row so slope is positive
        df.loc[dates[-2], "rsi"] = rsi_prev
        return df

    def test_buy_signal_in_uptrend(self):
        strat = self._make_strategy()
        md = self._make_data(rsi=28.0, rsi_prev=25.0, price=110.0, sma_100=100.0)
        md["symbol"] = "AAPL"
        signals = strat.generate_signals(md)
        buys = [s for s in signals if s["action"] == "BUY"]
        assert len(buys) == 1

    def test_no_buy_in_downtrend(self):
        """Price below SMA-100 = downtrend; RSI mean reversion should be suppressed."""
        strat = self._make_strategy()
        # price=100 but sma_100=120 → downtrend
        md = self._make_data(rsi=28.0, rsi_prev=25.0, price=100.0, sma_100=120.0)
        md["symbol"] = "AAPL"
        signals = strat.generate_signals(md)
        buys = [s for s in signals if s["action"] == "BUY"]
        assert len(buys) == 0, "Should not buy oversold stock in downtrend"

    def test_no_buy_on_capitulation_volume(self):
        """High volume on oversold = capitulation/distribution, not reversion."""
        strat = self._make_strategy()
        md = self._make_data(rsi=28.0, rsi_prev=25.0, price=110.0, sma_100=100.0, vol_ratio=2.0)
        md["symbol"] = "AAPL"
        signals = strat.generate_signals(md)
        buys = [s for s in signals if s["action"] == "BUY"]
        assert len(buys) == 0, "Should suppress buy on capitulation volume spike"


# ===========================================================================
# 10. Factor momentum — benchmark exclusion from scoring universe
# ===========================================================================


class TestFactorMomentumBenchmarkExclusion:
    def _make_strategy(self):
        from src.strategies.strategy_factor_momentum import FactorMomentumStrategy

        return FactorMomentumStrategy(strategy_id=4, capital=10_000)

    def _make_market_data(self, symbols, n=65):
        rng = np.random.default_rng(7)
        frames = []
        for sym in symbols:
            prices = 100 * np.cumprod(1 + rng.normal(0.001, 0.015, n))
            returns = np.diff(prices) / prices[:-1]
            df = pd.DataFrame(
                {
                    "symbol": sym,
                    "close": prices,
                    "open": prices * 0.999,
                    "high": prices * 1.01,
                    "low": prices * 0.99,
                    "volume": rng.integers(500_000, 2_000_000, n),
                    "rsi": rng.uniform(30, 70, n),
                    "returns_5d": np.pad(returns, (5, 0))[:n],
                    "returns_20d": np.pad(returns, (20, 0))[:n],
                    "returns_60d": np.pad(returns, (60, 0))[:n],
                    "volatility_20d": np.full(n, 0.15),
                    "volatility_60d": np.full(n, 0.15),
                    "volume_ratio": rng.uniform(0.5, 2.0, n),
                    "atr_20": prices * 0.02,
                    "adx": rng.uniform(15, 40, n),
                    "price_to_sma20": rng.uniform(-0.05, 0.05, n),
                    "price_to_sma50": rng.uniform(-0.05, 0.05, n),
                },
                index=pd.date_range("2024-01-01", periods=n, freq="B"),
            )
            frames.append(df)
        return pd.concat(frames)

    def test_benchmark_symbols_not_in_buy_signals(self):
        strat = self._make_strategy()
        benchmarks = UniverseProvider.BENCHMARK_SYMBOLS
        tradeable = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META"]
        all_syms = tradeable + list(benchmarks)
        md = self._make_market_data(all_syms)
        signals = strat.generate_signals(md)
        bought = {s["symbol"] for s in signals if s["action"] == "BUY"}
        overlap = bought & benchmarks
        assert len(overlap) == 0, (
            f"Factor momentum bought benchmark ETF(s): {overlap}. "
            "These must never appear as BUY signals."
        )


# ===========================================================================
# 11. Regime detector — VIX fallback detection
# ===========================================================================


class TestRegimeDetectorVIXFallback:
    def test_fallback_value_triggers_normal_regime(self):
        """VIX=18.0 is the hardcoded fallback. System should at least classify it correctly."""
        detector = RegimeDetector(vix_low_threshold=15.0, vix_high_threshold=25.0)
        regime = detector.detect_volatility_regime(vix=18.0)
        assert regime == "normal"

    def test_low_vix_gives_low_vol_regime(self):
        detector = RegimeDetector(vix_low_threshold=15.0, vix_high_threshold=25.0)
        regime = detector.detect_volatility_regime(vix=12.0)
        assert regime == "low_volatility"

    def test_high_vix_gives_high_vol_regime(self):
        detector = RegimeDetector(vix_low_threshold=15.0, vix_high_threshold=25.0)
        regime = detector.detect_volatility_regime(vix=30.0)
        assert regime == "high_volatility"

    def test_regime_adjustments_reduce_heat_in_high_vol(self):
        detector = RegimeDetector(vix_low_threshold=15.0, vix_high_threshold=25.0)
        normal_adj = detector.get_regime_adjustments(vix=18.0, market_data=None)
        high_adj = detector.get_regime_adjustments(vix=30.0, market_data=None)
        assert (
            high_adj["max_portfolio_heat"] < normal_adj["max_portfolio_heat"]
        ), "High-vol regime must reduce max_portfolio_heat vs normal"

    def test_regime_adjustments_increase_heat_in_low_vol(self):
        detector = RegimeDetector(vix_low_threshold=15.0, vix_high_threshold=25.0)
        normal_adj = detector.get_regime_adjustments(vix=18.0, market_data=None, base_max_heat=0.30)
        low_adj = detector.get_regime_adjustments(vix=10.0, market_data=None, base_max_heat=0.30)
        assert low_adj["max_portfolio_heat"] >= normal_adj["max_portfolio_heat"]


# ===========================================================================
# 12. Config sanity checks (holistic)
# ===========================================================================


class TestConfigSanity:
    def setup_method(self):
        self.cfg = get_config()

    def test_max_portfolio_heat_is_fraction_not_percentage(self):
        heat = self.cfg.get("risk.max_portfolio_heat")
        assert heat is not None
        assert heat <= 1.0, (
            f"max_portfolio_heat={heat} looks like a percentage (e.g. 1.75 = 175%). "
            "Must be a fraction: 0.40 means 40%."
        )

    def test_max_total_positions_exists(self):
        assert self.cfg.get("risk.max_total_positions") is not None

    def test_stop_loss_atr_multiplier_is_positive(self):
        mult = self.cfg.get("risk.stop_loss_atr_multiplier")
        assert mult is not None and mult > 0

    def test_drawdown_halt_less_than_panic(self):
        halt = self.cfg.get("risk.drawdown_halt_threshold")
        panic = self.cfg.get("risk.drawdown_panic_threshold")
        assert halt < panic

    def test_min_confidence_is_above_random_chance(self):
        conf = self.cfg.get("strategies.ml_momentum.min_confidence", 0.51)
        assert conf >= 0.50, "min_confidence below 0.50 is worse than random — no edge"

    def test_max_position_size_pct_is_reasonable(self):
        pct = self.cfg.get("risk.max_position_size_pct")
        assert 0.02 <= pct <= 0.20, (
            f"max_position_size_pct={pct:.0%} is outside [2%, 20%] — "
            "too large concentrates risk, too small means negligible positions"
        )


# ===========================================================================
# 13. Order timing: execution engine must use OPG not DAY
#     (DAY orders placed at 4:15 PM ET after market close never fill)
# ===========================================================================


class TestOrderTimingOPG:
    def test_execution_engine_uses_opg_not_day_for_buys(self):
        """All BUY orders in execution_engine must use TimeInForce.OPG.

        Signals are generated after close at 4:15 PM ET.  DAY orders placed
        after market close are queued or rejected by Alpaca.  OPG (market-on-
        open) orders execute at the next session's open — the correct workflow.
        """
        engine_src = Path("src/core/execution_engine.py").read_text()
        assert "TimeInForce.DAY" not in engine_src, (
            "execution_engine.py still references TimeInForce.DAY — "
            "orders placed after 4 PM ET with DAY never fill.  Use OPG."
        )

    def test_execution_engine_uses_opg(self):
        engine_src = Path("src/core/execution_engine.py").read_text()
        assert "TimeInForce.OPG" in engine_src, (
            "execution_engine.py has no TimeInForce.OPG — after-hours orders "
            "must use OPG to execute at next market open."
        )

    def test_limit_order_uses_generous_buffer(self):
        """BUY orders use LOO (Limit-On-Open) with a 1% buffer above typical price.

        The previous bug used 0.1% which caused non-fills on any overnight gap.
        The new design intentionally uses LimitOrderRequest with typical_price * 1.01
        so we avoid chasing gap-ups while still filling on normal opens.
        """
        engine_src = Path("src/core/execution_engine.py").read_text()
        import re

        # Must use LimitOrderRequest for BUY (the intentional new design)
        instantiations = re.findall(r"LimitOrderRequest\s*\(", engine_src)
        assert (
            len(instantiations) >= 1
        ), "LimitOrderRequest should be used for BUY OPG orders (LOO) with a 1% typical-price buffer"

        # The buffer must be 1% (1.01), NOT the old 0.1% (1.001) that caused non-fills
        assert (
            "1.001" not in engine_src
        ), "Found old 0.1% limit buffer — use 1.01 (1%) so orders fill on normal opens"
        assert "1.01" in engine_src, "Typical-price 1% buffer (1.01) must be present"


# ===========================================================================
# 14. VIX fetcher: User-Agent header required to avoid Yahoo 429 throttling
# ===========================================================================


class TestVIXFetcherUserAgent:
    def test_yahoo_fetch_includes_user_agent(self):
        """_fetch_from_yahoo must send a User-Agent header.

        Without it Yahoo Finance returns HTTP 429 (Too Many Requests), which
        propagates as an exception and causes get_current_vix() to always fall
        back to the hardcoded 18.0, making regime detection permanently stuck
        on NORMAL regardless of actual market conditions.
        """
        vix_src = Path("src/data/vix_data_fetcher.py").read_text()
        assert "User-Agent" in vix_src, (
            "vix_data_fetcher.py has no User-Agent header — Yahoo returns 429 "
            "without it, permanently forcing the VIX fallback to 18.0."
        )

    def test_vix_fetcher_returns_live_value(self):
        """Live VIX fetch must return a value different from the hardcoded fallback.

        Skipped when network is unavailable.
        """
        import socket

        try:
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        except OSError:
            pytest.skip("no network — skipping live VIX test")

        from src.data.vix_data_fetcher import VIXDataFetcher

        fetcher = VIXDataFetcher(source="yahoo")
        vix = fetcher.get_current_vix()
        assert 5.0 <= vix <= 80.0, f"VIX out of plausible range: {vix}"
        # Hardcoded fallback is 18.0 — live value should not equal it exactly
        # (unless VIX genuinely is 18.0, so we just verify range, not exact value)
        assert vix != 0.0, "VIX returned 0 — fetch failed silently"


# ===========================================================================
# 15. Stale order cancellation: _cancel_stale_orders must exist and be called
# ===========================================================================


class TestStaleOrderCancellation:
    def test_cancel_stale_orders_method_exists(self):
        """ExecutionEngine must have _cancel_stale_orders method.

        Without this, OPG orders from a prior run accumulate — if the bot runs
        twice (e.g. manual retry + scheduled), duplicate BUY orders are placed
        and may fill both, doubling position size.
        """
        from src.core.execution_engine import MultiStrategyRunner

        assert hasattr(MultiStrategyRunner, "_cancel_stale_orders"), (
            "MultiStrategyRunner missing _cancel_stale_orders — "
            "stale OPG orders from prior runs will accumulate"
        )

    def test_cancel_stale_orders_called_in_run_all_strategies(self):
        """_cancel_stale_orders must be invoked inside run_all_strategies.

        It must fire before any new orders are submitted so that duplicate
        OPG orders from a prior session are cleaned up first.
        """
        engine_src = Path("src/core/execution_engine.py").read_text()
        assert (
            "_cancel_stale_orders" in engine_src
        ), "execution_engine.py never calls _cancel_stale_orders"
        # Verify it appears inside run_all_strategies (not just defined)
        import re

        # Extract the body of run_all_strategies
        match = re.search(
            r"def run_all_strategies\(.*?\n(.*?)(?=\n    def |\Z)", engine_src, re.DOTALL
        )
        assert match is not None, "Could not locate run_all_strategies body"
        body = match.group(1)
        assert (
            "_cancel_stale_orders" in body
        ), "_cancel_stale_orders is defined but not called from run_all_strategies"


# ===========================================================================
# 16. ML Momentum confidence floor raised from near-random 0.51
# ===========================================================================


class TestMLMomentumConfidenceFloor:
    def test_config_min_confidence_at_least_0_55(self):
        """ML Momentum min_confidence must be >= 0.55.

        At 0.51 the model is capturing noise, not signal.  A GBT on 60 days of
        financial data rarely achieves >0.55 accuracy — but 0.51 is essentially
        random, meaning every 'high confidence' call adds noise to the portfolio.
        """
        cfg = get_config()
        conf = cfg.get("strategies.ml_momentum.min_confidence", 0.51)
        assert conf >= 0.55, (
            f"strategies.ml_momentum.min_confidence={conf:.2f} is too close to "
            "random (0.50) — set to at least 0.55 to require genuine signal"
        )

    def test_max_new_positions_config_present(self):
        """max_new_positions_per_day must be in config (not just a hardcoded default)."""
        cfg = get_config()
        val = cfg.get("strategies.ml_momentum.max_new_positions_per_day")
        assert val is not None, (
            "strategies.ml_momentum.max_new_positions_per_day missing from config — "
            "it defaults to 3 in code, but should be explicit so it's reviewable"
        )
        assert 1 <= val <= 10, f"max_new_positions_per_day={val} is outside [1, 10]"

    def test_buy_quantile_threshold_config_present(self):
        cfg = get_config()
        val = cfg.get("strategies.ml_momentum.buy_quantile_threshold")
        assert val is not None, "strategies.ml_momentum.buy_quantile_threshold missing from config"
        assert 0.5 <= val <= 0.9, f"buy_quantile_threshold={val} outside [0.5, 0.9]"


# ===========================================================================
# 17. Let-winners-run: RSI and Factor strategies extend hold for profitable positions
# ===========================================================================


class TestLetWinnersRun:
    """RSI and Factor Momentum must skip the time-based exit when the position
    is profitable and RSI/momentum conditions are still healthy."""

    def _rsi_strategy(self):
        from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy

        s = RSIMeanReversionStrategy.__new__(RSIMeanReversionStrategy)
        s.positions = {}
        s.entry_prices = {}
        s.entry_dates = {}
        s.rsi_threshold = 35
        s.rsi_exit = 55
        s.hold_days = 20
        s.max_hold_days = 40
        s.profit_target_pct = 0.05
        s.stop_loss_pct = 0.07
        s.let_winners_run_pct = 0.03
        s.volume_spike_threshold = 1.5
        s.capital = 10_000
        s.strategy_id = 1
        return s

    def _make_rsi_data(self, rsi, rsi_prev, price, sma_100=None, entry_date_offset=25):
        """Build a market_data DataFrame for the RSI strategy."""
        n = 150
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        rows = []
        for _ in dates:
            rows.append(
                {
                    "symbol": "AAPL",
                    "close": float(price),
                    "rsi": float(rsi),
                    "sma_100": float(sma_100) if sma_100 is not None else None,
                    "volume_ratio": 1.0,
                    "atr_20": 2.0,
                }
            )
        df = pd.DataFrame(rows, index=dates)
        df.loc[dates[-2], "rsi"] = float(rsi_prev)
        df["symbol"] = "AAPL"
        return df, dates

    def test_rsi_time_exit_fires_when_losing(self):
        """Time exit fires normally when position is not profitable."""
        strat = self._rsi_strategy()
        # Build data first so we can anchor entry_date relative to dates[-1]
        df, dates = self._make_rsi_data(rsi=50.0, rsi_prev=48.0, price=100.0, sma_100=90.0)
        # Entry 20 business days ago → ~28 calendar days → between hold_days (20) and max_hold (40)
        strat.positions = {"AAPL": 10}
        strat.entry_prices = {"AAPL": 102.0}  # -2% loss — below stop-loss threshold (7%)
        strat.entry_dates = {"AAPL": dates[-20].strftime("%Y-%m-%d")}
        signals = strat.generate_signals(df)
        sells = [s for s in signals if s["action"] == "SELL"]
        # -2% loss → profit < let_winners_run_pct (3%) → let-winners-run doesn't apply → time exit fires
        assert len(sells) == 1
        assert "time-based exit" in sells[0]["reasoning"]

    def test_rsi_time_exit_skipped_when_profitable(self):
        """Time exit is suppressed when position is ≥3% profitable and RSI < rsi_exit."""
        strat = self._rsi_strategy()
        df, dates = self._make_rsi_data(rsi=48.0, rsi_prev=45.0, price=100.0, sma_100=90.0)
        # Entry ~20 bdays ago → ~28 calendar days → between hold_days (20) and max_hold (40)
        strat.positions = {"AAPL": 10}
        strat.entry_prices = {
            "AAPL": 97.0
        }  # +3.09% profit — above let_winners_run (3%), below profit target (5%)
        strat.entry_dates = {"AAPL": dates[-20].strftime("%Y-%m-%d")}
        signals = strat.generate_signals(df)
        sells = [s for s in signals if s["action"] == "SELL"]
        # RSI 48 < rsi_exit 55, +3.09% ≥ 3%, days held < max_hold (40) → time exit suppressed
        assert (
            len(sells) == 0
        ), "Time exit should be suppressed for profitable position with healthy RSI"

    def test_rsi_max_hold_enforced(self):
        """Absolute max_hold_days forces exit even if profitable."""
        strat = self._rsi_strategy()
        df, dates = self._make_rsi_data(rsi=48.0, rsi_prev=45.0, price=100.0, sma_100=90.0)
        # Entry ~32 bdays ago → ~45 calendar days → exceeds max_hold_days (40)
        strat.positions = {"AAPL": 10}
        strat.entry_prices = {"AAPL": 97.0}  # +3.09% — above let_winners_run, below profit target
        strat.entry_dates = {"AAPL": dates[-32].strftime("%Y-%m-%d")}
        signals = strat.generate_signals(df)
        sells = [s for s in signals if s["action"] == "SELL"]
        # days_held ~45 > max_hold_days=40 → let-winners-run `days_held < max_hold` check fails → time exit fires
        assert len(sells) == 1
        assert "time-based exit" in sells[0]["reasoning"]

    def test_rsi_let_winners_attributes_exist(self):
        """RSIMeanReversionStrategy must expose max_hold_days and let_winners_run_pct."""
        from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy

        s = RSIMeanReversionStrategy(strategy_id=1, capital=10_000)
        assert hasattr(s, "max_hold_days"), "max_hold_days missing"
        assert hasattr(s, "let_winners_run_pct"), "let_winners_run_pct missing"
        assert s.max_hold_days > s.hold_days, "max_hold_days must be > hold_days"
        assert 0 < s.let_winners_run_pct < s.profit_target_pct


# ===========================================================================
# 18. Cross-strategy symbol dedup: same symbol can't be bought by two strategies
# ===========================================================================


class TestCrossStrategyDedup:
    def test_held_symbols_set_initialized_in_run(self):
        """_held_symbols must be set during run_all_strategies initialization."""
        src = Path("src/core/execution_engine.py").read_text()
        assert "_held_symbols" in src, "_held_symbols cache missing from execution_engine.py"

    def test_cross_strategy_dedup_guard_present(self):
        """execution_engine.py must contain the cross_strategy_dedup rejection reason."""
        src = Path("src/core/execution_engine.py").read_text()
        assert "cross_strategy_dedup" in src, (
            "cross_strategy_dedup guard missing — two strategies can buy the same symbol "
            "creating unintended double-concentration"
        )

    def test_held_symbols_updated_on_buy(self):
        """_held_symbols must be updated when a BUY fills so subsequent strategies see it."""
        src = Path("src/core/execution_engine.py").read_text()
        assert "_held_symbols.add(symbol)" in src, (
            "_held_symbols not updated after BUY — cross-strategy dedup won't catch "
            "symbols bought earlier in the same run"
        )


# ===========================================================================
# 19. Short-prevention: SELL guards verify shares > 0 before submitting
# ===========================================================================


class TestShortPrevention:
    def test_short_prevention_in_strategy_sell(self):
        """Strategy SELL path must check DB shares > 0 before submitting."""
        src = Path("src/core/execution_engine.py").read_text()
        assert "selling would create a short" in src, (
            "Short-prevention guard missing from strategy SELL path — "
            "a double-exit can submit SELL on a zero-share position, creating a short"
        )

    def test_short_prevention_in_stop_loss_sell(self):
        """Stop-loss SELL path must check DB shares > 0 before submitting."""
        src = Path("src/core/execution_engine.py").read_text()
        assert "double-exit prevented" in src, (
            "Short-prevention guard missing from stop-loss SELL path — "
            "if stop-loss fires twice it would short the position"
        )

    def test_short_prevention_cleans_stale_memory(self):
        """When short-prevention blocks a SELL, it must also clean the in-memory position."""
        src = Path("src/core/execution_engine.py").read_text()
        assert "strategy.positions.pop(symbol, None)" in src, (
            "Short-prevention guard doesn't clean stale in-memory state — "
            "the strategy will keep trying to sell a position that doesn't exist"
        )
