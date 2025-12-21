#!/bin/bash
# Setup cron job for daily automated workflow

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Setting up daily cron job for automated trading workflow..."
echo ""
echo "This will run the automated workflow every weekday at 9:00 AM"
echo ""

# Create cron job entry
CRON_JOB="0 9 * * 1-5 cd $PROJECT_DIR && /usr/local/bin/python3 scripts/automated_morning_workflow.py >> logs/cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "automated_morning_workflow.py"; then
    echo "⚠️  Cron job already exists!"
    echo ""
    echo "Current cron jobs:"
    crontab -l | grep "automated_morning_workflow.py"
    echo ""
    read -p "Do you want to replace it? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
    # Remove old entry
    crontab -l | grep -v "automated_morning_workflow.py" | crontab -
fi

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Cron job added successfully!"
echo ""
echo "Schedule: Every weekday (Mon-Fri) at 9:00 AM"
echo "Command: $CRON_JOB"
echo ""
echo "📋 To view your cron jobs:"
echo "   crontab -l"
echo ""
echo "📋 To view logs:"
echo "   tail -f $PROJECT_DIR/logs/cron.log"
echo ""
echo "📋 To remove this cron job:"
echo "   crontab -e"
echo "   (then delete the line with 'automated_morning_workflow.py')"
echo ""
echo "✅ Automation complete! Workflow will run automatically every weekday at 9 AM."
