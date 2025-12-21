#!/usr/bin/env python3
"""
Enhanced Professional Financial Email Template
Includes market updates, stock news, and reasoning flow
"""
from datetime import datetime
from typing import List, Dict, Optional
from news_causal_chains import _generate_news_based_chain


def generate_professional_approval_email(
    trades: List[Dict],
    portfolio_value: float,
    cash: float,
    approval_url: str,
    request_id: str,
    market_data: Optional[Dict] = None,
    holdings_news: Optional[List[Dict]] = None,
    current_holdings: Optional[List[Dict]] = None
) -> str:
    """
    Generate professional financial-style approval email
    
    Args:
        trades: List of proposed trades with symbol, shares, price, value, reasoning
        portfolio_value: Current portfolio value
        cash: Available cash
        approval_url: URL to approval page
        request_id: Unique request ID
        market_data: Market overview data (S&P 500, NASDAQ, DOW)
        holdings_news: News about current holdings
        current_holdings: Current portfolio holdings
    
    Returns:
        Professional HTML email string
    """
    
    # Calculate totals
    total_investment = sum(t['value'] for t in trades)
    
    # Build market overview section
    market_html = _build_market_overview(market_data) if market_data else ""
    
    # Build holdings news section
    holdings_news_html = _build_holdings_news_section(holdings_news) if holdings_news else ""
    
    # Build current holdings section
    current_holdings_html = _build_current_holdings(current_holdings) if current_holdings else ""
    
    # Build proposed trades with reasoning
    trades_html = _build_trades_with_reasoning(trades, portfolio_value)
    
    # Professional financial color scheme
    # Primary: Deep navy #0A2540 (financial institutions)
    # Accent: Gold #D4AF37 (wealth/premium)
    # Success: Forest green #2E7D32 (growth)
    # Alert: Amber #F57C00 (caution)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Trade Approval Required | Investment Review</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        </style>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f7fa; line-height: 1.6;">
        
        <div style="max-width: 1400px; margin: 0 auto; background-color: #ffffff;">
            
            <!-- Professional Header -->
            <div style="background: linear-gradient(135deg, #0A2540 0%, #1a3a5c 50%, #2a4a6c 100%); padding: 48px 32px; position: relative; overflow: hidden;">
                <div style="position: absolute; top: 0; right: 0; width: 300px; height: 300px; background: radial-gradient(circle, rgba(212,175,55,0.1) 0%, transparent 70%);"></div>
                <div style="position: relative; z-index: 1;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
                        <div style="color: #D4AF37; font-size: 14px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase;">Investment Advisory</div>
                        <div style="color: rgba(255,255,255,0.7); font-size: 13px;">{datetime.now().strftime('%B %d, %Y')}</div>
                    </div>
                    <h1 style="color: #ffffff; margin: 0 0 8px 0; font-size: 36px; font-weight: 700; letter-spacing: -0.5px;">Trade Approval Required</h1>
                    <p style="color: rgba(255,255,255,0.8); margin: 0; font-size: 16px; font-weight: 500;">Review and authorize {len(trades)} proposed transaction{'s' if len(trades) != 1 else ''}</p>
                </div>
            </div>

            <!-- Alert Banner -->
            <div style="background: linear-gradient(90deg, #F57C00 0%, #FB8C00 100%); padding: 16px 32px; border-bottom: 3px solid #E65100;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="background: rgba(255,255,255,0.2); border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; font-size: 18px;">⚠️</div>
                    <div>
                        <div style="color: #ffffff; font-weight: 600; font-size: 14px; margin-bottom: 2px;">Action Required</div>
                        <div style="color: rgba(255,255,255,0.9); font-size: 13px;">Manual approval required before trade execution • Expires in 24 hours</div>
                    </div>
                </div>
            </div>

            {market_html}

            <!-- Executive Summary -->
            <div style="padding: 32px 48px; background: linear-gradient(to bottom, #f8f9fb 0%, #ffffff 100%); border-bottom: 1px solid #e1e8ed;">
                <h2 style="color: #0A2540; margin: 0 0 24px 0; font-size: 24px; font-weight: 700; letter-spacing: -0.3px;">Executive Summary</h2>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px;">
                    <div style="background: #ffffff; padding: 20px; border-radius: 12px; border: 2px solid #e1e8ed; box-shadow: 0 2px 4px rgba(0,0,0,0.04);">
                        <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Portfolio Value</div>
                        <div style="color: #0A2540; font-size: 28px; font-weight: 700; margin-bottom: 4px;">${portfolio_value:,.0f}</div>
                        <div style="color: #2E7D32; font-size: 12px; font-weight: 600;">▲ Total Assets</div>
                    </div>
                    <div style="background: #ffffff; padding: 20px; border-radius: 12px; border: 2px solid #e1e8ed; box-shadow: 0 2px 4px rgba(0,0,0,0.04);">
                        <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Available Cash</div>
                        <div style="color: #0A2540; font-size: 28px; font-weight: 700; margin-bottom: 4px;">${cash:,.0f}</div>
                        <div style="color: #64748b; font-size: 12px; font-weight: 600;">Liquid Capital</div>
                    </div>
                    <div style="background: #ffffff; padding: 20px; border-radius: 12px; border: 2px solid #e1e8ed; box-shadow: 0 2px 4px rgba(0,0,0,0.04);">
                        <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Proposed Investment</div>
                        <div style="color: #0A2540; font-size: 28px; font-weight: 700; margin-bottom: 4px;">${total_investment:,.0f}</div>
                        <div style="color: #F57C00; font-size: 12px; font-weight: 600;">{(total_investment/cash*100):.1f}% of Cash</div>
                    </div>
                    <div style="background: #ffffff; padding: 20px; border-radius: 12px; border: 2px solid #e1e8ed; box-shadow: 0 2px 4px rgba(0,0,0,0.04);">
                        <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Transactions</div>
                        <div style="color: #0A2540; font-size: 28px; font-weight: 700; margin-bottom: 4px;">{len(trades)}</div>
                        <div style="color: #64748b; font-size: 12px; font-weight: 600;">Pending Approval</div>
                    </div>
                </div>
            </div>

            {current_holdings_html}
            {holdings_news_html}

            <!-- Proposed Trades -->
            <div style="padding: 32px 48px; background-color: #ffffff; border-bottom: 1px solid #e1e8ed;">
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #0A2540; margin: 0 0 8px 0; font-size: 24px; font-weight: 700; letter-spacing: -0.3px;">Proposed Transactions</h2>
                    <p style="color: #64748b; margin: 0; font-size: 15px;">Detailed analysis and reasoning for each recommended trade</p>
                </div>
                {trades_html}
            </div>

            <!-- Action Section -->
            <div style="padding: 48px; text-align: center; background: linear-gradient(to bottom, #f8f9fb 0%, #ffffff 100%); border-top: 3px solid #D4AF37;">
                <div style="margin-bottom: 24px;">
                    <div style="color: #0A2540; font-size: 18px; font-weight: 600; margin-bottom: 8px;">Ready to Review?</div>
                    <p style="color: #64748b; font-size: 14px; margin: 0; line-height: 1.6;">
                        Click below to access the secure approval portal where you can review each trade in detail<br/>
                        and approve or reject individual transactions.
                    </p>
                </div>
                <a href="{approval_url}?request_id={request_id}" 
                   style="display: inline-block; background: linear-gradient(135deg, #0A2540 0%, #1a3a5c 100%); color: #ffffff; padding: 18px 48px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 12px rgba(10, 37, 64, 0.3); border: 2px solid #D4AF37;">
                    📋 Review & Approve Trades
                </a>
                <div style="margin-top: 20px; padding: 16px; background: rgba(245, 124, 0, 0.1); border-radius: 8px; border-left: 4px solid #F57C00;">
                    <p style="color: #E65100; font-size: 13px; margin: 0; font-weight: 500;">
                        ⏱️ Trades will not execute until approved • Request expires in 24 hours
                    </p>
                </div>
            </div>

            <!-- Professional Footer -->
            <div style="background-color: #0A2540; padding: 32px; text-align: center; border-top: 3px solid #D4AF37;">
                <div style="color: #D4AF37; font-size: 14px; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">AUTOMATED TRADING SYSTEM</div>
                <p style="color: rgba(255,255,255,0.6); font-size: 12px; margin: 0 0 8px 0;">Secure Trade Approval Portal</p>
                <p style="color: rgba(255,255,255,0.4); font-size: 11px; margin: 0;">Request ID: {request_id} • {datetime.now().strftime('%I:%M %p ET')}</p>
            </div>

        </div>
    </body>
    </html>
    """
    
    return html


def _build_market_overview(market_data: Dict) -> str:
    """Build professional market overview section"""
    html = """
    <div style="padding: 32px 48px; background-color: #ffffff; border-bottom: 1px solid #e1e8ed;">
        <h2 style="color: #0A2540; margin: 0 0 24px 0; font-size: 24px; font-weight: 700; letter-spacing: -0.3px;">Market Overview</h2>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">
    """
    
    # Sample market data if not provided
    if not market_data:
        market_data = {
            "S&P 500": {"value": "4,783.45", "change": 23.45, "change_pct": 0.49},
            "NASDAQ": {"value": "15,095.14", "change": -15.23, "change_pct": -0.10},
            "DOW": {"value": "37,545.33", "change": 45.67, "change_pct": 0.12}
        }
    
    for name, data in market_data.items():
        change = data.get("change", 0)
        change_pct = data.get("change_pct", 0)
        value = data.get("value", "")
        
        is_positive = change >= 0
        color = "#2E7D32" if is_positive else "#C62828"
        bg_color = "#E8F5E9" if is_positive else "#FFEBEE"
        arrow = "▲" if is_positive else "▼"
        
        html += f"""
        <div style="background: {bg_color}; padding: 20px; border-radius: 12px; border-left: 4px solid {color};">
            <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">{name}</div>
            <div style="color: #0A2540; font-size: 24px; font-weight: 700; margin-bottom: 8px;">{value}</div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="color: {color}; font-weight: 700; font-size: 16px;">{arrow} {abs(change_pct):.2f}%</span>
                <span style="color: #64748b; font-size: 13px;">{abs(change):+.2f} pts</span>
            </div>
        </div>
        """
    
    html += """
        </div>
        <div style="margin-top: 16px; padding: 16px; background: #f8f9fb; border-radius: 8px; border-left: 4px solid #0A2540;">
            <div style="display: flex; justify-content: space-between; flex-wrap: wrap; gap: 16px;">
                <div>
                    <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">Market Sentiment</div>
                    <div style="color: #0A2540; font-size: 14px; font-weight: 600;">Moderately Bullish</div>
                </div>
                <div>
                    <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">Sector Leaders</div>
                    <div style="color: #0A2540; font-size: 14px; font-weight: 600;">Technology, Healthcare</div>
                </div>
                <div>
                    <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">Trading Volume</div>
                    <div style="color: #0A2540; font-size: 14px; font-weight: 600;">Above Average</div>
                </div>
            </div>
        </div>
    </div>
    """
    
    return html


def _build_current_holdings(holdings: List[Dict]) -> str:
    """Build current holdings section"""
    if not holdings:
        return ""
    
    html = """
    <div style="padding: 32px 48px; background-color: #f8f9fb; border-bottom: 1px solid #e1e8ed;">
        <h2 style="color: #0A2540; margin: 0 0 24px 0; font-size: 24px; font-weight: 700; letter-spacing: -0.3px;">Current Holdings</h2>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px;">
    """
    
    for holding in holdings:
        symbol = holding.get('symbol', '')
        shares = holding.get('shares', 0)
        avg_price = holding.get('avg_price', 0)
        current_price = holding.get('current_price', avg_price)
        value = shares * current_price
        gain_loss_pct = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
        
        is_positive = gain_loss_pct >= 0
        color = "#2E7D32" if is_positive else "#C62828"
        
        html += f"""
        <div style="background: #ffffff; padding: 16px; border-radius: 8px; border: 1px solid #e1e8ed; display: flex; justify-content: space-between; align-items: center;">
            <div style="flex: 1;">
                <div style="color: #0A2540; font-weight: 700; font-size: 16px; margin-bottom: 4px;">{symbol}</div>
                <div style="color: #64748b; font-size: 13px;">{shares:.2f} shares @ ${avg_price:.2f} avg</div>
            </div>
            <div style="text-align: right;">
                <div style="color: #0A2540; font-weight: 600; font-size: 16px; margin-bottom: 4px;">${value:,.2f}</div>
                <div style="color: {color}; font-size: 13px; font-weight: 600;">{gain_loss_pct:+.2f}%</div>
            </div>
        </div>
        """
    
    html += "</div></div>"
    return html


def _build_holdings_news_section(holdings_news: List[Dict]) -> str:
    """Build news about current holdings"""
    if not holdings_news:
        return ""
    
    html = """
    <div style="padding: 32px 48px; background-color: #ffffff; border-bottom: 1px solid #e1e8ed;">
        <h2 style="color: #0A2540; margin: 0 0 24px 0; font-size: 24px; font-weight: 700; letter-spacing: -0.3px;">News About Your Holdings</h2>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px;">
    """
    
    for news in holdings_news:
        ticker = news.get("ticker", "")
        title = news.get("title", "")
        summary = news.get("summary", "")
        sentiment = news.get("sentiment", "Neutral")
        
        sentiment_colors = {
            "Bullish": "#2E7D32",
            "Bearish": "#C62828",
            "Neutral": "#64748b"
        }
        sentiment_color = sentiment_colors.get(sentiment, "#64748b")
        
        html += f"""
        <div style="background: #f8f9fb; padding: 20px; border-radius: 8px; border-left: 4px solid {sentiment_color};">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
                <div style="background: #0A2540; color: #ffffff; padding: 4px 12px; border-radius: 4px; font-weight: 700; font-size: 13px;">{ticker}</div>
                <div style="background: {sentiment_color}; color: #ffffff; padding: 4px 12px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase;">{sentiment}</div>
            </div>
            <h3 style="color: #0A2540; font-size: 15px; font-weight: 600; margin: 0 0 8px 0; line-height: 1.4;">{title}</h3>
            <p style="color: #64748b; font-size: 13px; margin: 0; line-height: 1.5;">{summary}</p>
        </div>
        """
    
    html += "</div></div>"
    return html


def _build_trades_with_reasoning(trades: List[Dict], portfolio_value: float) -> str:
    """Build trades section with reasoning flow"""
    html = ""
    
    for i, trade in enumerate(trades):
        symbol = trade['symbol']
        shares = trade['shares']
        price = trade['price']
        value = trade['value']
        allocation = (value / portfolio_value * 100) if portfolio_value > 0 else 0
        
        # Get reasoning if provided
        reasoning = trade.get('reasoning', {})
        rsi = reasoning.get('rsi', 'N/A')
        volatility = reasoning.get('volatility', 'N/A')
        score = reasoning.get('score', 0)
        
        # Get action (default to BUY)
        action = trade.get('action', 'BUY').upper()
        action_color = "#2E7D32" if action == "BUY" else "#C62828"
        action_bg = "#E8F5E9" if action == "BUY" else "#FFEBEE"
        
        # Get causal chain if provided
        causal_chain = trade.get('causal_chain', [])
        
        html += f"""
        <div style="background: #f8f9fb; padding: 24px; border-radius: 12px; margin-bottom: 20px; border: 2px solid #e1e8ed;">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="background: #0A2540; color: #D4AF37; display: inline-block; padding: 6px 16px; border-radius: 6px; font-weight: 700; font-size: 18px;">{symbol}</div>
                    <div style="background: {action_bg}; color: {action_color}; display: inline-block; padding: 6px 16px; border-radius: 6px; font-weight: 700; font-size: 18px; border: 2px solid {action_color};">{action}</div>
                    <div style="color: #64748b; font-size: 13px; font-weight: 500;">Trade #{i+1} of {len(trades)}</div>
                </div>
                <div style="text-align: right;">
                    <div style="color: #0A2540; font-size: 24px; font-weight: 700; margin-bottom: 4px;">${value:,.2f}</div>
                    <div style="color: #64748b; font-size: 13px;">{allocation:.1f}% of portfolio</div>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px;">
                <div style="background: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #e1e8ed;">
                    <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">Shares</div>
                    <div style="color: #0A2540; font-size: 18px; font-weight: 700;">{shares}</div>
                </div>
                <div style="background: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #e1e8ed;">
                    <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">Price</div>
                    <div style="color: #0A2540; font-size: 18px; font-weight: 700;">${price:.2f}</div>
                </div>
                <div style="background: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #e1e8ed;">
                    <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">RSI</div>
                    <div style="color: #2E7D32; font-size: 18px; font-weight: 700;">{rsi}</div>
                </div>
                <div style="background: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #e1e8ed;">
                    <div style="color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">Volatility</div>
                    <div style="color: #0A2540; font-size: 18px; font-weight: 700;">{volatility}</div>
                </div>
            </div>
            
            <div style="background: #ffffff; padding: 16px; border-radius: 8px; border-left: 4px solid #2E7D32; margin-bottom: 16px;">
                <div style="color: #0A2540; font-weight: 600; font-size: 13px; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;">Investment Thesis</div>
                <div style="color: #64748b; font-size: 14px; line-height: 1.6;">
                    <strong style="color: #0A2540;">{symbol}</strong> shows strong buy signals with RSI indicating oversold conditions ({rsi}) and controlled volatility ({volatility}). Technical indicators suggest favorable entry point for mean reversion strategy with 20-day holding period target.
                </div>
            </div>
            
            {_build_causal_flow_chart(symbol, causal_chain, i)}
        </div>
        """
    
    return html


def _build_causal_flow_chart(symbol: str, causal_chain: List[Dict], trade_index: int) -> str:
    """Build causal reasoning flowchart for a trade"""
    if not causal_chain:
        # Generate default news-based causal chain
        # This shows real-world events that led to the opportunity
        causal_chain = _generate_news_based_chain(symbol)
    
    chart_id = f"flow_{symbol}_{trade_index}".replace(".", "_")
    
    html = f"""
    <div style="background: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #e1e8ed;">
        <div style="margin-bottom: 16px;">
            <div style="color: #0A2540; font-weight: 600; font-size: 13px; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px;">Recommendation Analysis</div>
            <div style="color: #64748b; font-size: 12px;">Causal chain showing the reasoning behind this trade recommendation</div>
        </div>
    """
    
    for i, step in enumerate(causal_chain):
        step_num = step.get("step", i + 1)
        title = step.get("title", "")
        description = step.get("description", "")
        details = step.get("details", "")
        impact = step.get("impact", "positive")
        
        # Color based on impact
        color_map = {
            "positive": "#2E7D32",
            "negative": "#C62828",
            "neutral": "#64748b"
        }
        color = color_map.get(impact, "#2E7D32")
        
        step_id = f"{chart_id}_step_{step_num}"
        
        html += f"""
        <div style="margin-bottom: 8px;">
            <div style="background: {color}; color: white; padding: 12px 14px; border-radius: 8px 8px 0 0; cursor: pointer;" onclick="toggleDetails('{step_id}')">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div style="background: rgba(255,255,255,0.2); border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 12px;">{step_num}</div>
                        <span style="font-weight: 600; font-size: 14px;">{title}</span>
                    </div>
                    <span id="arrow_{step_id}" style="font-size: 12px; transition: transform 0.3s;">▼</span>
                </div>
            </div>
            <div style="background: #f8f9fb; padding: 12px 14px; border: 1px solid #e1e8ed; border-top: none; border-radius: 0 0 8px 8px;">
                <p style="color: #0A2540; font-size: 13px; margin: 0 0 8px 0; line-height: 1.5; font-weight: 500;">{description}</p>
                <div id="details_{step_id}" style="display: none; margin-top: 8px; padding-top: 8px; border-top: 1px solid #e1e8ed;">
                    <p style="color: #64748b; font-size: 12px; margin: 0; line-height: 1.4;">{details}</p>
                </div>
            </div>
        </div>
        """
        
        # Arrow between steps (except last)
        if i < len(causal_chain) - 1:
            html += f"""
            <div style="text-align: center; margin: 6px 0;">
                <div style="color: {color}; font-size: 16px; font-weight: 700;">↓</div>
            </div>
            """
    
    html += """
        <div style="margin-top: 12px; padding: 12px; background: #f8f9fb; border-radius: 6px; border-left: 3px solid #0A2540;">
            <p style="color: #64748b; font-size: 11px; margin: 0; line-height: 1.4;">
                💡 <strong style="color: #0A2540;">Interactive:</strong> Click any step above to view detailed reasoning. Analysis based on technical indicators, historical patterns, and risk management principles.
            </p>
        </div>
    </div>
    
    <script>
        function toggleDetails(stepId) {
            var details = document.getElementById('details_' + stepId);
            var arrow = document.getElementById('arrow_' + stepId);
            
            if (details.style.display === 'none') {
                details.style.display = 'block';
                arrow.style.transform = 'rotate(180deg)';
                arrow.textContent = '▲';
            } else {
                details.style.display = 'none';
                arrow.style.transform = 'rotate(0deg)';
                arrow.textContent = '▼';
            }
        }
    </script>
    """
    
    return html
