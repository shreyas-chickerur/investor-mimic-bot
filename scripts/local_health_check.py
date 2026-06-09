#!/usr/bin/env python3
"""Quick local health check — called by `make check-health`."""
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ok = True

# DB existence and tables
if Path("trading.db").exists():
    with sqlite3.connect("trading.db", timeout=5) as c:
        tables = {
            r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    required = {"trades", "positions", "order_intents", "broker_state"}
    missing = required - tables
    if missing:
        print(f"❌ DB tables missing: {missing}")
        ok = False
    else:
        print("✅ DB: all required tables present")
else:
    print("⚠️  trading.db not found (run make setup to initialise)")

# Data freshness
data = Path("data/training_data.csv")
if data.exists():
    age = (datetime.now() - datetime.fromtimestamp(data.stat().st_mtime)).total_seconds() / 3600
    icon = "✅" if age < 48 else "⚠️ "
    print(f"{icon} Market data: {age:.0f}h old")
else:
    print("⚠️  training_data.csv not found (run make update-data)")

# API key presence
for var in ("ALPACA_API_KEY", "ALPHA_VANTAGE_API_KEY"):
    if os.getenv(var):
        print(f"✅ {var} set")
    else:
        print(f"⚠️  {var} not set (source .env or export manually)")

# ML model freshness
model = Path("data/ml_model.pkl")
if model.exists():
    age = (datetime.now() - datetime.fromtimestamp(model.stat().st_mtime)).total_seconds() / 86400
    icon = "✅" if age < 7 else "⚠️ "
    print(f"{icon} ML model: {age:.0f} days old")
else:
    print("ℹ️  ML model not cached (will train on first run)")

sys.exit(0 if ok else 1)
