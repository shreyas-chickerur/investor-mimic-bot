"""
HTML pages for trade approval.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from services.approval.trade_approval import TradeApprovalManager
from services.monitoring.approval_form_template import get_approval_form_html

router = APIRouter()
approval_manager = TradeApprovalManager()


@router.get("/{request_id}", response_class=HTMLResponse)
async def view_approval_request(request_id: str):
    """Redirect to the review page."""
    return RedirectResponse(url=f"/api/v1/approve/{request_id}/review")


@router.get("/{request_id}/approve", response_class=HTMLResponse)
async def approve_page(request_id: str):
    """Display approval confirmation page."""
    request = approval_manager.get_request(request_id)

    if not request:
        return """
        <html>
            <head><title>Approval Not Found</title></head>
            <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px;">
                <h1>❌ Approval Request Not Found</h1>
                <p>The approval request could not be found.</p>
            </body>
        </html>
        """

    if request.status.value != "PENDING":
        return f"""
        <html>
            <head><title>Already Processed</title></head>
            <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px;">
                <h1>ℹ️ Already Processed</h1>
                <p>This approval request has already been {request.status.value.lower()}.</p>
                <p><strong>Status:</strong> {request.status.value}</p>
            </body>
        </html>
        """

    # Build trade table
    trade_rows = ""
    for trade in request.trades:
        trade_rows += f"""
        <tr>
            <td>{trade.symbol}</td>
            <td>{trade.quantity:.2f}</td>
            <td>${trade.estimated_price:.2f}</td>
            <td>${trade.estimated_value:,.2f}</td>
            <td>{trade.allocation_pct:.1f}%</td>
        </tr>
        """

    return f"""
    <html>
        <head>
            <title>Approve Trade Request</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 900px;
                    margin: 50px auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #2c3e50;
                    border-bottom: 3px solid #3498db;
                    padding-bottom: 10px;
                }}
                .summary {{
                    background-color: #ecf0f1;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                .summary-item {{
                    margin: 10px 0;
                    font-size: 16px;
                }}
                .summary-item strong {{
                    display: inline-block;
                    width: 200px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    padding: 12px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #3498db;
                    color: white;
                }}
                tr:hover {{
                    background-color: #f5f5f5;
                }}
                .button-container {{
                    margin-top: 30px;
                    text-align: center;
                }}
                button {{
                    padding: 15px 40px;
                    font-size: 18px;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    margin: 0 10px;
                    transition: all 0.3s;
                }}
                .approve-btn {{
                    background-color: #27ae60;
                    color: white;
                }}
                .approve-btn:hover {{
                    background-color: #229954;
                }}
                .reject-btn {{
                    background-color: #e74c3c;
                    color: white;
                }}
                .reject-btn:hover {{
                    background-color: #c0392b;
                }}
                .expires {{
                    color: #e67e22;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 Trade Approval Required</h1>

                <div class="summary">
                    <div class="summary-item">
                        <strong>Total Investment:</strong> ${request.total_investment:,.2f}
                    </div>
                    <div class="summary-item">
                        <strong>Available Cash:</strong> ${request.available_cash:,.2f}
                    </div>
                    <div class="summary-item">
                        <strong>Cash Buffer:</strong> ${request.cash_buffer:,.2f}
                    </div>
                    <div class="summary-item">
                        <strong>Number of Trades:</strong> {len(request.trades)}
                    </div>
                    <div class="summary-item">
                        <strong>Strategy:</strong> {request.strategy_name}
                    </div>
                    <div class="summary-item expires">
                        <strong>Expires:</strong> {request.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
                    </div>
                </div>

                <h2>Proposed Trades</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Quantity</th>
                            <th>Est. Price</th>
                            <th>Est. Value</th>
                            <th>Allocation</th>
                        </tr>
                    </thead>
                    <tbody>
                        {trade_rows}
                    </tbody>
                </table>

                <div class="button-container">
                    <button class="approve-btn" onclick="approve()">
                        ✓ Approve Trades
                    </button>
                    <button class="reject-btn" onclick="reject()">
                        ✗ Reject Trades
                    </button>
                </div>

                <div id="result" style="margin-top: 20px; text-align: center; font-size: 18px;"></div>
            </div>

            <script>
                async function approve() {{
                    const result = document.getElementById('result');
                    result.innerHTML = '⏳ Processing...';

                    try {{
                        const response = await fetch('/api/v1/approvals/{request_id}/approve', {{
                            method: 'POST'
                        }});
                        const data = await response.json();

                        if (data.success) {{
                            result.innerHTML = '<span style="color: #27ae60; font-weight: bold;">✓ Trades Approved! The bot will execute them shortly.</span>';
                            document.querySelector('.approve-btn').disabled = true;
                            document.querySelector('.reject-btn').disabled = true;
                        }} else {{
                            result.innerHTML = '<span style="color: #e74c3c;">✗ ' + data.message + '</span>';
                        }}
                    }} catch (error) {{
                        result.innerHTML = '<span style="color: #e74c3c;">✗ Error: ' + error.message + '</span>';
                    }}
                }}

                async function reject() {{
                    const result = document.getElementById('result');
                    result.innerHTML = '⏳ Processing...';

                    try {{
                        const response = await fetch('/api/v1/approvals/{request_id}/reject', {{
                            method: 'POST'
                        }});
                        const data = await response.json();

                        if (data.success) {{
                            result.innerHTML = '<span style="color: #e74c3c; font-weight: bold;">✗ Trades Rejected</span>';
                            document.querySelector('.approve-btn').disabled = true;
                            document.querySelector('.reject-btn').disabled = true;
                        }} else {{
                            result.innerHTML = '<span style="color: #e74c3c;">✗ ' + data.message + '</span>';
                        }}
                    }} catch (error) {{
                        result.innerHTML = '<span style="color: #e74c3c;">✗ Error: ' + error.message + '</span>';
                    }}
                }}
            </script>
        </body>
    </html>
    """


@router.get("/{request_id}/reject", response_class=HTMLResponse)
async def reject_page(request_id: str):
    """Display rejection confirmation page."""
    return await approve_page(request_id)  # Same page, different button will be used


@router.get("/{request_id}/review", response_class=HTMLResponse)
async def review_trades_page(request_id: str):
    """Display interactive form to review and approve/reject trades individually."""
    request = approval_manager.get_request(request_id)

    if not request:
        return """
        <html>
            <head><title>Approval Not Found</title></head>
            <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px;">
                <h1>❌ Approval Request Not Found</h1>
                <p>The approval request could not be found.</p>
            </body>
        </html>
        """

    if request.status.value != "PENDING":
        return f"""
        <html>
            <head><title>Already Processed</title></head>
            <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px;">
                <h1>ℹ️ Already Processed</h1>
                <p>This approval request has already been {request.status.value.lower()}.</p>
                <p><strong>Status:</strong> {request.status.value}</p>
            </body>
        </html>
        """

    # Convert trades to dict format
    trades_list = [
        {
            "symbol": trade.symbol,
            "quantity": trade.quantity,
            "estimated_price": trade.estimated_price,
            "estimated_value": trade.estimated_value,
            "allocation_pct": trade.allocation_pct,
        }
        for trade in request.trades
    ]

    # Generate the interactive form
    submit_url = f"/api/v1/approve/{request_id}/submit"

    html = get_approval_form_html(
        request_id=request_id,
        trades=trades_list,
        total_investment=request.total_investment,
        available_cash=request.available_cash,
        cash_buffer=request.cash_buffer,
        submit_url=submit_url,
    )

    return html


@router.post("/{request_id}/submit", response_class=HTMLResponse)
async def submit_bulk_decisions(request_id: str, request: Request):
    """Handle bulk approval/rejection form submission."""
    form_data = await request.form()

    approval_request = approval_manager.get_request(request_id)

    if not approval_request:
        return """
        <html>
            <head><title>Error</title></head>
            <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px;">
                <h1>❌ Error</h1>
                <p>Approval request not found.</p>
            </body>
        </html>
        """

    # Process decisions
    approved_count = 0
    rejected_count = 0

    for i in range(len(approval_request.trades)):
        decision = form_data.get(f"trade_{i}")

        if decision == "approve":
            approval_manager.approve_trade(request_id, i)
            approved_count += 1
        elif decision == "reject":
            approval_manager.reject_trade(request_id, i)
            rejected_count += 1

    # Get updated request with approval statuses
    updated_request = approval_manager.get_request(request_id)

    # Build detailed trade table rows
    trades_table_html = ""
    for trade in updated_request.trades:
        status_badge = ""
        if trade.approved is True:
            status_badge = '<span style="background-color: #27ae60; color: white; padding: 8px 16px; border-radius: 4px; font-weight: 600; font-size: 14px; display: inline-block;">✓ APPROVED</span>'
        elif trade.approved is False:
            status_badge = '<span style="background-color: #e74c3c; color: white; padding: 8px 16px; border-radius: 4px; font-weight: 600; font-size: 14px; display: inline-block;">✗ REJECTED</span>'
        else:
            status_badge = '<span style="background-color: #95a5a6; color: white; padding: 8px 16px; border-radius: 4px; font-weight: 600; font-size: 14px; display: inline-block;">⏳ PENDING</span>'

        trades_table_html += f"""
        <tr>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; font-weight: 600; color: #2c3e50; font-size: 15px;">{trade.symbol}</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: right; color: #555;">{trade.quantity:.2f}</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: right; color: #555;">${trade.estimated_price:.2f}</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: right; font-weight: 600; color: #2c3e50;">${trade.estimated_value:,.2f}</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: right; color: #555;">{trade.allocation_pct:.1f}%</td>
            <td style="padding: 16px; border-bottom: 1px solid #e0e0e0; text-align: center;">{status_badge}</td>
        </tr>
        """

    return f"""
    <html>
        <head>
            <title>Decisions Submitted</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
                    background-color: #27ae60;
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
                    color: #e8f5e9;
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
                .next-steps {{
                    margin-top: 30px;
                    padding: 20px;
                    background: #e3f2fd;
                    border-left: 4px solid #2196f3;
                    border-radius: 4px;
                }}
                .next-steps p {{
                    margin: 0;
                    color: #1976d2;
                }}
                .next-steps p:first-child {{
                    font-weight: 600;
                    margin-bottom: 10px;
                }}
                .next-steps p:last-child {{
                    color: #555;
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
                    <h1>✅ Decisions Submitted Successfully!</h1>
                    <p>InvestorMimic Bot</p>
                </div>

                <!-- Main Content -->
                <div class="content">

                    <!-- Summary -->
                    <table class="summary-table">
                        <tbody>
                            <tr>
                                <td class="summary-label">Total Trades</td>
                                <td class="summary-value">{len(updated_request.trades)}</td>
                            </tr>
                            <tr>
                                <td class="summary-label">Approved</td>
                                <td class="summary-value" style="color: #27ae60;">{approved_count}</td>
                            </tr>
                            <tr>
                                <td class="summary-label">Rejected</td>
                                <td class="summary-value" style="color: #e74c3c;">{rejected_count}</td>
                            </tr>
                        </tbody>
                    </table>

                    <!-- Trade Details -->
                    <h2 style="color: #2c3e50; margin: 0 0 20px 0; font-size: 18px; font-weight: 600;">Trade Details</h2>
                    <div style="overflow-x: auto;">
                        <table class="trades-table">
                            <thead>
                                <tr>
                                    <th style="text-align: left;">Symbol</th>
                                    <th style="text-align: right;">Shares</th>
                                    <th style="text-align: right;">Price</th>
                                    <th style="text-align: right;">Value</th>
                                    <th style="text-align: right;">Allocation</th>
                                    <th style="text-align: center; min-width: 150px;">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {trades_table_html}
                            </tbody>
                        </table>
                    </div>

                    <!-- Next Steps -->
                    <div class="next-steps">
                        <p>📋 Next Steps</p>
                        <p>The approved trades will be executed automatically by the bot. You'll receive a confirmation email once the trades are complete.</p>
                    </div>

                </div>

                <!-- Footer -->
                <div class="footer">
                    <p>Request ID: {request_id}</p>
                    <p>Approved: {approved_count} | Rejected: {rejected_count}</p>
                </div>

            </div>
        </body>
    </html>
    """
