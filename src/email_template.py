#!/usr/bin/env python3
"""
Email Template for Trade Approval
Based on previous implementation with professional styling
"""
from datetime import datetime
from typing import List, Dict


def generate_approval_email(
    trades: List[Dict],
    portfolio_value: float,
    cash: float,
    approval_url: str,
    request_id: str
) -> str:
    """
    Generate HTML email for trade approval
    
    Args:
        trades: List of proposed trades with symbol, shares, price, value
        portfolio_value: Current portfolio value
        cash: Available cash
        approval_url: URL to approval page
        request_id: Unique request ID
    
    Returns:
        HTML email string
    """
    
    # Calculate totals
    total_investment = sum(t['value'] for t in trades)
    
    # Build trades table
    trades_html = ""
    for trade in trades:
        symbol = trade['symbol']
        shares = trade['shares']
        price = trade['price']
        value = trade['value']
        allocation = (value / portfolio_value * 100) if portfolio_value > 0 else 0
        
        trades_html += f"""
        <tr>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; font-weight: 600; color: #2c3e50; font-size: 15px;">{symbol}</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: right; color: #555;">{shares}</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: right; color: #555;">${price:.2f}</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: right; font-weight: 600; color: #2c3e50;">${value:,.2f}</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: right; color: #555;">{allocation:.1f}%</td>
        </tr>
        """
    
    # Complete HTML email
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Trade Approval Required</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8f9fa; line-height: 1.6;">
        
        <div style="max-width: 900px; margin: 20px auto; background-color: #ffffff; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-radius: 8px; overflow: hidden;">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #7e8ba3 100%); padding: 40px 32px; text-align: center; position: relative; overflow: hidden;">
                <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: url('data:image/svg+xml,%3Csvg width=\"100\" height=\"100\" xmlns=\"http://www.w3.org/2000/svg\"%3E%3Cpath d=\"M0 0h100v100H0z\" fill=\"none\"/%3E%3Cpath d=\"M0 50h100M50 0v100\" stroke=\"%23ffffff\" stroke-width=\"0.5\" opacity=\"0.1\"/%3E%3C/svg%3E') repeat; opacity: 0.3;"></div>
                <div style="position: relative; z-index: 1;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 32px; font-weight: 700; letter-spacing: -0.5px; text-shadow: 0 2px 4px rgba(0,0,0,0.2);">✋ Trade Approval Required</h1>
                    <p style="color: #e3f2fd; margin: 12px 0 0 0; font-size: 15px; font-weight: 500;">{datetime.now().strftime('%A, %B %d, %Y at %I:%M %p ET')}</p>
                </div>
            </div>

            <!-- Alert Banner -->
            <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 16px 24px; margin: 0;">
                <p style="color: #856404; margin: 0; font-size: 14px; font-weight: 600;">
                    ⚠️ Manual approval required before trades execute
                </p>
            </div>

            <!-- Portfolio Summary -->
            <div style="padding: 24px; border-bottom: 2px solid #f1f3f5;">
                <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 20px; font-weight: 700;">Portfolio Summary</h2>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
                    <div style="background: #f8f9fa; padding: 16px; border-radius: 8px; border: 1px solid #e9ecef;">
                        <div style="color: #546e7a; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 8px;">Portfolio Value</div>
                        <div style="color: #2c3e50; font-size: 20px; font-weight: 700;">${portfolio_value:,.2f}</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 16px; border-radius: 8px; border: 1px solid #e9ecef;">
                        <div style="color: #546e7a; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 8px;">Available Cash</div>
                        <div style="color: #2c3e50; font-size: 20px; font-weight: 700;">${cash:,.2f}</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 16px; border-radius: 8px; border: 1px solid #e9ecef;">
                        <div style="color: #546e7a; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 8px;">Proposed Investment</div>
                        <div style="color: #2c3e50; font-size: 20px; font-weight: 700;">${total_investment:,.2f}</div>
                    </div>
                </div>
            </div>

            <!-- Proposed Trades -->
            <div style="padding: 24px; border-bottom: 2px solid #f1f3f5;">
                <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 20px; font-weight: 700;">Proposed Trades ({len(trades)})</h2>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse; background-color: #ffffff;">
                        <thead>
                            <tr style="background-color: #f8f9fa;">
                                <th style="padding: 12px 16px; text-align: left; font-size: 12px; font-weight: 600; color: #546e7a; text-transform: uppercase; border-bottom: 2px solid #e0e0e0;">Symbol</th>
                                <th style="padding: 12px 16px; text-align: right; font-size: 12px; font-weight: 600; color: #546e7a; text-transform: uppercase; border-bottom: 2px solid #e0e0e0;">Shares</th>
                                <th style="padding: 12px 16px; text-align: right; font-size: 12px; font-weight: 600; color: #546e7a; text-transform: uppercase; border-bottom: 2px solid #e0e0e0;">Price</th>
                                <th style="padding: 12px 16px; text-align: right; font-size: 12px; font-weight: 600; color: #546e7a; text-transform: uppercase; border-bottom: 2px solid #e0e0e0;">Value</th>
                                <th style="padding: 12px 16px; text-align: right; font-size: 12px; font-weight: 600; color: #546e7a; text-transform: uppercase; border-bottom: 2px solid #e0e0e0;">Allocation</th>
                            </tr>
                        </thead>
                        <tbody>
                            {trades_html}
                        </tbody>
                        <tfoot>
                            <tr style="background-color: #f8f9fa; font-weight: 700;">
                                <td colspan="3" style="padding: 16px; text-align: right; color: #2c3e50; border-top: 2px solid #e0e0e0;">Total Investment:</td>
                                <td style="padding: 16px; text-align: right; color: #2c3e50; border-top: 2px solid #e0e0e0;">${total_investment:,.2f}</td>
                                <td style="padding: 16px; border-top: 2px solid #e0e0e0;"></td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>

            <!-- Action Buttons -->
            <div style="padding: 32px 24px; text-align: center; background-color: #f8f9fa;">
                <p style="color: #546e7a; font-size: 14px; margin: 0 0 20px 0;">
                    Click below to review and approve/reject these trades
                </p>
                <a href="{approval_url}?request_id={request_id}" 
                   style="display: inline-block; background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%); color: #ffffff; padding: 16px 48px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 12px rgba(33, 150, 243, 0.3); transition: all 0.3s;">
                    📋 Review Trades
                </a>
                <p style="color: #95a5a6; font-size: 12px; margin: 20px 0 0 0;">
                    Trades will not execute until you approve them
                </p>
            </div>

            <!-- Footer -->
            <div style="background-color: #2c3e50; padding: 24px; text-align: center;">
                <p style="color: #95a5a6; font-size: 12px; margin: 0;">Automated Trading System • Trade Approval</p>
                <p style="color: #7f8c8d; font-size: 11px; margin: 8px 0 0 0;">Request ID: {request_id}</p>
            </div>

        </div>
    </body>
    </html>
    """
    
    return html


def generate_approval_page_html(
    trades: List[Dict],
    portfolio_value: float,
    cash: float,
    request_id: str
) -> str:
    """
    Generate interactive approval page HTML
    
    Args:
        trades: List of proposed trades
        portfolio_value: Current portfolio value
        cash: Available cash
        request_id: Unique request ID
    
    Returns:
        HTML page string with approve/reject form
    """
    
    total_investment = sum(t['value'] for t in trades)
    
    # Build trade rows with radio buttons
    trades_html = ""
    for i, trade in enumerate(trades):
        symbol = trade['symbol']
        shares = trade['shares']
        price = trade['price']
        value = trade['value']
        allocation = (value / portfolio_value * 100) if portfolio_value > 0 else 0
        
        trades_html += f"""
        <tr>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; font-weight: 600; color: #2c3e50; font-size: 15px;">{symbol}</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: right; color: #555;">{shares}</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: right; color: #555;">${price:.2f}</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: right; font-weight: 600; color: #2c3e50;">${value:,.2f}</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: right; color: #555;">{allocation:.1f}%</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: center;">
                <div style="display: flex; gap: 12px; justify-content: center; align-items: center;">
                    <label style="display: flex; align-items: center; gap: 4px; cursor: pointer;">
                        <input type="radio" name="trade_{i}" value="approve" style="cursor: pointer; width: 18px; height: 18px;" checked>
                        <span style="color: #27ae60; font-weight: 600; font-size: 14px;">✓ Approve</span>
                    </label>
                    <label style="display: flex; align-items: center; gap: 4px; cursor: pointer;">
                        <input type="radio" name="trade_{i}" value="reject" style="cursor: pointer; width: 18px; height: 18px;">
                        <span style="color: #e74c3c; font-weight: 600; font-size: 14px;">✗ Reject</span>
                    </label>
                </div>
            </td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Trade Approval - Review Required</title>
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background-color: #f8f9fa;
            }}
            .container {{
                max-width: 1000px;
                margin: 40px auto;
                background-color: #ffffff;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                border-radius: 8px;
                overflow: hidden;
            }}
            .btn {{
                padding: 16px 32px;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 16px;
                cursor: pointer;
                transition: all 0.3s;
            }}
            .btn-approve {{
                background: linear-gradient(135deg, #27ae60 0%, #229954 100%);
                color: white;
                box-shadow: 0 4px 12px rgba(39, 174, 96, 0.3);
            }}
            .btn-approve:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 16px rgba(39, 174, 96, 0.4);
            }}
            .btn-reject {{
                background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
                color: white;
                box-shadow: 0 4px 12px rgba(231, 76, 60, 0.3);
            }}
            .btn-reject:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 16px rgba(231, 76, 60, 0.4);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #7e8ba3 100%); padding: 40px 32px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 32px; font-weight: 700;">Trade Approval Required</h1>
                <p style="color: #e3f2fd; margin: 12px 0 0 0; font-size: 15px;">{datetime.now().strftime('%A, %B %d, %Y at %I:%M %p ET')}</p>
            </div>

            <!-- Form -->
            <form id="approvalForm" method="POST" action="/api/approve">
                <input type="hidden" name="request_id" value="{request_id}">
                
                <!-- Portfolio Summary -->
                <div style="padding: 24px; border-bottom: 2px solid #f1f3f5;">
                    <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 20px; font-weight: 700;">Portfolio Summary</h2>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
                        <div style="background: #f8f9fa; padding: 16px; border-radius: 8px;">
                            <div style="color: #546e7a; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 8px;">Portfolio Value</div>
                            <div style="color: #2c3e50; font-size: 20px; font-weight: 700;">${portfolio_value:,.2f}</div>
                        </div>
                        <div style="background: #f8f9fa; padding: 16px; border-radius: 8px;">
                            <div style="color: #546e7a; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 8px;">Available Cash</div>
                            <div style="color: #2c3e50; font-size: 20px; font-weight: 700;">${cash:,.2f}</div>
                        </div>
                        <div style="background: #f8f9fa; padding: 16px; border-radius: 8px;">
                            <div style="color: #546e7a; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 8px;">Proposed Investment</div>
                            <div style="color: #2c3e50; font-size: 20px; font-weight: 700;">${total_investment:,.2f}</div>
                        </div>
                    </div>
                </div>

                <!-- Trades Table -->
                <div style="padding: 24px;">
                    <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 20px; font-weight: 700;">Review Trades ({len(trades)})</h2>
                    <div style="overflow-x: auto;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <thead>
                                <tr style="background-color: #f8f9fa;">
                                    <th style="padding: 12px 16px; text-align: left; font-size: 12px; font-weight: 600; color: #546e7a; text-transform: uppercase; border-bottom: 2px solid #e0e0e0;">Symbol</th>
                                    <th style="padding: 12px 16px; text-align: right; font-size: 12px; font-weight: 600; color: #546e7a; text-transform: uppercase; border-bottom: 2px solid #e0e0e0;">Shares</th>
                                    <th style="padding: 12px 16px; text-align: right; font-size: 12px; font-weight: 600; color: #546e7a; text-transform: uppercase; border-bottom: 2px solid #e0e0e0;">Price</th>
                                    <th style="padding: 12px 16px; text-align: right; font-size: 12px; font-weight: 600; color: #546e7a; text-transform: uppercase; border-bottom: 2px solid #e0e0e0;">Value</th>
                                    <th style="padding: 12px 16px; text-align: right; font-size: 12px; font-weight: 600; color: #546e7a; text-transform: uppercase; border-bottom: 2px solid #e0e0e0;">Allocation</th>
                                    <th style="padding: 12px 16px; text-align: center; font-size: 12px; font-weight: 600; color: #546e7a; text-transform: uppercase; border-bottom: 2px solid #e0e0e0;">Decision</th>
                                </tr>
                            </thead>
                            <tbody>
                                {trades_html}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Action Buttons -->
                <div style="padding: 32px 24px; text-align: center; background-color: #f8f9fa; border-top: 2px solid #e9ecef;">
                    <div style="display: flex; gap: 16px; justify-content: center; flex-wrap: wrap;">
                        <button type="button" onclick="approveAll()" class="btn btn-approve">
                            ✓ Approve All Trades
                        </button>
                        <button type="button" onclick="rejectAll()" class="btn btn-reject">
                            ✗ Reject All Trades
                        </button>
                    </div>
                    <p style="color: #7f8c8d; font-size: 12px; margin: 16px 0 0 0;">
                        Or select individual trades above and click Submit
                    </p>
                    <button type="submit" class="btn" style="margin-top: 16px; background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%); color: white;">
                        Submit Decisions
                    </button>
                </div>
            </form>
        </div>

        <script>
            function approveAll() {{
                document.querySelectorAll('input[value="approve"]').forEach(input => {{
                    input.checked = true;
                }});
            }}
            
            function rejectAll() {{
                document.querySelectorAll('input[value="reject"]').forEach(input => {{
                    input.checked = true;
                }});
            }}
            
            document.getElementById('approvalForm').addEventListener('submit', function(e) {{
                e.preventDefault();
                const formData = new FormData(this);
                
                // Show loading state
                const submitBtn = this.querySelector('button[type="submit"]');
                submitBtn.textContent = 'Processing...';
                submitBtn.disabled = true;
                
                // Submit form
                fetch('/api/approve', {{
                    method: 'POST',
                    body: formData
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        alert('Trades processed successfully!');
                        window.location.href = '/success';
                    }} else {{
                        alert('Error: ' + data.message);
                        submitBtn.textContent = 'Submit Decisions';
                        submitBtn.disabled = false;
                    }}
                }})
                .catch(error => {{
                    alert('Error submitting form: ' + error);
                    submitBtn.textContent = 'Submit Decisions';
                    submitBtn.disabled = false;
                }});
            }});
        </script>
    </body>
    </html>
    """
    
    return html
