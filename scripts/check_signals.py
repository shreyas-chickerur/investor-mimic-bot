#!/usr/bin/env python3
"""Preview today's signals without executing trades — called by `make signals-check`."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

os.environ['DRY_RUN'] = 'true'

from src.core.execution_engine import MultiStrategyRunner

runner = MultiStrategyRunner()
market_data = runner.load_market_data()
strategies = runner.initialize_strategies()

if market_data is None or len(market_data) == 0:
    print("\n⚠️  No market data available — run `make update-data` first")
    sys.exit(0)

as_of = market_data.index.max().date() if hasattr(market_data.index, 'max') else 'N/A'
print(f"\n{'='*60}")
print(f"  SIGNAL CHECK — {as_of}")
print(f"{'='*60}")

total_buys = total_sells = 0
for s in strategies:
    signals = s.generate_signals(market_data)
    buys  = [x for x in signals if x.get('action') == 'BUY']
    sells = [x for x in signals if x.get('action') == 'SELL']
    total_buys += len(buys)
    total_sells += len(sells)
    status = '✅' if (buys or sells) else '⚪'
    print(f"\n{status} {s.name}: {len(buys)} buys, {len(sells)} sells")
    for sig in buys[:3]:
        conf = sig.get('confidence', 0)
        reason = sig.get('reasoning', '')[:70]
        print(f"   BUY  {sig['symbol']:6s}  conf={conf:.2f}  {reason}")
    for sig in sells[:2]:
        reason = sig.get('reasoning', '')[:70]
        print(f"   SELL {sig['symbol']:6s}  {reason}")

print(f"\n{'='*60}")
print(f"  Total: {total_buys} buys, {total_sells} sells")
print(f"{'='*60}\n")
