# Manual Tests

This folder is for manual testing scripts that require human interaction or verification.

## Purpose

Manual tests are used for:
- Interactive testing that requires user input
- Visual verification of outputs
- Integration tests with external services
- Performance benchmarking
- Exploratory testing

## vs Automated Tests

- **Automated tests** (`tests/*.py`) - Run via `make test`, no human interaction
- **Manual tests** (`tests/manual/`) - Require human verification or interaction

## Usage

Manual tests should be documented and can be run individually:

```bash
python3 tests/manual/test_name.py
```

## Guidelines

1. Name files clearly: `test_<feature>_manual.py`
2. Include instructions at the top of each file
3. Document expected outcomes
4. Keep separate from automated test suite
