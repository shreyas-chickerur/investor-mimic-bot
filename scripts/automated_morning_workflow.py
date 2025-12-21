#!/usr/bin/env python3
"""
Automated Morning Workflow
Runs all strategies, executes trades, and sends summary email
NO MANUAL APPROVAL - Fully automated for multi-strategy testing
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from strategy_runner import StrategyRunner
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

def send_summary_email(rankings, total_signals):
    """Send daily summary email"""
    email_username = os.getenv('EMAIL_USERNAME')
    email_password = os.getenv('EMAIL_PASSWORD')
    email_to = os.getenv('EMAIL_TO')
    
    if not email_username or not email_password or not email_to:
        print("⚠️  Email not configured, skipping summary email")
        return
    
    # Generate email HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f5f7fa; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 30px; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
            .rankings {{ margin: 20px 0; }}
            .rank-item {{ padding: 15px; background: #f8f9fb; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }}
            .rank-number {{ font-size: 24px; font-weight: bold; width: 40px; }}
            .rank-1 {{ color: #ffd700; }}
            .rank-2 {{ color: #c0c0c0; }}
            .rank-3 {{ color: #cd7f32; }}
            .strategy-name {{ font-weight: 600; color: #2d3748; flex: 1; }}
            .return {{ font-weight: 700; font-size: 18px; }}
            .positive {{ color: #48bb78; }}
            .negative {{ color: #f56565; }}
            .stats {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin: 20px 0; }}
            .stat-card {{ background: #f8f9fb; padding: 15px; border-radius: 8px; text-align: center; }}
            .stat-label {{ color: #718096; font-size: 12px; text-transform: uppercase; margin-bottom: 5px; }}
            .stat-value {{ color: #2d3748; font-size: 24px; font-weight: 700; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Daily Strategy Summary</h1>
                <p>{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-label">Signals Generated</div>
                    <div class="stat-value">{total_signals}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Strategies Active</div>
                    <div class="stat-value">5</div>
                </div>
            </div>
            
            <h2 style="color: #2d3748; margin: 30px 0 15px 0;">🏆 Current Rankings</h2>
            <div class="rankings">
    """
    
    for i, strategy in enumerate(rankings, 1):
        rank_class = f"rank-{i}" if i <= 3 else ""
        return_class = "positive" if strategy['return_pct'] >= 0 else "negative"
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        
        html += f"""
                <div class="rank-item">
                    <div class="rank-number {rank_class}">{medal}</div>
                    <div class="strategy-name">{strategy['name']}</div>
                    <div class="return {return_class}">{strategy['return_pct']:+.2f}%</div>
                </div>
        """
    
    html += f"""
            </div>
            
            <div style="margin-top: 30px; padding: 20px; background: #e6fffa; border-radius: 8px; border-left: 4px solid #38b2ac;">
                <p style="margin: 0; color: #234e52; font-weight: 600;">✅ All trades executed automatically</p>
                <p style="margin: 5px 0 0 0; color: #2c7a7b; font-size: 14px;">View detailed performance at your admin dashboard</p>
            </div>
            
            <div style="margin-top: 20px; text-align: center; padding: 20px; background: #f8f9fb; border-radius: 8px;">
                <p style="margin: 0; color: #718096; font-size: 14px;">Dashboard: http://localhost:5000</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send email
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"📊 Daily Strategy Summary - {datetime.now().strftime('%b %d')}"
    msg['From'] = email_username
    msg['To'] = email_to
    
    html_part = MIMEText(html, 'html')
    msg.attach(html_part)
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(email_username, email_password)
            server.send_message(msg)
        print(f"✅ Summary email sent to {email_to}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


def main():
    """Main automated workflow"""
    print("=" * 80)
    print(f"AUTOMATED MORNING WORKFLOW - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Initialize runner
    runner = StrategyRunner()
    
    # Load strategies
    print("\n📊 Loading strategies...")
    runner.initialize_strategies(total_capital=100000)
    
    # Fetch market data
    print("\n📈 Fetching market data...")
    market_data = runner.fetch_market_data()
    print(f"✅ Loaded data for {len(market_data)} symbols")
    
    # Run all strategies with automatic execution
    print("\n🤖 Executing all strategies (AUTOMATIC MODE)...")
    signals = runner.run_all_strategies(market_data, execute_trades=True)
    
    # Get rankings
    rankings = runner.get_rankings()
    
    # Send summary email
    print("\n📧 Sending summary email...")
    send_summary_email(rankings, len(signals))
    
    # Show summary
    print("\n" + "=" * 80)
    print("DAILY SUMMARY")
    print("=" * 80)
    
    print("\n🏆 Current Rankings:")
    for i, strategy in enumerate(rankings, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}️⃣"
        print(f"{medal} {strategy['name']}: {strategy['return_pct']:+.2f}% "
              f"(${strategy['portfolio_value']:,.0f})")
    
    print(f"\n📊 Total Signals: {len(signals)}")
    print(f"✅ All trades executed automatically")
    print(f"📧 Summary email sent")
    print(f"📈 View dashboard: http://localhost:5000")
    
    print("\n✅ Automated workflow complete!")


if __name__ == '__main__':
    main()
