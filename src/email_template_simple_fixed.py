#!/usr/bin/env python3
"""
Simplified Email Template - Email Client Compatible
Uses HTML tables instead of CSS grid for better rendering in email clients
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
    Email-client compatible with HTML tables
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
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f5f7fa;">
        
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f5f7fa;">
        <tr>
            <td align="center" style="padding: 20px 0;">
                
                <!-- Main Container -->
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; max-width: 600px;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #0A2540 0%, #1a3a5c 100%); padding: 40px 32px; text-align: center;">
                            <div style="color: #D4AF37; font-size: 12px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px;">Daily Trading Digest</div>
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700;">Trade Approval Required</h1>
                            <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0 0; font-size: 14px;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
                        </td>
                    </tr>

                    <!-- Alert Banner -->
                    <tr>
                        <td style="background: linear-gradient(90deg, #F57C00 0%, #FB8C00 100%); padding: 16px 24px; text-align: center;">
                            <div style="color: #ffffff; font-weight: 600; font-size: 14px; margin-bottom: 4px;">⚠️ Action Required</div>
                            <div style="color: rgba(255,255,255,0.95); font-size: 13px;">{len(trades)} trade{'s' if len(trades) != 1 else ''} pending your approval • Expires in 24 hours</div>
                        </td>
                    </tr>

                    <!-- Summary Section -->
                    <tr>
                        <td style="padding: 32px 24px; background-color: #f8f9fb;">
                            <h2 style="color: #0A2540; margin: 0 0 20px 0; font-size: 20px; font-weight: 700;">Today's Summary</h2>
                            
                            <!-- Summary Cards - 2x2 Grid using Tables -->
                            <table width="100%" cellpadding="6" cellspacing="0" border="0">
                                <tr>
                                    <td width="50%" style="padding: 6px;">
                                        <table width="100%" cellpadding="16" cellspacing="0" border="0" style="background: #ffffff; border-radius: 8px; border: 2px solid #e1e8ed;">
                                            <tr>
                                                <td>
                                                    <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 6px;">Portfolio</div>
                                                    <div style="color: #0A2540; font-size: 22px; font-weight: 700;">${portfolio_value:,.0f}</div>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                    <td width="50%" style="padding: 6px;">
                                        <table width="100%" cellpadding="16" cellspacing="0" border="0" style="background: #ffffff; border-radius: 8px; border: 2px solid #e1e8ed;">
                                            <tr>
                                                <td>
                                                    <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 6px;">Cash Available</div>
                                                    <div style="color: #0A2540; font-size: 22px; font-weight: 700;">${cash:,.0f}</div>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <tr>
                                    <td width="50%" style="padding: 6px;">
                                        <table width="100%" cellpadding="16" cellspacing="0" border="0" style="background: #ffffff; border-radius: 8px; border: 2px solid #e1e8ed;">
                                            <tr>
                                                <td>
                                                    <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 6px;">Pending Trades</div>
                                                    <div style="color: #F57C00; font-size: 22px; font-weight: 700;">{len(trades)}</div>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                    <td width="50%" style="padding: 6px;">
                                        <table width="100%" cellpadding="16" cellspacing="0" border="0" style="background: #ffffff; border-radius: 8px; border: 2px solid #e1e8ed;">
                                            <tr>
                                                <td>
                                                    <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 6px;">Current Holdings</div>
                                                    <div style="color: #0A2540; font-size: 22px; font-weight: 700;">{holdings_count}</div>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- Market Overview -->
                            <table width="100%" cellpadding="16" cellspacing="0" border="0" style="margin-top: 20px; background: #f8f9fb; border-radius: 8px; border-left: 4px solid #0A2540;">
                                <tr>
                                    <td>
                                        <div style="color: #0A2540; font-weight: 600; font-size: 13px; margin-bottom: 8px;">Market Overview</div>
                                        <div style="color: #64748b; font-size: 13px; line-height: 1.6;">{market_summary}</div>
                                    </td>
                                </tr>
                            </table>

                            <!-- Proposed Investment -->
                            <table width="100%" cellpadding="16" cellspacing="0" border="0" style="margin-top: 20px; background: #fff8e1; border-radius: 8px; border-left: 4px solid #F57C00;">
                                <tr>
                                    <td>
                                        <div style="color: #E65100; font-weight: 600; font-size: 13px; margin-bottom: 8px;">Proposed Investment</div>
                                        <div style="color: #0A2540; font-size: 20px; font-weight: 700; margin-bottom: 4px;">${total_investment:,.2f}</div>
                                        <div style="color: #64748b; font-size: 12px;">{(total_investment/cash*100):.1f}% of available cash</div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Trades List -->
                    <tr>
                        <td style="padding: 24px; background-color: #ffffff; border-top: 1px solid #e1e8ed;">
                            <h3 style="color: #0A2540; margin: 0 0 16px 0; font-size: 16px; font-weight: 700;">Trades Awaiting Approval</h3>
    """
    
    for trade in trades:
        symbol = trade['symbol']
        shares = trade['shares']
        value = trade['value']
        action = trade.get('action', 'BUY').upper()
        action_color = "#2E7D32" if action == "BUY" else "#C62828"
        action_bg = "#E8F5E9" if action == "BUY" else "#FFEBEE"
        
        html += f"""
                            <table width="100%" cellpadding="12" cellspacing="0" border="0" style="margin-bottom: 10px; background: #f8f9fb; border-radius: 6px;">
                                <tr>
                                    <td width="70%">
                                        <table cellpadding="0" cellspacing="0" border="0">
                                            <tr>
                                                <td style="background: #0A2540; color: #D4AF37; padding: 4px 12px; border-radius: 4px; font-weight: 700; font-size: 14px;">{symbol}</td>
                                                <td width="10"></td>
                                                <td style="background: {action_bg}; color: {action_color}; padding: 3px 10px; border-radius: 4px; font-weight: 700; font-size: 12px; border: 1px solid {action_color};">{action}</td>
                                                <td width="10"></td>
                                                <td style="color: #64748b; font-size: 13px;">{shares} shares</td>
                                            </tr>
                                        </table>
                                    </td>
                                    <td width="30%" align="right">
                                        <div style="color: #0A2540; font-weight: 600; font-size: 15px;">${value:,.2f}</div>
                                    </td>
                                </tr>
                            </table>
        """
    
    html += f"""
                        </td>
                    </tr>

                    <!-- Call to Action -->
                    <tr>
                        <td style="padding: 40px 24px; text-align: center; background-color: #f8f9fb; border-top: 3px solid #D4AF37;">
                            <div style="margin-bottom: 20px;">
                                <div style="color: #0A2540; font-size: 18px; font-weight: 700; margin-bottom: 8px;">Ready to Review?</div>
                                <p style="color: #64748b; font-size: 14px; margin: 0; line-height: 1.6;">
                                    Click below to view detailed analysis, market data, your holdings,<br/>
                                    news, and reasoning for each trade before making your decision.
                                </p>
                            </div>
                            
                            <table cellpadding="0" cellspacing="0" border="0" align="center">
                                <tr>
                                    <td style="background: linear-gradient(135deg, #0A2540 0%, #1a3a5c 100%); border-radius: 8px; border: 2px solid #D4AF37;">
                                        <a href="{approval_url}?request_id={request_id}" style="display: block; color: #ffffff; padding: 18px 48px; text-decoration: none; font-weight: 600; font-size: 16px;">
                                            📋 Review & Approve Trades
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <table width="100%" cellpadding="16" cellspacing="0" border="0" style="margin-top: 20px; background: rgba(245, 124, 0, 0.1); border-radius: 8px; border-left: 4px solid #F57C00;">
                                <tr>
                                    <td>
                                        <p style="color: #E65100; font-size: 13px; margin: 0; font-weight: 500;">
                                            ⏱️ Comprehensive analysis available on approval page • Request expires in 24 hours
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #0A2540; padding: 24px; text-align: center; border-top: 3px solid #D4AF37;">
                            <div style="color: #D4AF37; font-size: 14px; font-weight: 600; margin-bottom: 6px; letter-spacing: 1px;">AUTOMATED TRADING SYSTEM</div>
                            <p style="color: rgba(255,255,255,0.6); font-size: 11px; margin: 0;">Request ID: {request_id} • {datetime.now().strftime('%I:%M %p ET')}</p>
                        </td>
                    </tr>

                </table>
                
            </td>
        </tr>
        </table>
    </body>
    </html>
    """
    
    return html
