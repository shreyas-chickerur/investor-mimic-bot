#!/usr/bin/env python3
"""
Simplified Email Template - Daily Digest
Quick summary with call-to-action, detailed info on approval page
"""
from datetime import datetime
from typing import List, Dict, Optional


def generate_simple_approval_email(
    trades: List[Dict],
    portfolio_value: float,
    cash: float,
    approval_url: str,
    request_id: str,
    market_data: Optional[Dict] = None,
    current_holdings: Optional[List[Dict]] = None
) -> str:
    """
    Generate simplified email - daily digest style
    Comprehensive info moved to approval page
    """
    
    total_investment = sum(t['value'] for t in trades)
    
    # Quick market summary
    market_summary = ""
    if market_data:
        market_summary = "<br>".join([
            f"{name}: {data['value']} ({data['change_pct']:+.2f}%)"
            for name, data in list(market_data.items())[:3]
        ])
    
    # Holdings count
    holdings_count = len(current_holdings) if current_holdings else 0
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Daily Trading Digest | Action Required</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        </style>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f7fa; line-height: 1.6;">
        
        <div style="max-width: 700px; margin: 0 auto; background-color: #ffffff;">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #0A2540 0%, #1a3a5c 50%, #2a4a6c 100%); padding: 40px 32px; text-align: center;">
                <div style="color: #D4AF37; font-size: 12px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px;">Daily Trading Digest</div>
                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">Trade Approval Required</h1>
                <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0 0; font-size: 14px;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>

            <!-- Alert Banner -->
            <div style="background: linear-gradient(90deg, #F57C00 0%, #FB8C00 100%); padding: 16px 24px;">
                <div style="text-align: center;">
                    <div style="color: #ffffff; font-weight: 600; font-size: 14px; margin-bottom: 4px;">⚠️ Action Required</div>
                    <div style="color: rgba(255,255,255,0.95); font-size: 13px;">{len(trades)} trade{'s' if len(trades) != 1 else ''} pending your approval • Expires in 24 hours</div>
                </div>
            </div>

            <!-- Quick Summary -->
            <div style="padding: 32px 24px; background: linear-gradient(to bottom, #f8f9fb 0%, #ffffff 100%);">
                <h2 style="color: #0A2540; margin: 0 0 20px 0; font-size: 20px; font-weight: 700;">Today's Summary</h2>
                
                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">
                <tr>
                    <div style="background: #ffffff; padding: 16px; border-radius: 8px; border: 2px solid #e1e8ed;">
                        <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 6px;">Portfolio</div>
                        <div style="color: #0A2540; font-size: 22px; font-weight: 700;">${portfolio_value:,.0f}</div>
                    </div>
                    <div style="background: #ffffff; padding: 16px; border-radius: 8px; border: 2px solid #e1e8ed;">
                        <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 6px;">Cash Available</div>
                        <div style="color: #0A2540; font-size: 22px; font-weight: 700;">${cash:,.0f}</div>
                    </div>
                    <div style="background: #ffffff; padding: 16px; border-radius: 8px; border: 2px solid #e1e8ed;">
                        <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 6px;">Pending Trades</div>
                        <div style="color: #F57C00; font-size: 22px; font-weight: 700;">{len(trades)}</div>
                    </div>
                    <div style="background: #ffffff; padding: 16px; border-radius: 8px; border: 2px solid #e1e8ed;">
                        <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 6px;">Current Holdings</div>
                        <div style="color: #0A2540; font-size: 22px; font-weight: 700;">{holdings_count}</div>
                    </div>
                </div>

                <div style="background: #f8f9fb; padding: 16px; border-radius: 8px; border-left: 4px solid #0A2540; margin-bottom: 20px;">
                    <div style="color: #0A2540; font-weight: 600; font-size: 13px; margin-bottom: 8px;">Market Overview</div>
                    <div style="color: #64748b; font-size: 13px; line-height: 1.6;">{market_summary}</div>
                </div>

                <div style="background: #fff8e1; padding: 16px; border-radius: 8px; border-left: 4px solid #F57C00;">
                    <div style="color: #E65100; font-weight: 600; font-size: 13px; margin-bottom: 8px;">Proposed Investment</div>
                    <div style="color: #0A2540; font-size: 20px; font-weight: 700; margin-bottom: 4px;">${total_investment:,.2f}</div>
                    <div style="color: #64748b; font-size: 12px;">{(total_investment/cash*100):.1f}% of available cash</div>
                </div>
            </div>

            <!-- Proposed Trades List -->
            <div style="padding: 24px; background-color: #ffffff; border-top: 1px solid #e1e8ed;">
                <h3 style="color: #0A2540; margin: 0 0 16px 0; font-size: 16px; font-weight: 700;">Trades Awaiting Approval</h3>
                <div style="display: grid; gap: 10px;">
    """
    
    for trade in trades:
        symbol = trade['symbol']
        shares = trade['shares']
        value = trade['value']
        action = trade.get('action', 'BUY').upper()
        action_color = "#2E7D32" if action == "BUY" else "#C62828"
        action_bg = "#E8F5E9" if action == "BUY" else "#FFEBEE"
        
        html += f"""
                    <div style="background: #f8f9fb; padding: 12px 16px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <div style="background: #0A2540; color: #D4AF37; padding: 4px 12px; border-radius: 4px; font-weight: 700; font-size: 14px;">{symbol}</div>
                            <div style="background: {action_bg}; color: {action_color}; padding: 3px 10px; border-radius: 4px; font-weight: 700; font-size: 12px; border: 1px solid {action_color};">{action}</div>
                            <div style="color: #64748b; font-size: 13px;">{shares} shares</div>
                        </div>
                        <div style="color: #0A2540; font-weight: 600; font-size: 15px;">${value:,.2f}</div>
                    </div>
        """
    
    html += f"""
                </div>
            </div>

            <!-- Call to Action -->
            <div style="padding: 40px 24px; text-align: center; background: linear-gradient(to bottom, #f8f9fb 0%, #ffffff 100%); border-top: 3px solid #D4AF37;">
                <div style="margin-bottom: 20px;">
                    <div style="color: #0A2540; font-size: 18px; font-weight: 700; margin-bottom: 8px;">Ready to Review?</div>
                    <p style="color: #64748b; font-size: 14px; margin: 0; line-height: 1.6;">
                        Click below to view detailed analysis, market data, your holdings,<br/>
                        news, and reasoning for each trade before making your decision.
                    </p>
                </div>
                
                <a href="{approval_url}?request_id={request_id}" 
                   style="display: inline-block; background: linear-gradient(135deg, #0A2540 0%, #1a3a5c 100%); color: #ffffff; padding: 18px 48px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 12px rgba(10, 37, 64, 0.3); border: 2px solid #D4AF37;">
                    📋 Review & Approve Trades
                </a>
                
                <div style="margin-top: 20px; padding: 16px; background: rgba(245, 124, 0, 0.1); border-radius: 8px; border-left: 4px solid #F57C00;">
                    <p style="color: #E65100; font-size: 13px; margin: 0; font-weight: 500;">
                        ⏱️ Comprehensive analysis available on approval page • Request expires in 24 hours
                    </p>
                </div>
            </div>

            <!-- Footer -->
            <div style="background-color: #0A2540; padding: 24px; text-align: center; border-top: 3px solid #D4AF37;">
                <div style="color: #D4AF37; font-size: 14px; font-weight: 600; margin-bottom: 6px; letter-spacing: 1px;">AUTOMATED TRADING SYSTEM</div>
                <p style="color: rgba(255,255,255,0.6); font-size: 11px; margin: 0;">Request ID: {request_id} • {datetime.now().strftime('%I:%M %p ET')}</p>
            </div>

        </div>
    </body>
    </html>
    """
    
    return html
