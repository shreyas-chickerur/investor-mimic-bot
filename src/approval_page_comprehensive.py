#!/usr/bin/env python3
"""
Comprehensive Approval Page
Contains all detailed information for informed decision-making
"""
from datetime import datetime
from typing import List, Dict, Optional
from news_causal_chains import _generate_news_based_chain


def generate_comprehensive_approval_page(
    trades: List[Dict],
    portfolio_value: float,
    cash: float,
    request_id: str,
    market_data: Optional[Dict] = None,
    current_holdings: Optional[List[Dict]] = None,
    holdings_news: Optional[List[Dict]] = None
) -> str:
    """
    Generate comprehensive approval page with all information
    Market data, holdings, news, causal analysis - everything for informed decisions
    """
    
    total_investment = sum(t['value'] for t in trades)
    
    # Build market overview
    market_html = _build_market_section(market_data) if market_data else ""
    
    # Build current holdings
    holdings_html = _build_holdings_section(current_holdings) if current_holdings else ""
    
    # Build holdings news
    news_html = _build_news_section(holdings_news) if holdings_news else ""
    
    # Build trades with causal analysis
    trades_html = _build_trades_section(trades, portfolio_value)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Trade Approval - Comprehensive Review</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            body {{
                margin: 0;
                padding: 0;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background-color: #f5f7fa;
            }}
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                background-color: #ffffff;
            }}
            .btn {{
                padding: 14px 28px;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 15px;
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
            .btn-submit {{
                background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);
                color: white;
                box-shadow: 0 4px 12px rgba(33, 150, 243, 0.3);
            }}
            .btn-submit:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 16px rgba(33, 150, 243, 0.4);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #0A2540 0%, #1a3a5c 50%, #2a4a6c 100%); padding: 40px 32px; text-align: center;">
                <div style="color: #D4AF37; font-size: 12px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px;">Comprehensive Trade Review</div>
                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">Approve or Reject Trades</h1>
                <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0 0; font-size: 14px;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>

            <!-- Alert Banner -->
            <div style="background: linear-gradient(90deg, #F57C00 0%, #FB8C00 100%); padding: 16px 24px;">
                <div style="text-align: center;">
                    <div style="color: #ffffff; font-weight: 600; font-size: 14px; margin-bottom: 4px;">⚠️ Action Required</div>
                    <div style="color: rgba(255,255,255,0.95); font-size: 13px;">{len(trades)} trade{'s' if len(trades) != 1 else ''} pending your approval • Expires in 24 hours</div>
                </div>
            </div>

            <form id="approvalForm" method="POST" action="/api/approve">
                <input type="hidden" name="request_id" value="{request_id}">
                
                <!-- Executive Summary -->
                <div style="padding: 32px 24px; background: linear-gradient(to bottom, #f8f9fb 0%, #ffffff 100%);">
                    <h2 style="color: #0A2540; margin: 0 0 20px 0; font-size: 20px; font-weight: 700;">Today's Summary</h2>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 20px;">
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
                            <div style="color: #0A2540; font-size: 22px; font-weight: 700;">{len(current_holdings) if current_holdings else 0}</div>
                        </div>
                    </div>
                </div>

                {market_html}
                {holdings_html}
                {news_html}

                <!-- Proposed Trades with Analysis -->
                <div style="padding: 32px 48px; background-color: #ffffff; border-bottom: 1px solid #e1e8ed;">
                    <div style="margin-bottom: 28px;">
                        <h2 style="color: #0A2540; margin: 0 0 8px 0; font-size: 24px; font-weight: 700;">Proposed Transactions - Detailed Analysis</h2>
                        <p style="color: #64748b; margin: 0; font-size: 15px;">Review each trade with complete market analysis, news, and reasoning</p>
                    </div>
                    {trades_html}
                </div>

                <!-- Action Buttons -->
                <div style="padding: 48px; text-align: center; background: linear-gradient(to bottom, #f8f9fb 0%, #ffffff 100%); border-top: 3px solid #D4AF37;">
                    <div style="margin-bottom: 24px;">
                        <div style="color: #0A2540; font-size: 18px; font-weight: 700; margin-bottom: 8px;">Submit Your Decisions</div>
                        <p style="color: #64748b; font-size: 14px; margin: 0;">Review complete? Submit your approve/reject decisions for each trade</p>
                    </div>
                    <button type="submit" class="btn btn-submit">
                        Submit Decisions
                    </button>
                </div>
            </form>
        </div>

        <script>
            function toggleDetails(stepId) {{
                var details = document.getElementById('details_' + stepId);
                var arrow = document.getElementById('arrow_' + stepId);
                
                if (details.style.display === 'none') {{
                    details.style.display = 'block';
                    arrow.textContent = '▲';
                }} else {{
                    details.style.display = 'none';
                    arrow.textContent = '▼';
                }}
            }}
            
            document.getElementById('approvalForm').addEventListener('submit', function(e) {{
                const submitBtn = this.querySelector('button[type="submit"]');
                submitBtn.textContent = 'Processing...';
                submitBtn.disabled = true;
                
                // Form will submit normally to /api/approve
            }});
        </script>
    </body>
    </html>
    """
    
    return html


def _build_market_section(market_data: Dict) -> str:
    """Build market overview section"""
    html = """
    <div style="padding: 32px 48px; background-color: #ffffff; border-bottom: 1px solid #e1e8ed;">
        <h2 style="color: #0A2540; margin: 0 0 24px 0; font-size: 24px; font-weight: 700;">Market Overview</h2>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">
    """
    
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
    
    html += "</div></div>"
    return html


def _build_holdings_section(holdings: List[Dict]) -> str:
    """Build current holdings section"""
    if not holdings:
        return ""
    
    html = """
    <div style="padding: 32px 48px; background-color: #f8f9fb; border-bottom: 1px solid #e1e8ed;">
        <h2 style="color: #0A2540; margin: 0 0 24px 0; font-size: 24px; font-weight: 700;">Your Current Holdings</h2>
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


def _build_news_section(holdings_news: List[Dict]) -> str:
    """Build news section"""
    if not holdings_news:
        return ""
    
    html = """
    <div style="padding: 32px 48px; background-color: #ffffff; border-bottom: 1px solid #e1e8ed;">
        <h2 style="color: #0A2540; margin: 0 0 24px 0; font-size: 24px; font-weight: 700;">News About Your Holdings</h2>
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


def _build_trades_section(trades: List[Dict], portfolio_value: float) -> str:
    """Build trades section with causal analysis"""
    html = ""
    
    for i, trade in enumerate(trades):
        symbol = trade['symbol']
        shares = trade['shares']
        price = trade['price']
        value = trade['value']
        allocation = (value / portfolio_value * 100) if portfolio_value > 0 else 0
        
        action = trade.get('action', 'BUY').upper()
        action_color = "#2E7D32" if action == "BUY" else "#C62828"
        action_bg = "#E8F5E9" if action == "BUY" else "#FFEBEE"
        
        # Get reasoning
        reasoning = trade.get('reasoning', {})
        rsi = reasoning.get('rsi', 'N/A')
        volatility = reasoning.get('volatility', 'N/A')
        
        # Get or generate causal chain
        causal_chain = trade.get('causal_chain', [])
        if not causal_chain:
            causal_chain = _generate_news_based_chain(symbol)
        
        # Build causal flowchart
        flowchart_html = _build_flowchart(symbol, causal_chain, i)
        
        html += f"""
        <div style="background: #f8f9fb; padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 2px solid #e1e8ed;">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 20px;">
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
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px;">
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
            
            {flowchart_html}
            
            <div style="background: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #e1e8ed; margin-top: 20px;">
                <div style="color: #0A2540; font-weight: 600; font-size: 14px; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Your Decision</div>
                <div style="display: flex; gap: 20px; align-items: center;">
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; padding: 12px 20px; background: #E8F5E9; border-radius: 8px; border: 2px solid #2E7D32;">
                        <input type="radio" name="trade_{i}" value="approve" style="cursor: pointer; width: 20px; height: 20px;" checked>
                        <span style="color: #2E7D32; font-weight: 700; font-size: 16px;">✓ Approve</span>
                    </label>
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; padding: 12px 20px; background: #FFEBEE; border-radius: 8px; border: 2px solid #C62828;">
                        <input type="radio" name="trade_{i}" value="reject" style="cursor: pointer; width: 20px; height: 20px;">
                        <span style="color: #C62828; font-weight: 700; font-size: 16px;">✗ Reject</span>
                    </label>
                </div>
            </div>
        </div>
        """
    
    return html


def _build_flowchart(symbol: str, causal_chain: List[Dict], trade_index: int) -> str:
    """Build causal flowchart"""
    chart_id = f"flow_{symbol}_{trade_index}".replace(".", "_")
    
    html = f"""
    <div style="background: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #e1e8ed;">
        <div style="margin-bottom: 16px;">
            <div style="color: #0A2540; font-weight: 600; font-size: 14px; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px;">News-Based Analysis</div>
            <div style="color: #64748b; font-size: 13px;">Causal chain showing real events that led to this opportunity</div>
        </div>
    """
    
    for i, step in enumerate(causal_chain):
        step_num = step.get("step", i + 1)
        title = step.get("title", "")
        description = step.get("description", "")
        details = step.get("details", "")
        impact = step.get("impact", "positive")
        
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
                    <span id="arrow_{step_id}" style="font-size: 12px;">▼</span>
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
        
        if i < len(causal_chain) - 1:
            html += f"""
            <div style="text-align: center; margin: 6px 0;">
                <div style="color: {color}; font-size: 16px; font-weight: 700;">↓</div>
            </div>
            """
    
    html += """
        <div style="margin-top: 12px; padding: 12px; background: #f8f9fb; border-radius: 6px; border-left: 3px solid #0A2540;">
            <p style="color: #64748b; font-size: 11px; margin: 0; line-height: 1.4;">
                💡 <strong style="color: #0A2540;">Interactive:</strong> Click any step to view detailed reasoning
            </p>
        </div>
    </div>
    """
    
    return html
