"""
Interactive approval form template for bulk trade approval.

Provides a user-friendly form where users can review all trades at once,
select approve/reject for each, and submit all decisions together.
"""

from datetime import datetime
from typing import Dict, List


def get_approval_form_html(
    request_id: str,
    trades: List[Dict],
    total_investment: float,
    available_cash: float,
    cash_buffer: float,
    submit_url: str = "",
) -> str:
    """
    Generate interactive HTML form for bulk trade approval.

    Args:
        request_id: Approval request ID
        trades: List of proposed trades
        total_investment: Total investment amount
        available_cash: Available cash
        cash_buffer: Cash buffer amount
        submit_url: URL to submit the form

    Returns:
        HTML form string
    """

    # Build trades form rows
    trades_html = ""
    for i, trade in enumerate(trades):
        symbol = trade["symbol"]
        quantity = trade["quantity"]
        price = trade["estimated_price"]
        value = trade["estimated_value"]
        allocation = trade["allocation_pct"]

        trades_html += f"""
        <tr>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; font-weight: 600; color: #2c3e50; font-size: 15px;">{symbol}</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: right; color: #555;">{quantity:.2f}</td>
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

    # Interactive HTML form template
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Trade Approval Required</title>
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background-color: #f8f9fa;
            }}
            .container {{
                max-width: 900px;
                margin: 40px auto;
                background-color: #ffffff;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                border-radius: 8px;
                overflow: hidden;
            }}
            .header {{
                background-color: #2c3e50;
                padding: 32px;
                text-align: center;
            }}
            .header h1 {{
                color: #ffffff;
                margin: 0;
                font-size: 24px;
                font-weight: 600;
                letter-spacing: -0.5px;
            }}
            .header p {{
                color: #95a5a6;
                margin: 8px 0 0 0;
                font-size: 14px;
            }}
            .content {{
                padding: 40px;
            }}
            .summary-table {{
                width: 100%;
                border-collapse: collapse;
                background: #f8f9fa;
                border-radius: 6px;
                overflow: hidden;
                margin-bottom: 32px;
            }}
            .summary-table tr {{
                border-bottom: 1px solid #dee2e6;
            }}
            .summary-table tr:last-child {{
                border-bottom: none;
            }}
            .summary-table td {{
                padding: 16px 20px;
            }}
            .summary-label {{
                color: #495057;
                font-size: 14px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                width: 50%;
            }}
            .summary-value {{
                color: #2c3e50;
                font-size: 24px;
                font-weight: 700;
                text-align: right;
            }}
            .trades-table {{
                width: 100%;
                border-collapse: collapse;
                background: #ffffff;
                margin-bottom: 32px;
            }}
            .trades-table thead tr {{
                background-color: #f8f9fa;
                border-bottom: 2px solid #dee2e6;
            }}
            .trades-table th {{
                padding: 14px 16px;
                color: #495057;
                font-weight: 600;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .submit-section {{
                text-align: center;
                margin-top: 40px;
                padding-top: 32px;
                border-top: 2px solid #ecf0f1;
            }}
            .submit-button {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 16px 48px;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 18px;
                cursor: pointer;
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
                transition: all 0.3s ease;
            }}
            .submit-button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 16px rgba(102, 126, 234, 0.5);
            }}
            .submit-button:active {{
                transform: translateY(0);
            }}
            .helper-text {{
                color: #7f8c8d;
                font-size: 13px;
                margin-top: 16px;
            }}
            .footer {{
                background-color: #f8f9fa;
                padding: 24px;
                text-align: center;
                border-top: 1px solid #dee2e6;
            }}
            .footer p {{
                color: #7f8c8d;
                font-size: 12px;
                margin: 4px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">

            <!-- Header -->
            <div class="header">
                <h1>Trade Approval Required</h1>
                <p>InvestorMimic Bot</p>
            </div>

            <!-- Main Content -->
            <div class="content">

                <!-- Summary -->
                <table class="summary-table">
                    <tbody>
                        <tr>
                            <td class="summary-label">Total Investment</td>
                            <td class="summary-value">${total_investment:,.2f}</td>
                        </tr>
                        <tr>
                            <td class="summary-label">Number of Positions</td>
                            <td class="summary-value">{len(trades)}</td>
                        </tr>
                    </tbody>
                </table>

                <!-- Instructions -->
                <div style="background: #e3f2fd; border-left: 4px solid #2196f3; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
                    <p style="margin: 0; color: #1976d2; font-weight: 600; font-size: 14px;">📋 Instructions</p>
                    <p style="margin: 8px 0 0 0; color: #555; font-size: 13px;">Review each trade below and select <strong>Approve</strong> or <strong>Reject</strong>. All trades are pre-selected to approve by default. Click <strong>Submit Decisions</strong> when ready.</p>
                </div>

                <!-- Proposed Trades Form -->
                <form id="approvalForm" action="{submit_url}" method="POST">
                    <input type="hidden" name="request_id" value="{request_id}">

                    <h2 style="color: #2c3e50; margin: 0 0 20px 0; font-size: 18px; font-weight: 600;">Proposed Trades</h2>

                    <div style="overflow-x: auto;">
                        <table class="trades-table">
                            <thead>
                                <tr>
                                    <th style="text-align: left;">Symbol</th>
                                    <th style="text-align: right;">Shares</th>
                                    <th style="text-align: right;">Price</th>
                                    <th style="text-align: right;">Value</th>
                                    <th style="text-align: right;">Allocation</th>
                                    <th style="text-align: center; min-width: 250px;">Decision</th>
                                </tr>
                            </thead>
                            <tbody>
                                {trades_html}
                            </tbody>
                        </table>
                    </div>

                    <!-- Submit Section -->
                    <div class="submit-section">
                        <button type="submit" class="submit-button">
                            🚀 Submit Decisions
                        </button>
                        <p class="helper-text">This request expires in 24 hours</p>
                    </div>

                </form>

            </div>

            <!-- Footer -->
            <div class="footer">
                <p>Request ID: {request_id}</p>
                <p>{datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
            </div>

        </div>

        <script>
            // Calculate and display summary on form change
            document.getElementById('approvalForm').addEventListener('change', function() {{
                const formData = new FormData(this);
                let approvedCount = 0;
                let rejectedCount = 0;

                for (let i = 0; i < {len(trades)}; i++) {{
                    const decision = formData.get('trade_' + i);
                    if (decision === 'approve') approvedCount++;
                    else if (decision === 'reject') rejectedCount++;
                }}

                console.log('Approved:', approvedCount, 'Rejected:', rejectedCount);
            }});
        </script>
    </body>
    </html>
    """

    return html
