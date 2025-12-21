#!/usr/bin/env python3
"""
Approval Server
Simple Flask server to handle trade approval requests
"""
from flask import Flask, request, render_template_string, redirect, url_for
from approval_handler import ApprovalHandler
from approval_page_comprehensive import generate_comprehensive_approval_page
from database_schema import TradingDatabase
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
handler = ApprovalHandler()
db = TradingDatabase()


@app.route('/')
def index():
    """Home page"""
    return """
    <html>
    <head>
        <title>Trade Approval System</title>
        <style>
            body {
                font-family: 'Inter', -apple-system, sans-serif;
                background: linear-gradient(135deg, #0A2540 0%, #1a3a5c 100%);
                color: white;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }
            .container {
                text-align: center;
                padding: 40px;
                background: rgba(255,255,255,0.1);
                border-radius: 12px;
                backdrop-filter: blur(10px);
            }
            h1 {
                color: #D4AF37;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔔 Trade Approval System</h1>
            <p>Server is running and ready to handle approval requests.</p>
            <p style="color: #D4AF37; margin-top: 20px;">Check your email for approval links.</p>
        </div>
    </body>
    </html>
    """


@app.route('/approve')
def approve():
    """Approval page"""
    request_id = request.args.get('request_id')
    
    if not request_id:
        return "Error: No request ID provided", 400
    
    # Get pending request
    pending_request = handler.get_pending_request(request_id)
    
    if not pending_request:
        return """
        <html>
        <head>
            <title>Request Not Found</title>
            <style>
                body {
                    font-family: 'Inter', sans-serif;
                    background: #f5f7fa;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }
                .error {
                    text-align: center;
                    padding: 40px;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                }
                h1 { color: #C62828; }
            </style>
        </head>
        <body>
            <div class="error">
                <h1>❌ Request Not Found</h1>
                <p>This approval request does not exist or has already been processed.</p>
            </div>
        </body>
        </html>
        """, 404
    
    # Get market data and holdings from database
    market_data = db.get_latest_market_data()
    current_holdings = db.get_current_holdings()
    holdings_news = db.get_holdings_news(limit=5)
    
    # Generate comprehensive approval page
    approval_html = generate_comprehensive_approval_page(
        trades=pending_request['trades'],
        portfolio_value=pending_request['portfolio_value'],
        cash=pending_request['cash'],
        request_id=request_id,
        market_data=market_data,
        current_holdings=current_holdings,
        holdings_news=holdings_news
    )
    
    return approval_html


@app.route('/api/approve', methods=['POST'])
def process_approval():
    """Process approval form submission"""
    request_id = request.form.get('request_id')
    
    if not request_id:
        return "Error: No request ID provided", 400
    
    # Extract decisions from form
    decisions = {}
    for key, value in request.form.items():
        if key.startswith('trade_'):
            decisions[key] = value
    
    # Process decisions and execute trades
    results = handler.process_approval_decisions(request_id, decisions)
    
    if 'error' in results:
        return f"""
        <html>
        <head>
            <title>Error</title>
            <style>
                body {{
                    font-family: 'Inter', sans-serif;
                    background: #f5f7fa;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }}
                .error {{
                    text-align: center;
                    padding: 40px;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                }}
                h1 {{ color: #C62828; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h1>❌ Error</h1>
                <p>{results['error']}</p>
            </div>
        </body>
        </html>
        """, 400
    
    # Get account info for daily digest
    from alpaca_data_fetcher import AlpacaDataFetcher
    try:
        fetcher = AlpacaDataFetcher()
        account_info = fetcher.get_account_info()
        portfolio_value = account_info['portfolio_value']
        cash = account_info['cash']
    except:
        portfolio_value = 0
        cash = 0
    
    # Generate success page with daily digest and trades table
    summary = results.get('summary', {})
    approved = results.get('approved', [])
    executed = results.get('executed', [])
    rejected = results.get('rejected', [])
    failed = results.get('failed', [])
    
    # Combine all trades with their status
    all_trades = []
    for trade in approved:
        status = 'EXECUTED'
        order_id = None
        error = None
        # Find if it was executed or failed
        for exec_result in executed:
            if exec_result['trade']['symbol'] == trade['symbol']:
                order_id = exec_result['order_id']
                break
        for fail_result in failed:
            if fail_result['trade']['symbol'] == trade['symbol']:
                status = 'FAILED'
                error = fail_result['error']
                break
        all_trades.append({
            'trade': trade,
            'status': status,
            'order_id': order_id,
            'error': error
        })
    
    for trade in rejected:
        all_trades.append({
            'trade': trade,
            'status': 'REJECTED',
            'order_id': None,
            'error': None
        })
    
    success_html = f"""
    <html>
    <head>
        <title>Trades Processed</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            body {{
                font-family: 'Inter', -apple-system, sans-serif;
                background: linear-gradient(135deg, #0A2540 0%, #1a3a5c 100%);
                margin: 0;
                padding: 40px;
            }}
            .container {{
                max-width: 1000px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #27ae60 0%, #229954 100%);
                padding: 40px;
                text-align: center;
                color: white;
            }}
            .header h1 {{
                margin: 0;
                font-size: 32px;
            }}
            .content {{
                padding: 40px;
            }}
            .digest {{
                background: #f8f9fb;
                padding: 24px;
                border-radius: 8px;
                margin-bottom: 30px;
            }}
            .digest h2 {{
                color: #0A2540;
                margin: 0 0 20px 0;
                font-size: 20px;
            }}
            .digest-grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 12px;
            }}
            .digest-card {{
                background: white;
                padding: 16px;
                border-radius: 8px;
                border: 2px solid #e1e8ed;
            }}
            .digest-label {{
                color: #64748b;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                margin-bottom: 6px;
            }}
            .digest-value {{
                color: #0A2540;
                font-size: 22px;
                font-weight: 700;
            }}
            .trades-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            .trades-table th {{
                background: #0A2540;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: 600;
                font-size: 13px;
                text-transform: uppercase;
            }}
            .trades-table td {{
                padding: 16px 12px;
                border-bottom: 1px solid #e1e8ed;
            }}
            .trades-table tr:last-child td {{
                border-bottom: none;
            }}
            .trades-table tr:hover {{
                background: #f8f9fb;
            }}
            .status-badge {{
                display: inline-block;
                padding: 4px 12px;
                border-radius: 4px;
                font-weight: 600;
                font-size: 11px;
                text-transform: uppercase;
            }}
            .status-badge.approved {{
                background: #E8F5E9;
                color: #27ae60;
            }}
            .status-badge.rejected {{
                background: #f8f9fb;
                color: #64748b;
            }}
            .status-badge.failed {{
                background: #FFEBEE;
                color: #C62828;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Trades Processed Successfully</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">Your decisions have been executed</p>
            </div>
            <div class="content">
                <!-- Daily Digest -->
                <div class="digest">
                    <h2>Daily Digest</h2>
                    <div class="digest-grid">
                        <div class="digest-card">
                            <div class="digest-label">Portfolio</div>
                            <div class="digest-value">${portfolio_value:,.0f}</div>
                        </div>
                        <div class="digest-card">
                            <div class="digest-label">Cash Available</div>
                            <div class="digest-value">${cash:,.0f}</div>
                        </div>
                        <div class="digest-card">
                            <div class="digest-label">Approved</div>
                            <div class="digest-value" style="color: #27ae60;">{summary.get('approved', 0)}</div>
                        </div>
                        <div class="digest-card">
                            <div class="digest-label">Rejected</div>
                            <div class="digest-value" style="color: #64748b;">{summary.get('rejected', 0)}</div>
                        </div>
                    </div>
                </div>
                
                <!-- Trades Table -->
                <h3 style="color: #0A2540; margin: 0 0 16px 0;">All Suggested Trades</h3>
                <table class="trades-table">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Action</th>
                            <th>Shares</th>
                            <th>Price</th>
                            <th>Value</th>
                            <th>Status</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    for item in all_trades:
        trade = item['trade']
        status = item['status']
        order_id = item['order_id']
        error = item['error']
        
        action = trade.get('action', 'BUY')
        status_class = 'approved' if status == 'EXECUTED' else ('rejected' if status == 'REJECTED' else 'failed')
        
        # Create user-friendly details using database
        details = ''
        if order_id:
            details = 'Successfully placed on Alpaca'
        elif status == 'REJECTED':
            details = 'You chose not to execute this trade'
        elif error:
            # Get user-friendly message from database
            details = db.get_user_friendly_message(error)
        else:
            details = '-'
        
        success_html += f"""
                        <tr>
                            <td><strong>{trade['symbol']}</strong></td>
                            <td>{action}</td>
                            <td>{trade['shares']}</td>
                            <td>${trade['price']:.2f}</td>
                            <td>${trade['value']:,.2f}</td>
                            <td><span class="status-badge {status_class}">{status}</span></td>
                            <td style="font-size: 12px; color: #64748b;">{details}</td>
                        </tr>
        """
    
    success_html += """
                    </tbody>
                </table>
                
                <div style="margin-top: 40px; text-align: center; padding: 20px; background: #f8f9fb; border-radius: 8px;">
                    <p style="margin: 0; color: #64748b;">You can close this window now.</p>
                    <p style="margin: 10px 0 0 0; color: #64748b; font-size: 14px;">A confirmation email has been sent to your inbox.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send confirmation email
    send_confirmation_email(request_id, all_trades, summary, portfolio_value, cash)
    
    return success_html


def send_confirmation_email(request_id: str, trades: list, summary: dict, portfolio_value: float, cash: float):
    """Send confirmation email after approval submission"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import os
    from dotenv import load_dotenv
    from datetime import datetime
    
    load_dotenv()
    
    email_username = os.getenv('EMAIL_USERNAME')
    email_password = os.getenv('EMAIL_PASSWORD')
    email_to = os.getenv('EMAIL_TO')
    
    if not email_username or not email_password or not email_to:
        return
    
    # Generate confirmation email
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f5f7fa; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px; }}
            .header {{ background: linear-gradient(135deg, #27ae60 0%, #229954 100%); color: white; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 30px; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .digest {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin: 20px 0; }}
            .digest-card {{ background: #f8f9fb; padding: 15px; border-radius: 8px; text-align: center; }}
            .digest-label {{ color: #718096; font-size: 12px; text-transform: uppercase; margin-bottom: 5px; }}
            .digest-value {{ color: #2d3748; font-size: 24px; font-weight: 700; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th {{ background: #f7fafc; padding: 12px; text-align: left; font-weight: 600; color: #4a5568; font-size: 13px; }}
            td {{ padding: 12px; border-bottom: 1px solid #e2e8f0; }}
            .status-executed {{ color: #48bb78; font-weight: 600; }}
            .status-rejected {{ color: #718096; font-weight: 600; }}
            .status-failed {{ color: #f56565; font-weight: 600; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Trade Decisions Confirmed</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">{datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}</p>
            </div>
            
            <div class="digest">
                <div class="digest-card">
                    <div class="digest-label">Portfolio</div>
                    <div class="digest-value">${portfolio_value:,.0f}</div>
                </div>
                <div class="digest-card">
                    <div class="digest-label">Cash</div>
                    <div class="digest-value">${cash:,.0f}</div>
                </div>
                <div class="digest-card">
                    <div class="digest-label">Approved</div>
                    <div class="digest-value" style="color: #48bb78;">{summary.get('approved', 0)}</div>
                </div>
                <div class="digest-card">
                    <div class="digest-label">Rejected</div>
                    <div class="digest-value" style="color: #718096;">{summary.get('rejected', 0)}</div>
                </div>
            </div>
            
            <h2 style="color: #2d3748; margin: 30px 0 15px 0;">Your Decisions</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Action</th>
                        <th>Shares</th>
                        <th>Value</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for item in trades:
        trade = item['trade']
        status = item['status']
        status_class = 'status-executed' if status == 'EXECUTED' else ('status-rejected' if status == 'REJECTED' else 'status-failed')
        
        html += f"""
                    <tr>
                        <td><strong>{trade['symbol']}</strong></td>
                        <td>{trade.get('action', 'BUY')}</td>
                        <td>{trade['shares']}</td>
                        <td>${trade['value']:,.2f}</td>
                        <td class="{status_class}">{status}</td>
                    </tr>
        """
    
    html += f"""
                </tbody>
            </table>
            
            <div style="margin-top: 30px; padding: 20px; background: #e6fffa; border-radius: 8px; border-left: 4px solid #38b2ac;">
                <p style="margin: 0; color: #234e52; font-weight: 600;">✅ Your decisions have been processed</p>
                <p style="margin: 5px 0 0 0; color: #2c7a7b; font-size: 14px;">Request ID: {request_id}</p>
            </div>
            
            <div style="margin-top: 20px; text-align: center; padding: 20px; background: #f8f9fb; border-radius: 8px;">
                <p style="margin: 0; color: #718096; font-size: 14px;">Thank you for reviewing your trades!</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send email
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"✅ Trade Decisions Confirmed - {summary.get('approved', 0)} Approved, {summary.get('rejected', 0)} Rejected"
    msg['From'] = email_username
    msg['To'] = email_to
    
    html_part = MIMEText(html, 'html')
    msg.attach(html_part)
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(email_username, email_password)
            server.send_message(msg)
    except:
        pass  # Silently fail if email can't be sent


def run_server(host='0.0.0.0', port=8000, debug=False):
    """Run the approval server"""
    print("=" * 80)
    print("TRADE APPROVAL SERVER")
    print("=" * 80)
    print(f"\n🚀 Starting server on http://{host}:{port}")
    print(f"📧 Approval emails will link to: http://localhost:{port}/approve")
    print("\n⚠️  Keep this server running to handle approval requests")
    print("   Press Ctrl+C to stop\n")
    
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_server()
