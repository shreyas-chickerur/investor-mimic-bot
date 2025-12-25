# Phase 5 Signal Injection - Critical Blocker

**Status:** ⚠️ BLOCKED - Attribute initialization not persisting in file

## Problem

The `self.signal_injection_enabled` attribute initialization code is being added via edits but not persisting in the actual file. Multiple edit attempts have failed.

## Evidence

1. Edit tool reports success and shows updated view with lines 78-85 containing initialization
2. Actual file read shows lines 78-86 do NOT contain the initialization code
3. Error persists: `'MultiStrategyRunner' object has no attribute 'signal_injection_enabled'`

## Root Cause

File edits are not being saved/persisted. Possible causes:
- File locking issue
- Edit tool bug
- Python bytecode caching preventing reload

## Required Fix

The following code MUST be added between lines 76-78 in `src/multi_strategy_main.py`:

```python
# Line 76: self.trading_client = TradingClient(api_key, secret_key, paper=self.paper_mode)
# Line 77: (blank)
# INSERT HERE:
        # PHASE 5 VALIDATION: Signal injection for non-zero path proof
        self.signal_injection_enabled = os.getenv('PHASE5_SIGNAL_INJECTION', 'false').lower() == 'true'
        if self.signal_injection_enabled:
            if not self.paper_mode:
                raise ValueError("Signal injection requires ALPACA_PAPER=true")
            logger.warning("=" * 80)
            logger.warning("PHASE5_SIGNAL_INJECTION ENABLED - VALIDATION ONLY")
            logger.warning("=" * 80)
        
# Line 78: # Get account info - CRITICAL FIX: Use portfolio value, not just cash
```

## Manual Intervention Required

User needs to manually add the above code to the file, or I need to use a different approach (write entire file, not incremental edits).

## Alternative Approach

Create a minimal test script to verify signal injection works independently, then integrate once proven.
