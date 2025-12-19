"""
Professional HTML Email Templates - Technology themed, clean and modern.
"""

from datetime import datetime
from typing import Dict, List


def get_approval_email_html(
    request_id: str,
    trades: List[Dict],
    total_investment: float,
    available_cash: float,
    cash_buffer: float,
    recommendations: List[Dict] = None,
    risk_metrics: Dict = None,
    performance_summary: Dict = None,
    approve_url: str = "",
    reject_url: str = "",
) -> str:
    """
    Generate clean, professional HTML email focused on proposed trades.

    Args:
        request_id: Approval request ID
        trades: List of proposed trades
        total_investment: Total investment amount
        available_cash: Available cash
        cash_buffer: Cash buffer amount
        recommendations: Not used (kept for compatibility)
        risk_metrics: Not used (kept for compatibility)
        performance_summary: Not used (kept for compatibility)
        approve_url: Approval URL
        reject_url: Rejection URL

    Returns:
        HTML email string
    """

    # Build trades table (preview only - decisions made on review page)
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
        </tr>
        """

    # Removed recommendations, risk metrics, and performance sections for cleaner email

    # Clean, professional HTML template focused on trades only
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Trade Approval Required</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8f9fa;">
        <div style="max-width: 700px; margin: 40px auto; background-color: #ffffff; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-radius: 8px; overflow: hidden;">

            <!-- Header -->
            <div style="background-color: #2c3e50; padding: 32px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: -0.5px;">Trade Approval Required</h1>
                <p style="color: #95a5a6; margin: 8px 0 0 0; font-size: 14px;">InvestorMimic Bot</p>
            </div>

            <!-- Main Content -->
            <div style="padding: 40px;">

                <!-- Summary -->
                <div style="margin-bottom: 32px;">
                    <table style="width: 100%; border-collapse: collapse; background: #f8f9fa; border-radius: 6px; overflow: hidden;">
                        <tbody>
                            <tr style="border-bottom: 1px solid #dee2e6;">
                                <td style="padding: 16px 20px; color: #495057; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; width: 50%;">Total Investment</td>
                                <td style="padding: 16px 20px; color: #2c3e50; font-size: 24px; font-weight: 700; text-align: right;">${total_investment:,.2f}</td>
                            </tr>
                            <tr>
                                <td style="padding: 16px 20px; color: #495057; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Number of Positions</td>
                                <td style="padding: 16px 20px; color: #2c3e50; font-size: 24px; font-weight: 700; text-align: right;">{len(trades)}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <!-- Proposed Trades -->
                <div style="margin-bottom: 32px;">
                    <h2 style="color: #2c3e50; margin: 0 0 20px 0; font-size: 18px; font-weight: 600;">Proposed Trades</h2>
                    <div style="overflow-x: auto;">
                        <table style="width: 100%; border-collapse: collapse; background: #ffffff;">
                            <thead>
                                <tr style="background-color: #f8f9fa; border-bottom: 2px solid #dee2e6;">
                                    <th style="padding: 14px 16px; text-align: left; color: #495057; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Symbol</th>
                                    <th style="padding: 14px 16px; text-align: right; color: #495057; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Shares</th>
                                    <th style="padding: 14px 16px; text-align: right; color: #495057; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Price</th>
                                    <th style="padding: 14px 16px; text-align: right; color: #495057; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Value</th>
                                    <th style="padding: 14px 16px; text-align: right; color: #495057; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Allocation</th>
                                </tr>
                            </thead>
                            <tbody>
                                {trades_html}
                                <tr style="background-color: #f8f9fa; border-top: 2px solid #dee2e6;">
                                    <td colspan="3" style="padding: 16px; font-weight: 600; color: #2c3e50; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;">Total</td>
                                    <td style="padding: 16px; text-align: right; font-weight: 700; color: #2c3e50; font-size: 18px;">${total_investment:,.2f}</td>
                                    <td style="padding: 16px;"></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Action Button -->
                <div style="margin-top: 48px;">
                    <p style="color: #7f8c8d; text-align: center; margin-bottom: 32px; font-size: 13px;">This request expires in 24 hours</p>
                    <div style="text-align: center;">
                        <a href="http://localhost:8000/api/v1/approve/{request_id}/review" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 18px 48px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 18px; display: inline-block; box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4); transition: all 0.3s ease;">
                            🚀 Review & Approve Trades
                        </a>
                    </div>
                    <p style="color: #95a5a6; text-align: center; margin-top: 16px; font-size: 12px;">Click to review each trade and make your decisions</p>
                </div>

            </div>

            <!-- Footer -->
            <div style="background-color: #f8f9fa; padding: 24px; text-align: center; border-top: 1px solid #dee2e6;">
                <p style="color: #7f8c8d; font-size: 12px; margin: 0;">Request ID: {request_id}</p>
                <p style="color: #95a5a6; font-size: 11px; margin: 8px 0 0 0;">{datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
            </div>

        </div>
    </body>
    </html>
    """

    return html
