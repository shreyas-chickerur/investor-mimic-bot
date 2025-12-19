# 🧪 Testing Guide - Investor Mimic Bot

**Comprehensive Testing Documentation**

---

## 📋 Test Organization

Tests are organized by type into separate folders:

```
tests/
├── unit/              # Unit tests for individual modules
├── functional/        # Functional tests for workflows
├── integration/       # Integration tests for system components
└── performance/       # Performance and load tests
```

---

## 🎯 Test Types

### **Unit Tests** (`tests/unit/`)
Test individual modules and functions in isolation.

**Coverage:**
- `test_cache.py` - Cache functionality
- `test_validators.py` - Data validation
- `test_paper_trading.py` - Paper trading engine
- `test_execution_phase5_planner.py` - Execution planning
- `test_strategy_phase4.py` - Strategy logic

**Run:** `make test-unit`

### **Functional Tests** (`tests/functional/`)
Test complete workflows and user scenarios.

**Coverage:**
- `test_advanced_features.py` - Advanced feature workflows
- `test_approval_integration.py` - Approval workflow
- `test_selective_approval.py` - Selective approval logic

**Run:** `make test-functional`

### **Integration Tests** (`tests/integration/`)
Test how components work together.

**Coverage:**
- `test_integration.py` - Cache, validation, paper trading, database, end-to-end workflows

**Run:** `make test-integration`

### **Performance Tests** (`tests/performance/`)
Test system performance and efficiency.

**Coverage:**
- `test_cache_performance.py` - Cache performance
- `test_async_performance.py` - Async processing speedup

**Run:** `make test-performance`

---

## 🚀 Running Tests

### **All Tests**
```bash
make test
# or
python3 -m pytest tests/ -v
```

### **By Type**
```bash
make test-unit              # Unit tests only
make test-functional        # Functional tests only
make test-integration       # Integration tests only
make test-performance       # Performance tests only
```

### **With Coverage**
```bash
make test-coverage
# Generates HTML report in htmlcov/index.html
```

### **Quick Tests**
```bash
make test-quick
# Runs unit tests only, stops on first failure
```

### **Specific Test File**
```bash
python3 -m pytest tests/unit/test_cache.py -v
```

### **Specific Test**
```bash
python3 -m pytest tests/unit/test_cache.py::TestCache::test_set_and_get -v
```

---

## 📊 Test Coverage

### **Current Coverage**
- **Services:** Core business logic
- **Backtesting:** Backtest engine and strategies
- **ML:** Machine learning models
- **Utils:** Utility modules (cache, validators, etc.)

### **Coverage Goals**
- **Target:** 80%+ overall coverage
- **Critical paths:** 90%+ coverage
- **New features:** Must include tests

### **Viewing Coverage**
```bash
make test-coverage
open htmlcov/index.html
```

---

## ✅ Test Requirements

### **For New Features**
1. **Unit tests** for all new functions/classes
2. **Integration tests** if feature interacts with other components
3. **Performance tests** if feature affects performance
4. **Documentation** of test scenarios

### **Test Quality Standards**
- ✅ Tests must be independent (no dependencies between tests)
- ✅ Tests must be repeatable (same result every time)
- ✅ Tests must be fast (unit tests < 1s each)
- ✅ Tests must have clear assertions
- ✅ Tests must have descriptive names

---

## 🔧 Writing Tests

### **Unit Test Template**
```python
"""
Unit Tests for Module Name

Brief description of what's being tested.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from module_to_test import ClassToTest


class TestClassName:
    """Unit tests for ClassName."""
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        obj = ClassToTest()
        result = obj.method()
        assert result == expected_value
    
    def test_error_handling(self):
        """Test error handling."""
        obj = ClassToTest()
        with pytest.raises(ExpectedError):
            obj.method_that_should_fail()
```

### **Integration Test Template**
```python
"""
Integration Tests for Feature

Tests how components work together.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from component1 import Component1
from component2 import Component2


class TestFeatureIntegration:
    """Integration tests for feature."""
    
    def test_end_to_end_workflow(self):
        """Test complete workflow."""
        # Setup
        comp1 = Component1()
        comp2 = Component2()
        
        # Execute
        result1 = comp1.process()
        result2 = comp2.process(result1)
        
        # Verify
        assert result2.is_valid()
```

### **Performance Test Template**
```python
"""
Performance Tests for Module

Tests performance and efficiency.
"""

import pytest
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from module_to_test import function_to_test


class TestPerformance:
    """Performance tests."""
    
    def test_execution_time(self):
        """Test execution completes within time limit."""
        start = time.time()
        
        function_to_test()
        
        elapsed = time.time() - start
        assert elapsed < 1.0  # Should complete in under 1 second
```

---

## 🐛 Debugging Tests

### **Run with Verbose Output**
```bash
python3 -m pytest tests/ -v -s
```

### **Run with Debugging**
```bash
python3 -m pytest tests/ -v --pdb
```

### **Run Specific Test with Print Statements**
```bash
python3 -m pytest tests/unit/test_cache.py::TestCache::test_set_and_get -v -s
```

### **Show Test Duration**
```bash
python3 -m pytest tests/ -v --durations=10
```

---

## 🔄 Continuous Integration

Tests run automatically on:
- **Every push** to any branch
- **Every pull request**
- **Before deployment**

### **CI Requirements**
- All tests must pass
- Code coverage must be maintained
- No linting errors

---

## 📝 Best Practices

### **DO:**
- ✅ Write tests before or with code (TDD)
- ✅ Test edge cases and error conditions
- ✅ Use descriptive test names
- ✅ Keep tests simple and focused
- ✅ Mock external dependencies
- ✅ Clean up after tests (fixtures)

### **DON'T:**
- ❌ Test implementation details
- ❌ Write tests that depend on each other
- ❌ Use sleep() for timing (use mocks)
- ❌ Test external APIs directly (use mocks)
- ❌ Commit failing tests
- ❌ Skip tests without good reason

---

## 🎯 Test Fixtures

### **Using Fixtures**
```python
import pytest

@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {"key": "value"}

def test_with_fixture(sample_data):
    """Test using fixture."""
    assert sample_data["key"] == "value"
```

### **Common Fixtures**
```python
@pytest.fixture
def mock_database():
    """Mock database connection."""
    # Setup
    db = MockDatabase()
    yield db
    # Teardown
    db.close()

@pytest.fixture
def sample_portfolio():
    """Sample portfolio for testing."""
    return {
        "AAPL": 100,
        "MSFT": 50,
        "GOOGL": 25
    }
```

---

## 📊 Test Metrics

### **Key Metrics**
- **Test Count:** 58+ tests
- **Coverage:** 80%+ target
- **Execution Time:** < 30 seconds for all tests
- **Pass Rate:** 100% required

### **Monitoring**
```bash
# Run tests with timing
python3 -m pytest tests/ -v --durations=0

# Generate coverage report
make test-coverage

# Check test count
python3 -m pytest tests/ --collect-only
```

---

## 🔗 Related Commands

```bash
# Format code before testing
make format

# Run linting
make lint

# Run all quality checks
make format lint test

# Quick development cycle
make test-quick format lint
```

---

## ✅ Summary

**Test Organization:**
- ✅ Tests organized by type (unit/functional/integration/performance)
- ✅ Clear naming conventions
- ✅ Comprehensive coverage

**Running Tests:**
- ✅ Multiple test commands available
- ✅ Coverage reporting
- ✅ Performance testing

**Quality Standards:**
- ✅ 80%+ coverage target
- ✅ All tests must pass
- ✅ Tests required for new features

---

*For more information, see:*
- `Makefile` - All test commands
- `pytest.ini` - Pytest configuration
- `.github/workflows/ci.yml` - CI/CD configuration
