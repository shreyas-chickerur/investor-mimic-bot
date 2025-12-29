#!/usr/bin/env python3
"""
Generate Daily Email Digest

Reads the daily artifact JSON and generates a properly formatted HTML email
using the EmailNotifier class format.
"""
import sys
import json
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

def generate_email_body(artifact_path: str) -> str:
    """Generate HTML email body from artifact JSON"""
    
    with open(artifact_path) as f:
        data = json.load(f)
    
    # Extract data from artifact
    trades_data = data.get('trades', {})
    positions_data = data.get('positions', {})
    risk_data = data.get('risk', {})
    regime_data = data.get('regime', {})
    system_health = data.get('system_health', {})
    
    # Get trades list (handle both formats)
    placed_trades = trades_data.get('placed', []) if isinstance(trades_data, dict) else trades_data
    filled_trades = trades_data.get('filled', []) if isinstance(trades_data, dict) else []
    trades = filled_trades or placed_trades
    
    # Get positions list
    open_positions = positions_data.get('open', []) if isinstance(positions_data, dict) else positions_data
    
    # Extract metrics
    portfolio_value = risk_data.get('portfolio_value', 100000)
    cash = risk_data.get('cash', 0)
    daily_pnl = risk_data.get('daily_pnl', 0)
    portfolio_heat = risk_data.get('portfolio_heat', 0)
    
    # Reconciliation status
    recon_status = system_health.get('reconciliation_status', 'UNKNOWN')
    recon_emoji = '✅' if 'PASS' in recon_status else '❌'
    
    # Market regime
    regime_class = regime_data.get('classification', 'unknown').upper()
    vix = regime_data.get('vix', 'N/A')
    
    # Count trades by action
    buys = [t for t in trades if t.get('action') == 'BUY']
    sells = [t for t in trades if t.get('action') == 'SELL']
    
    # Build trades table
    trades_html = ""
    if trades:
        trades_html = "<table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>"
        trades_html += "<tr style='background: #f8f9fa; border-bottom: 2px solid #dee2e6;'>"
        trades_html += "<th style='padding: 10px; text-align: left;'>Action</th>"
        trades_html += "<th style='padding: 10px; text-align: left;'>Symbol</th>"
        trades_html += "<th style='padding: 10px; text-align: right;'>Shares</th>"
        trades_html += "<th style='padding: 10px; text-align: right;'>Price</th>"
        trades_html += "<th style='padding: 10px; text-align: left;'>Strategy</th>"
        trades_html += "</tr>"
        
        for trade in trades:
            action_color = '#28a745' if trade.get('action') == 'BUY' else '#dc3545'
            trades_html += f"<tr style='border-bottom: 1px solid #dee2e6;'>"
            trades_html += f"<td style='padding: 10px; color: {action_color}; font-weight: bold;'>{trade.get('action', 'N/A')}</td>"
            trades_html += f"<td style='padding: 10px;'>{trade.get('symbol', 'N/A')}</td>"
            trades_html += f"<td style='padding: 10px; text-align: right;'>{trade.get('shares', 0)}</td>"
            trades_html += f"<td style='padding: 10px; text-align: right;'>${trade.get('price', 0):.2f}</td>"
            trades_html += f"<td style='padding: 10px;'>{trade.get('strategy', 'N/A')}</td>"
            trades_html += "</tr>"
        
        trades_html += "</table>"
    else:
        trades_html = "<p style='color: #666; font-style: italic;'>No trades executed today</p>"
    
    # Build positions table
    positions_html = ""
    if open_positions:
        positions_html = "<table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>"
        positions_html += "<tr style='background: #f8f9fa; border-bottom: 2px solid #dee2e6;'>"
        positions_html += "<th style='padding: 10px; text-align: left;'>Symbol</th>"
        positions_html += "<th style='padding: 10px; text-align: right;'>Shares</th>"
        positions_html += "<th style='padding: 10px; text-align: right;'>Entry Price</th>"
        positions_html += "<th style='padding: 10px; text-align: right;'>Current Price</th>"
        positions_html += "<th style='padding: 10px; text-align: right;'>P&L</th>"
        positions_html += "</tr>"
        
        for pos in open_positions[:10]:
            entry_price = pos.get('entry_price', 0)
            current_price = pos.get('current_price', entry_price)
            shares = pos.get('shares', 0)
            pnl = (current_price - entry_price) * shares
            pnl_color = '#28a745' if pnl >= 0 else '#dc3545'
            
            positions_html += f"<tr style='border-bottom: 1px solid #dee2e6;'>"
            positions_html += f"<td style='padding: 10px;'>{pos.get('symbol', 'N/A')}</td>"
            positions_html += f"<td style='padding: 10px; text-align: right;'>{shares}</td>"
            positions_html += f"<td style='padding: 10px; text-align: right;'>${entry_price:.2f}</td>"
            positions_html += f"<td style='padding: 10px; text-align: right;'>${current_price:.2f}</td>"
            positions_html += f"<td style='padding: 10px; text-align: right; color: {pnl_color}; font-weight: bold;'>${pnl:+.2f}</td>"
            positions_html += "</tr>"
        
        positions_html += "</table>"
    else:
        positions_html = "<p style='color: #666; font-style: italic;'>No open positions</p>"
    
    # Build complete HTML email
    pnl_color = '#10b981' if daily_pnl >= 0 else '#dc3545'
    pnl_sign = '+' if daily_pnl >= 0 else ''
    
    html = f"""
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 900px; margin: 0 auto; background: #f5f5f5;">
    <!-- Header with blue gradient -->
    <div style="background: linear-gradient(135deg, #2c5282 0%, #4A90E2 100%); color: white; padding: 40px 30px; border-radius: 8px 8px 0 0;">
        <div style="color: #FFA500; font-size: 14px; font-weight: 700; letter-spacing: 2px; margin-bottom: 10px;">DAILY TRADING DIGEST</div>
        <h1 style="margin: 0; font-size: 32px; font-weight: 600;">Execution Complete</h1>
        <p style="margin: 8px 0 0 0; opacity: 0.95; font-size: 16px;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
    </div>
    
    <!-- Orange status bar -->
    <div style="background: #FF6B35; color: white; padding: 20px 30px; font-size: 15px;">
        <div style="margin-bottom: 5px;">{recon_emoji} <strong>Reconciliation: {recon_status}</strong></div>
        <div>{len(trades)} trades executed • Market regime: {regime_class} (VIX: {vix})</div>
    </div>
    
    <div style="padding: 30px; background: white;">
        <!-- Today's Summary Header -->
        <h2 style="color: #2c5282; font-size: 24px; margin-bottom: 25px; font-weight: 600;">Today's Summary</h2>
        
        <!-- Portfolio Overview Cards -->
        <div style="margin-bottom: 30px;">
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4A90E2;">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">PORTFOLIO</div>
                <div style="font-size: 36px; font-weight: 700; color: #2c5282;">${portfolio_value:,.0f}</div>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4A90E2;">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">CASH AVAILABLE</div>
                <div style="font-size: 36px; font-weight: 700; color: #2c5282;">${cash:,.0f}</div>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4A90E2;">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">PORTFOLIO HEAT</div>
                <div style="font-size: 36px; font-weight: 700; color: #2c5282;">{portfolio_heat:.1f}%</div>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; border-left: 4px solid {pnl_color};">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">DAILY P&L</div>
                <div style="font-size: 36px; font-weight: 700; color: {pnl_color};">{pnl_sign}${daily_pnl:.2f}</div>
            </div>
        </div>
        
        <!-- Trade Summary -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px; font-size: 20px; font-weight: 600;">
                Trades Executed ({len(trades)})
            </h2>
            <div style="margin: 15px 0;">
                <span style="background: #4A90E2; color: white; padding: 8px 16px; border-radius: 20px; margin-right: 10px; font-weight: 600; font-size: 14px;">
                    {len(buys)} Buys
                </span>
                <span style="background: #FF6B35; color: white; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 14px;">
                    {len(sells)} Sells
                </span>
            </div>
            {trades_html}
        </div>
        
        <!-- Current Positions -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px; font-size: 20px; font-weight: 600;">
                Current Positions ({len(open_positions)})
            </h2>
            {positions_html}
        </div>
        
        <!-- Footer -->
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 12px;">
            <p>View detailed logs and artifacts in GitHub Actions</p>
            <p style="margin-top: 10px;">This is an automated message from your trading system.</p>
        </div>
    </div>
</body>
</html>
"""
    
    return html

if __name__ == "__main__":
    # Get today's artifact path
    date = datetime.now().strftime('%Y-%m-%d')
    artifact_path = Path(f'artifacts/json/{date}.json')
    
    if not artifact_path.exists():
        print(f"❌ No artifact found for {date}")
        sys.exit(1)
    
    # Generate email HTML
    html = generate_email_body(str(artifact_path))
    
    # Save to file for workflow to use
    output_path = '/tmp/daily_email.html'
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"✅ Email HTML generated: {output_path}")
    sys.exit(0)
