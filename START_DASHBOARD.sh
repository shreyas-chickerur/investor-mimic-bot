#!/bin/bash
# Quick script to start the admin dashboard

cd "$(dirname "$0")"
echo "🚀 Starting Strategy Dashboard..."
python3 src/strategy_dashboard.py
