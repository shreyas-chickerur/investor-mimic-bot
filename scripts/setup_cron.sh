#!/bin/bash
# Setup cron job for automated investing

# Add cron job (runs at 10 AM on weekdays)
(crontab -l 2>/dev/null; echo "0 10 * * 1-5 cd /Users/shreyaschickerur/CascadeProjects/investor-mimic-bot && /Library/Frameworks/Python.framework/Versions/3.8/bin/python3 scripts/test_approval_workflow.py >> logs/auto_invest_approval.log 2>&1") | crontab -

echo "✅ Cron job installed!"
echo ""
echo "The bot will now run automatically at 10 AM every weekday (Mon-Fri)"
echo ""
echo "To view your cron jobs:"
echo "  crontab -l"
echo ""
echo "To remove the cron job:"
echo "  crontab -r"
echo ""
echo "To view logs:"
echo "  tail -f logs/auto_invest_approval.log"
