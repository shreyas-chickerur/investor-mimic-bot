#!/bin/bash
# Setup cron job for daily trading system execution

PROJECT_DIR="/Users/shreyaschickerur/CascadeProjects/investor-mimic-bot"
PYTHON_PATH="/Library/Frameworks/Python.framework/Versions/3.8/bin/python3"

# Create cron job entry
CRON_JOB="0 10 * * 1-5 cd $PROJECT_DIR && $PYTHON_PATH src/main.py >> logs/daily_run.log 2>&1"

# Check if cron job already exists
(crontab -l 2>/dev/null | grep -v "investor-mimic-bot"; echo "$CRON_JOB") | crontab -

echo "✅ Cron job configured:"
echo "   Schedule: 10:00 AM weekdays (Mon-Fri)"
echo "   Script: src/main.py"
echo "   Log: logs/daily_run.log"
echo ""
echo "To verify: crontab -l"
