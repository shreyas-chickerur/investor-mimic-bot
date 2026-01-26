# Contributing to Investor Mimic Bot

Thank you for your interest in contributing to this industrial-grade quantitative trading system! This document provides guidelines and requirements for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Quality Standards](#code-quality-standards)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Commit Message Guidelines](#commit-message-guidelines)

## Code of Conduct

### Professional Standards

- Write production-quality code with proper error handling
- Document all public APIs and complex logic
- Follow existing code patterns and architecture
- Prioritize system stability over new features
- No breaking changes without explicit approval

### Prohibited Changes

❌ **DO NOT:**
- Modify core trading logic without extensive testing
- Change risk management parameters without justification
- Add dependencies without security review
- Commit secrets, API keys, or sensitive data
- Bypass pre-commit hooks or CI/CD checks
- Make changes that affect production trading without approval

## Getting Started

### Prerequisites

- Python 3.8-3.11
- Git
- Pre-commit hooks
- Understanding of quantitative trading concepts

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/shreyas-chickerur/investor-mimic-bot.git
cd investor-mimic-bot

# Install dependencies
make install

# Install pre-commit hooks
pre-commit install
pre-commit install --hook-type commit-msg

# Initialize database
make init

# Verify setup
make check-health
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

**Branch naming conventions:**
- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates
- `test/` - Test additions/improvements

### 2. Make Changes

- Follow code quality standards (see below)
- Write tests for new functionality
- Update documentation as needed
- Run pre-commit hooks: `pre-commit run --all-files`

### 3. Test Locally

```bash
# Run all tests
make test

# Run specific test types
make test-unit
make test-integration
make test-component

# Check code coverage
make test-coverage

# Verify system health
make check-health
make validate
make verify
```

### 4. Commit Changes

Follow conventional commit format:

```bash
git commit -m "type(scope): description"
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `test`: Test additions
- `docs`: Documentation
- `chore`: Maintenance tasks
- `perf`: Performance improvements
- `security`: Security fixes

**Examples:**
```bash
git commit -m "feat(strategies): add momentum strategy with ATR stops"
git commit -m "fix(risk): correct correlation filter edge case"
git commit -m "test(integration): add broker reconciliation tests"
```

### 5. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Code Quality Standards

### Python Style Guide

- **Line length:** 100 characters (enforced by Black)
- **Formatting:** Black (automatic)
- **Linting:** Ruff (replaces flake8, isort, pyupgrade)
- **Type hints:** Required for public APIs
- **Docstrings:** Required for all public functions/classes

### Code Quality Tools

All enforced via pre-commit hooks:

```bash
# Format code
black src/ tests/ scripts/

# Lint code
ruff check src/ tests/ scripts/ --fix

# Type check
mypy src/ --ignore-missing-imports

# Security scan
bandit -r src/

# Check dependencies
safety check
```

### Code Complexity Limits

- **Cyclomatic Complexity:** ≤ 10 per function
- **Maintainability Index:** ≥ 20
- **Function length:** ≤ 50 lines (guideline)
- **Class length:** ≤ 300 lines (guideline)

### Documentation Requirements

**All public functions must have docstrings:**

```python
def calculate_position_size(price: float, atr: float, risk_pct: float = 0.01) -> int:
    """
    Calculate position size based on ATR and risk percentage.
    
    Args:
        price: Current stock price
        atr: Average True Range (20-day)
        risk_pct: Portfolio risk percentage (default: 1%)
    
    Returns:
        Number of shares to purchase
    
    Raises:
        ValueError: If price or ATR is <= 0
    
    Example:
        >>> calculate_position_size(100.0, 2.5, 0.01)
        40
    """
    if price <= 0 or atr <= 0:
        raise ValueError("Price and ATR must be positive")
    
    risk_amount = portfolio_value * risk_pct
    shares = int(risk_amount / (atr * 2.5))
    return shares
```

## Testing Requirements

### Test Coverage

- **Minimum coverage:** 60% overall
- **Critical modules:** 80% coverage required
  - `src/core/`
  - `src/risk/`
  - `src/strategies/`

### Test Organization

```
tests/
├── unit/           # Unit tests (isolated, fast)
├── integration/    # Integration tests (multiple components)
├── component/      # Component tests (full subsystems)
└── functional/     # End-to-end tests (full workflows)
```

### Writing Tests

```python
import pytest
from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy

class TestRSIMeanReversion:
    """Test suite for RSI Mean Reversion strategy."""
    
    def test_generate_buy_signal_when_oversold(self):
        """Should generate buy signal when RSI < 40 and slope > 0."""
        strategy = RSIMeanReversionStrategy(strategy_id=1, capital=10000)
        market_data = create_test_data(rsi=35, rsi_slope=2.0)
        
        signals = strategy.generate_signals(market_data)
        
        assert len(signals) == 1
        assert signals[0]['action'] == 'BUY'
        assert signals[0]['confidence'] > 0
```

### Test Markers

```python
@pytest.mark.unit
def test_unit_function():
    pass

@pytest.mark.integration
def test_integration_flow():
    pass

@pytest.mark.slow
def test_expensive_operation():
    pass
```

Run specific markers:
```bash
pytest -m unit
pytest -m "not slow"
```

## Pull Request Process

### PR Requirements Checklist

Before submitting a PR, ensure:

- [ ] All tests pass (`make test`)
- [ ] Code coverage ≥ 60% (`make test-coverage`)
- [ ] Pre-commit hooks pass (`pre-commit run --all-files`)
- [ ] No security vulnerabilities (`bandit -r src/`)
- [ ] Documentation updated (if applicable)
- [ ] CHANGELOG.md updated (for user-facing changes)
- [ ] No merge conflicts with `main`
- [ ] PR description explains what/why/how

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally
```

### Review Process

1. **Automated Checks:** All CI/CD checks must pass
2. **Code Review:** Requires approval from CODEOWNERS
3. **Testing:** Reviewer must verify test coverage
4. **Documentation:** Reviewer checks documentation completeness
5. **Merge:** Squash and merge (maintains clean history)

### Review Timeline

- **Initial review:** Within 2 business days
- **Follow-up reviews:** Within 1 business day
- **Urgent fixes:** Same day (security/critical bugs)

## Commit Message Guidelines

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Examples

**Feature:**
```
feat(strategies): add volatility breakout strategy

- Implements Bollinger Band breakout detection
- Includes ATR-based position sizing
- Adds comprehensive unit tests

Closes #123
```

**Bug Fix:**
```
fix(risk): correct correlation filter edge case

Fixed issue where correlation filter would fail on
single-day data windows. Added validation and tests.

Fixes #456
```

**Breaking Change:**
```
feat(api)!: change signal schema format

BREAKING CHANGE: Signal schema now uses Pydantic models
instead of dictionaries. Update all strategy implementations.

Migration guide: docs/migration/v2.0.md
```

## Security

### Reporting Vulnerabilities

**DO NOT** create public issues for security vulnerabilities.

Email: security@example.com

Include:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Security Best Practices

- Never commit secrets or API keys
- Use environment variables for sensitive data
- Run `detect-secrets` before committing
- Keep dependencies up to date
- Review security scan results

## Questions?

- **General questions:** Open a GitHub Discussion
- **Bug reports:** Create a GitHub Issue
- **Feature requests:** Create a GitHub Issue with [Feature Request] tag
- **Security issues:** Email security@example.com

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
