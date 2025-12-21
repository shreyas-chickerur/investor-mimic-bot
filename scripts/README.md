# Scripts Directory

Utility and test scripts for the trading system.

## Setup Scripts

- **`setup_security.py`** - Initialize security system and create admin user

## Test Scripts

- **`test_email.py`** - Test basic email template generation
- **`test_real_email.py`** - Test email with real Alpaca data
- **`test_approval_page.py`** - Test approval page generation
- **`test_new_workflow.py`** - Test complete workflow (simplified email + comprehensive approval page)

## Usage

```bash
# Setup security
python3 scripts/setup_security.py

# Test email workflow
python3 scripts/test_new_workflow.py
```

All test scripts will generate HTML files that open automatically in your browser for preview.
