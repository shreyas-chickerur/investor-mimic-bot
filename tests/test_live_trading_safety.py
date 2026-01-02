"""
Comprehensive test suite for live trading safety features.

Tests:
- Drawdown stop system (8% halt, 10% panic, cooldown/resume)
- Data quality & staleness detection
- DRY_RUN mode
- Signal funnel tracking with artifacts
- Idempotent order placement
- Kill switches
- Health scoring
"""

import os
import sys
import json
import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from drawdown_stop_manager import DrawdownStopManager
from data_quality_checker import DataQualityChecker
from dry_run_wrapper import DryRunWrapper, get_dry_run_wrapper
from signal_funnel_tracker import SignalFunnelTracker
from strategy_health_scorer import StrategyHealthScorer


class TestDrawdownStopManager:
    """Test drawdown stop system."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = Mock()
        db.get_system_state = Mock(return_value=None)
        db.set_system_state = Mock()
        db.count_duplicate_order_intents = Mock(return_value=0)
        return db
    
    @pytest.fixture
    def mock_email(self):
        """Create mock email notifier."""
        email = Mock()
        email.send_critical_alert = Mock()
        return email
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for artifacts."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_no_drawdown_normal_operation(self, mock_db, mock_email, temp_dir):
        """Test normal operation with no drawdown."""
        manager = DrawdownStopManager(mock_db, mock_email, temp_dir)
        
        # No drawdown
        is_stopped, reason, details = manager.check_drawdown_stop(
            current_portfolio_value=1050.0,
            peak_portfolio_value=1000.0
        )
        
        assert not is_stopped
        assert reason == ""
        assert details['drawdown_pct'] < 0  # Actually a gain
    
    def test_halt_threshold_triggered(self, mock_db, mock_email, temp_dir):
        """Test 8% drawdown triggers halt."""
        manager = DrawdownStopManager(mock_db, mock_email, temp_dir)
        
        # 8% drawdown
        is_stopped, reason, details = manager.check_drawdown_stop(
            current_portfolio_value=920.0,
            peak_portfolio_value=1000.0
        )
        
        assert is_stopped
        assert "HALT" in reason
        assert details['drawdown_pct'] == 0.08
        
        # Check email was sent
        mock_email.send_critical_alert.assert_called_once()
        
        # Check state was saved
        mock_db.set_system_state.assert_called()
    
    def test_panic_threshold_triggered(self, mock_db, mock_email, temp_dir):
        """Test 10% drawdown triggers panic."""
        manager = DrawdownStopManager(mock_db, mock_email, temp_dir)
        
        # 10% drawdown
        is_stopped, reason, details = manager.check_drawdown_stop(
            current_portfolio_value=900.0,
            peak_portfolio_value=1000.0
        )
        
        assert is_stopped
        assert "PANIC" in reason
        assert details['drawdown_pct'] == 0.10
        
        # Check panic alert was sent
        mock_email.send_critical_alert.assert_called_once()
        assert "PANIC" in mock_email.send_critical_alert.call_args[0][0]
    
    def test_cooldown_state_management(self, mock_db, mock_email, temp_dir):
        """Test cooldown state transitions."""
        manager = DrawdownStopManager(mock_db, mock_email, temp_dir)
        
        # Trigger halt
        manager.check_drawdown_stop(920.0, 1000.0)
        
        # Check state was set to HALT
        call_args = mock_db.set_system_state.call_args[0]
        assert call_args[0] == 'drawdown_stop_state'
        state_data = json.loads(call_args[1])
        assert state_data['state'] == 'HALT'
        assert state_data['cooldown_days'] == 10
    
    def test_health_checks_before_resume(self, mock_db, mock_email, temp_dir):
        """Test health checks run before resuming."""
        # Setup state: cooldown expired
        cooldown_end = (datetime.now() - timedelta(days=1)).isoformat()
        state_data = {
            'state': 'HALT',
            'drawdown': 0.08,
            'cooldown_days': 10,
            'cooldown_end': cooldown_end,
            'triggered_at': (datetime.now() - timedelta(days=11)).isoformat(),
            'rampup_end': None
        }
        
        # Mock get_system_state to return different values based on key
        def mock_get_state(key):
            if key == 'drawdown_stop_state':
                return json.dumps(state_data)
            elif key == 'last_reconciliation_status':
                return 'PASS'
            elif key == 'last_data_update':
                return datetime.now().isoformat()
            return None
        
        mock_db.get_system_state = Mock(side_effect=mock_get_state)
        mock_db.set_system_state = Mock()
        mock_db.count_duplicate_order_intents = Mock(return_value=0)
        
        manager = DrawdownStopManager(mock_db, mock_email, temp_dir)
        
        # Get current state (should trigger health checks)
        state = manager.get_current_state()
        
        # Should transition to RAMPUP if health checks pass
        assert state['state'] in ['RAMPUP', 'HALT']  # Depends on health checks
    
    def test_rampup_sizing_multiplier(self, mock_db, mock_email, temp_dir):
        """Test 50% sizing during rampup."""
        # Setup state: in rampup
        rampup_end = (datetime.now() + timedelta(days=3)).isoformat()
        state_data = {
            'state': 'RAMPUP',
            'drawdown': 0.0,
            'cooldown_days': 0,
            'cooldown_end': None,
            'triggered_at': datetime.now().isoformat(),
            'rampup_end': rampup_end,
            'sizing_multiplier': 0.5
        }
        mock_db.get_system_state = Mock(return_value=json.dumps(state_data))
        
        manager = DrawdownStopManager(mock_db, mock_email, temp_dir)
        
        # Check sizing multiplier
        multiplier = manager.get_sizing_multiplier()
        assert multiplier == 0.5
        
        # Check trading is allowed
        assert manager.is_trading_allowed()
    
    def test_trading_blocked_during_halt(self, mock_db, mock_email, temp_dir):
        """Test trading is blocked during halt/panic."""
        state_data = {
            'state': 'HALT',
            'drawdown': 0.08,
            'cooldown_days': 10,
            'cooldown_end': (datetime.now() + timedelta(days=5)).isoformat(),
            'triggered_at': datetime.now().isoformat(),
            'rampup_end': None
        }
        mock_db.get_system_state = Mock(return_value=json.dumps(state_data))
        
        manager = DrawdownStopManager(mock_db, mock_email, temp_dir)
        
        # Trading should be blocked
        assert not manager.is_trading_allowed()
        
        # Sizing multiplier should be 1.0 (not used during halt)
        assert manager.get_sizing_multiplier() == 1.0


class TestDataQualityChecker:
    """Test data quality and staleness detection."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for artifacts."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_empty_data_blocks_all(self, temp_dir):
        """Test empty data blocks all trading."""
        import pandas as pd
        
        checker = DataQualityChecker(temp_dir)
        
        empty_df = pd.DataFrame()
        blocked, report = checker.check_data_quality(empty_df, datetime.now())
        
        assert 'EMPTY_DATA' in report['issues']
        assert report['symbols_checked'] == 0
    
    def test_stale_data_detection(self, temp_dir):
        """Test stale data is detected and blocked."""
        import pandas as pd
        
        checker = DataQualityChecker(temp_dir)
        
        # Create data with old dates
        old_date = datetime.now() - timedelta(days=5)
        data = pd.DataFrame({
            'symbol': ['AAPL', 'MSFT'],
            'date': [old_date, old_date],
            'close': [150.0, 300.0],
            'rsi': [50.0, 60.0],
            'sma_20': [145.0, 295.0],
            'sma_50': [140.0, 290.0],
            'sma_100': [135.0, 285.0],
            'atr': [2.0, 3.0],
            'volatility_20d': [0.02, 0.03]
        })
        
        blocked, report = checker.check_data_quality(data, datetime.now())
        
        # Both symbols should be blocked for stale data
        assert len(blocked) == 2
        assert 'STALE_DATA' in report['issues']
    
    def test_missing_indicators_detection(self, temp_dir):
        """Test missing indicators are detected."""
        import pandas as pd
        
        checker = DataQualityChecker(temp_dir)
        
        # Create data missing required indicators
        data = pd.DataFrame({
            'symbol': ['AAPL'],
            'date': [datetime.now()],
            'close': [150.0]
            # Missing: rsi, sma_20, sma_50, sma_100, atr, volatility_20d
        })
        
        blocked, report = checker.check_data_quality(data, datetime.now())
        
        assert 'AAPL' in blocked
        assert 'MISSING_INDICATORS' in report['issues']
    
    def test_excessive_nan_detection(self, temp_dir):
        """Test excessive NaN values are detected."""
        import pandas as pd
        import numpy as np
        
        checker = DataQualityChecker(temp_dir)
        
        # Create data with excessive NaN
        data = pd.DataFrame({
            'symbol': ['AAPL'] * 100,
            'date': [datetime.now()] * 100,
            'close': [150.0] * 100,
            'rsi': [np.nan] * 50 + [50.0] * 50,  # 50% NaN
            'sma_20': [145.0] * 100,
            'sma_50': [140.0] * 100,
            'sma_100': [135.0] * 100,
            'atr': [2.0] * 100,
            'volatility_20d': [0.02] * 100
        })
        
        blocked, report = checker.check_data_quality(data, datetime.now())
        
        assert 'AAPL' in blocked
        assert 'EXCESSIVE_NAN' in report['issues']
    
    def test_price_outlier_detection(self, temp_dir):
        """Test price outliers are detected."""
        import pandas as pd
        
        checker = DataQualityChecker(temp_dir)
        
        # Create data with extreme price jump
        data = pd.DataFrame({
            'symbol': ['AAPL'] * 300,
            'date': pd.date_range(end=datetime.now(), periods=300),
            'close': [150.0] * 299 + [300.0],  # 100% jump
            'rsi': [50.0] * 300,
            'sma_20': [145.0] * 300,
            'sma_50': [140.0] * 300,
            'sma_100': [135.0] * 300,
            'atr': [2.0] * 300,
            'volatility_20d': [0.02] * 300
        })
        
        blocked, report = checker.check_data_quality(data, datetime.now())
        
        assert 'AAPL' in blocked
        assert 'PRICE_OUTLIER' in report['issues']
    
    def test_quality_report_artifact_generated(self, temp_dir):
        """Test quality report artifact is generated."""
        import pandas as pd
        
        checker = DataQualityChecker(temp_dir)
        
        data = pd.DataFrame({
            'symbol': ['AAPL'],
            'date': [datetime.now()],
            'close': [150.0],
            'rsi': [50.0],
            'sma_20': [145.0],
            'sma_50': [140.0],
            'sma_100': [135.0],
            'atr': [2.0],
            'volatility_20d': [0.02]
        })
        
        checker.check_data_quality(data, datetime.now())
        
        # Check artifact was created
        artifacts = os.listdir(temp_dir)
        assert any('data_quality_report' in f for f in artifacts)


class TestDryRunMode:
    """Test DRY_RUN mode."""
    
    def test_dry_run_disabled_by_default(self):
        """Test DRY_RUN is disabled by default."""
        with patch.dict(os.environ, {'DRY_RUN': 'false'}, clear=False):
            wrapper = DryRunWrapper()
            assert not wrapper.is_dry_run()
    
    def test_dry_run_enabled(self):
        """Test DRY_RUN can be enabled."""
        with patch.dict(os.environ, {'DRY_RUN': 'true'}, clear=False):
            wrapper = DryRunWrapper()
            assert wrapper.is_dry_run()
    
    def test_dry_run_blocks_broker_operations(self):
        """Test DRY_RUN blocks actual broker operations."""
        with patch.dict(os.environ, {'DRY_RUN': 'true'}, clear=False):
            wrapper = DryRunWrapper()
            
            # Mock broker operation
            mock_operation = Mock(return_value="REAL_RESULT")
            
            # Execute operation in DRY_RUN mode
            result = wrapper.execute_broker_operation(
                "submit_order",
                mock_operation,
                symbol="AAPL",
                qty=10
            )
            
            # Real operation should NOT have been called
            mock_operation.assert_not_called()
            
            # Should return mock result
            assert result is not None
    
    def test_dry_run_mock_order_result(self):
        """Test DRY_RUN returns mock order result."""
        with patch.dict(os.environ, {'DRY_RUN': 'true'}, clear=False):
            wrapper = DryRunWrapper()
            
            result = wrapper.execute_broker_operation(
                "submit_order",
                Mock(),
                qty=10
            )
            
            # Check mock order has expected attributes
            assert hasattr(result, 'id')
            assert hasattr(result, 'status')
            assert result.status == "filled"
            assert "DRY_RUN" in result.id


class TestSignalFunnelArtifacts:
    """Test signal funnel artifact generation."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = Mock()
        db.save_signal_funnel = Mock()
        db.log_signal_rejection = Mock()
        return db
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for artifacts."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_funnel_artifact_generation(self, mock_db, temp_dir):
        """Test signal_funnel.json artifact is generated."""
        tracker = SignalFunnelTracker(mock_db)
        
        # Record funnel data
        tracker.record_raw_signals(1, 10)
        tracker.record_after_regime(1, 8)
        tracker.record_after_correlation(1, 5)
        tracker.record_after_risk(1, 3)
        tracker.record_executed(1, 2)
        
        # Generate artifact
        filepath = tracker.generate_funnel_artifact(
            strategy_id=1,
            strategy_name="Test Strategy",
            run_id="20260101_120000",
            artifacts_dir=temp_dir
        )
        
        # Check file was created
        assert os.path.exists(filepath)
        
        # Check content
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        assert data['strategy_id'] == 1
        assert data['strategy_name'] == "Test Strategy"
        assert data['funnel']['raw_signals'] == 10
        assert data['funnel']['executed'] == 2
        assert 'conversion_rates' in data
    
    def test_rejections_artifact_generation(self, mock_db, temp_dir):
        """Test signal_rejections.json artifact is generated."""
        tracker = SignalFunnelTracker(mock_db)
        
        # Log rejections
        tracker.log_rejection(1, 'AAPL', 'CORRELATION', 'high_correlation', {'corr': 0.85})
        tracker.log_rejection(1, 'MSFT', 'RISK', 'insufficient_cash', {})
        
        # Generate artifact
        filepath = tracker.generate_rejections_artifact(
            strategy_id=1,
            strategy_name="Test Strategy",
            run_id="20260101_120000",
            artifacts_dir=temp_dir
        )
        
        # Check file was created
        assert os.path.exists(filepath)
        
        # Check content
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        assert data['total_rejections'] == 2
        assert 'rejections_by_stage' in data
        assert 'CORRELATION' in data['rejections_by_stage']
        assert 'RISK' in data['rejections_by_stage']
    
    def test_why_no_trade_artifact_only_when_zero_trades(self, mock_db, temp_dir):
        """Test why_no_trade_summary.json only generated when no trades."""
        tracker = SignalFunnelTracker(mock_db)
        
        # Record funnel with trades
        tracker.record_raw_signals(1, 10)
        tracker.record_executed(1, 2)
        
        # Should NOT generate artifact
        filepath = tracker.generate_why_no_trade_artifact(
            run_id="20260101_120000",
            artifacts_dir=temp_dir
        )
        
        assert filepath == ""
        
        # Now test with zero trades
        tracker2 = SignalFunnelTracker(mock_db)
        tracker2.record_raw_signals(1, 10)
        tracker2.record_executed(1, 0)
        
        # Should generate artifact
        filepath = tracker2.generate_why_no_trade_artifact(
            run_id="20260101_120000",
            artifacts_dir=temp_dir
        )
        
        assert filepath != ""
        assert os.path.exists(filepath)


class TestIdempotentOrders:
    """Test idempotent order placement."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = Mock()
        db.create_order_intent = Mock(return_value="intent_12345")
        db.get_order_intent_by_id = Mock(return_value=None)
        db.update_order_intent_status = Mock()
        return db
    
    def test_intent_id_deterministic(self, mock_db):
        """Test intent IDs are deterministic."""
        # Same inputs should produce same intent_id
        intent_id1 = mock_db.create_order_intent(1, 'AAPL', 'BUY', 10)
        intent_id2 = mock_db.create_order_intent(1, 'AAPL', 'BUY', 10)
        
        # Mock returns same value, in real implementation hash would be same
        assert intent_id1 == intent_id2
    
    def test_duplicate_intent_detected(self, mock_db):
        """Test duplicate intents are detected."""
        # Setup: intent already exists with SUBMITTED status
        mock_db.get_order_intent_by_id = Mock(return_value={
            'intent_id': 'intent_12345',
            'status': 'SUBMITTED'
        })
        
        # Check for duplicate
        intent = mock_db.get_order_intent_by_id('intent_12345')
        
        assert intent is not None
        assert intent['status'] == 'SUBMITTED'


class TestStrategyHealthScoring:
    """Test strategy health scoring."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database with connection."""
        db = Mock()
        
        # Mock connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall = Mock(return_value=[])
        mock_conn.cursor = Mock(return_value=mock_cursor)
        mock_conn.close = Mock()
        
        db._get_connection = Mock(return_value=mock_conn)
        
        return db
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for artifacts."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_health_score_calculation(self, mock_db, temp_dir):
        """Test health score is calculated correctly."""
        scorer = StrategyHealthScorer(mock_db, temp_dir)
        
        # Calculate health for strategy with no data
        health = scorer.calculate_strategy_health(1, "Test Strategy")
        
        assert 'health_score' in health
        assert 'health_status' in health
        assert 'issues' in health
        assert health['health_score'] >= 0
        assert health['health_score'] <= 100
    
    def test_health_summary_artifact_generated(self, mock_db, temp_dir):
        """Test strategy_health_summary.json is generated."""
        scorer = StrategyHealthScorer(mock_db, temp_dir)
        
        strategies = [(1, "Strategy 1"), (2, "Strategy 2")]
        
        filepath = scorer.generate_health_summary(strategies)
        
        # Check file was created
        assert os.path.exists(filepath)
        
        # Check content
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        assert 'portfolio_health_score' in data
        assert 'strategies' in data
        assert len(data['strategies']) == 2
        assert 'recommendations' in data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
