"""
Daily Digest Email Template - Morning Brew Style

Professional, clean email template for daily investment digest.
"""

from datetime import datetime
from typing import Dict, List
from services.monitoring.daily_digest_email_template_extended import _build_flow_charts


def get_daily_digest_email_html(market_section: Dict, portfolio_section: Dict, user_name: str = "Investor") -> str:
    """
    Generate Morning Brew style daily digest email.

    Args:
        market_section: Market news and data
        portfolio_section: User's portfolio and recommendations
        user_name: User's name

    Returns:
        HTML email string
    """

    # Market Summary Section
    market_summary_html = _build_market_summary(market_section.get("market_summary", {}))

    # Headlines Section
    headlines_html = _build_headlines(market_section.get("headlines", []))

    # Portfolio Performance Section
    performance_html = _build_portfolio_performance(portfolio_section.get("performance", {}))

    # Holdings Section
    holdings_html = _build_holdings(portfolio_section.get("holdings", []))

    # Recommendations Section
    recommendations_html = _build_recommendations(portfolio_section.get("recommendations", []))

    # Flow Charts Section
    flow_charts_html = _build_flow_charts(portfolio_section.get("recommendations", []))

    # Holdings News Section
    holdings_news_html = _build_holdings_news(portfolio_section.get("holdings_news", []))

    # Complete HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Daily Investment Digest</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: Georgia, 'Times New Roman', Times, serif; background-color: #f8f9fa; line-height: 1.6;">
        <div style="max-width: 900px; margin: 20px auto; background-color: #ffffff; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-radius: 8px; overflow: hidden;">

            <!-- Header -->
            <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #7e8ba3 100%); padding: 40px 32px; text-align: center; position: relative; overflow: hidden;">
                <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: url('data:image/svg+xml,%3Csvg width="100" height="100" xmlns="http://www.w3.org/2000/svg"%3E%3Cpath d="M0 0h100v100H0z" fill="none"/%3E%3Cpath d="M0 50h100M50 0v100" stroke="%23ffffff" stroke-width="0.5" opacity="0.1"/%3E%3C/svg%3E') repeat; opacity: 0.3;"></div>
                <div style="position: relative; z-index: 1;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 32px; font-weight: 700; letter-spacing: 0.5px; text-shadow: 0 2px 4px rgba(0,0,0,0.2); font-family: Georgia, 'Times New Roman', Times, serif;">📊 Daily Investment Digest</h1>
                    <p style="color: #e3f2fd; margin: 12px 0 0 0; font-size: 15px; font-weight: 500;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
                </div>
            </div>

            <!-- Greeting -->
            <div style="padding: 24px 24px 16px 24px; border-bottom: 2px solid #f1f3f5;">
                <p style="color: #2c3e50; font-size: 16px; margin: 0;">Good morning, {user_name}</p>
            </div>

            <!-- Market Section -->
            <div style="padding: 24px; border-bottom: 2px solid #f1f3f5;">
                <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 20px; font-weight: 700;">Market Overview</h2>
                {market_summary_html}
            </div>

            <!-- Headlines Section -->
            <div style="padding: 24px; border-bottom: 2px solid #f1f3f5;">
                <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 20px; font-weight: 700;">Top Headlines</h2>
                {headlines_html}
            </div>

            <!-- Portfolio Section -->
            <div style="padding: 24px; background-color: #f8f9fa; border-bottom: 2px solid #e9ecef;">
                <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 20px; font-weight: 700;">Your Portfolio</h2>
                {performance_html}
            </div>

            <!-- Holdings Section -->
            <div style="padding: 24px; border-bottom: 2px solid #f1f3f5;">
                <h3 style="color: #2c3e50; margin: 0 0 12px 0; font-size: 16px; font-weight: 600;">Current Holdings</h3>
                {holdings_html}
            </div>

            <!-- Recommendations Section -->
            <div style="padding: 24px; background-color: #fff8e1; border-bottom: 2px solid #ffe082;">
                <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 20px; font-weight: 700;">Today's Recommendations</h2>
                {recommendations_html}
            </div>

            <!-- Flow Charts Section -->
            {flow_charts_html}

            <!-- Holdings News Section -->
            {holdings_news_html}

            <!-- Review Trades Section -->
            <div style="padding: 32px 24px; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-top: 2px solid #dee2e6; text-align: center;">
                <h3 style="color: #2c3e50; margin: 0 0 8px 0; font-size: 18px; font-weight: 700;">Ready to Execute?</h3>
                <p style="color: #7f8c8d; font-size: 14px; margin: 0 0 20px 0;">Review today's recommendations and approve or reject trades</p>
                <a href="http://localhost:8000/api/v1/approve/today/review" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; padding: 16px 40px; border-radius: 8px; text-decoration: none; font-size: 16px; font-weight: 700; display: inline-block; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); transition: transform 0.2s;">
                    📊 Review & Approve Trades
                </a>
                <p style="color: #95a5a6; font-size: 12px; margin: 16px 0 0 0;">You can approve or reject each trade individually</p>
            </div>

            <!-- Footer -->
            <div style="background-color: #f8f9fa; padding: 24px; text-align: center; border-top: 1px solid #dee2e6;">
                <p style="color: #7f8c8d; font-size: 12px; margin: 0;">InvestorMimic Bot • Daily Digest</p>
                <p style="color: #95a5a6; font-size: 11px; margin: 8px 0 0 0;">Sent at {datetime.now().strftime('%I:%M %p ET')}</p>
            </div>

        </div>
    </body>
    </html>
    """

    return html


def _build_market_summary(market_data: Dict) -> str:
    """Build expanded market summary section with more metrics."""
    if not market_data:
        return '<p style="color: #7f8c8d; font-size: 14px;">Market data unavailable</p>'

    html = '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px;">'

    for name, data in market_data.items():
        change = data.get("change", 0)
        change_pct = data.get("change_pct", 0)
        value = data.get("value", "")
        color = "#27ae60" if change >= 0 else "#e74c3c"
        arrow = "↑" if change >= 0 else "↓"
        bg_color = "#e8f5e9" if change >= 0 else "#ffebee"

        html += f"""
        <div style="background: {bg_color}; padding: 16px; border-radius: 8px; border: 1px solid {color}20;">
            <div style="color: #546e7a; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 8px;">{name}</div>
            <div style="color: #2c3e50; font-size: 20px; font-weight: 700; margin-bottom: 4px;">{value}</div>
            <div style="color: {color}; font-weight: 600; font-size: 16px;">{arrow} {abs(change_pct):.2f}%</div>
            <div style="color: #7f8c8d; font-size: 11px; margin-top: 4px;">{abs(change):+.2f} pts</div>
        </div>
        """

    html += "</div>"

    # Add market sentiment summary
    html += """
    <div style="background: #f8f9fa; padding: 20px 24px; border-radius: 8px; border-left: 4px solid #2196F3;">
        <div style="display: flex; justify-content: space-evenly; align-items: center; flex-wrap: wrap; gap: 20px;">
            <div style="flex: 1; min-width: 180px;">
                <div style="color: #546e7a; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Market Sentiment</div>
                <div style="color: #2c3e50; font-size: 15px; font-weight: 600; margin-top: 6px;">Moderately Bullish</div>
            </div>
            <div style="flex: 1; min-width: 180px;">
                <div style="color: #546e7a; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Sector Leaders</div>
                <div style="color: #2c3e50; font-size: 15px; font-weight: 600; margin-top: 6px;">Technology, Healthcare</div>
            </div>
            <div style="flex: 1; min-width: 180px;">
                <div style="color: #546e7a; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Volume</div>
                <div style="color: #2c3e50; font-size: 15px; font-weight: 600; margin-top: 6px;">Above Average</div>
            </div>
        </div>
    </div>
    """

    return html


def _build_headlines(headlines: List[Dict]) -> str:
    """Build headlines section."""
    if not headlines:
        return '<p style="color: #7f8c8d; font-size: 14px;">No headlines available</p>'

    html = '<div style="display: grid; gap: 16px;">'

    for headline in headlines:
        sentiment_color = {"Bullish": "#27ae60", "Bearish": "#e74c3c", "Neutral": "#7f8c8d"}.get(
            headline.get("sentiment", "Neutral"), "#7f8c8d"
        )

        html += f"""
        <div style="border-left: 3px solid {sentiment_color}; padding-left: 12px;">
            <h4 style="color: #2c3e50; margin: 0 0 4px 0; font-size: 14px; font-weight: 600; line-height: 1.4;">{headline.get('title', '')}</h4>
            <p style="color: #7f8c8d; margin: 0; font-size: 12px;">{headline.get('source', '')} • {headline.get('sentiment', 'Neutral')}</p>
        </div>
        """

    html += "</div>"
    return html


def _build_portfolio_performance(performance: Dict) -> str:
    """Build portfolio performance section."""
    total_value = performance.get("total_value", 0)
    gain_loss = performance.get("total_gain_loss", 0)
    gain_loss_pct = performance.get("avg_gain_loss_pct", 0)

    color = "#27ae60" if gain_loss >= 0 else "#e74c3c"
    sign = "+" if gain_loss >= 0 else ""

    html = f"""
    <div style="background: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="display: grid; gap: 16px;">
            <div>
                <p style="color: #7f8c8d; font-size: 12px; margin: 0; text-transform: uppercase; letter-spacing: 0.5px;">Total Value</p>
                <p style="color: #2c3e50; font-size: 28px; font-weight: 700; margin: 4px 0 0 0;">${total_value:,.2f}</p>
            </div>
            <div>
                <p style="color: #7f8c8d; font-size: 12px; margin: 0; text-transform: uppercase; letter-spacing: 0.5px;">Total Gain/Loss</p>
                <p style="color: {color}; font-size: 20px; font-weight: 600; margin: 4px 0 0 0;">{sign}${abs(gain_loss):,.2f} ({sign}{gain_loss_pct:.2f}%)</p>
            </div>
        </div>
    </div>
    """

    return html


def _build_holdings(holdings: List[Dict]) -> str:
    """Build holdings table."""
    if not holdings:
        return '<p style="color: #7f8c8d; font-size: 14px;">No holdings</p>'

    html = '<div style="overflow-x: auto;"><table style="width: 100%; border-collapse: collapse; font-size: 13px;">'
    html += """
    <thead>
        <tr style="background-color: #f8f9fa; border-bottom: 2px solid #dee2e6;">
            <th style="padding: 10px 12px; text-align: left; color: #495057; font-weight: 600; text-transform: uppercase; font-size: 11px;">Ticker</th>
            <th style="padding: 10px 12px; text-align: right; color: #495057; font-weight: 600; text-transform: uppercase; font-size: 11px;">Value</th>
            <th style="padding: 10px 12px; text-align: right; color: #495057; font-weight: 600; text-transform: uppercase; font-size: 11px;">Gain/Loss</th>
        </tr>
    </thead>
    <tbody>
    """

    for holding in holdings[:5]:  # Top 5 holdings
        ticker = holding.get("ticker", "")
        value = holding.get("current_value", 0)
        gain_loss_pct = holding.get("gain_loss_pct", 0)

        color = "#27ae60" if gain_loss_pct >= 0 else "#e74c3c"
        sign = "+" if gain_loss_pct >= 0 else ""

        html += f"""
        <tr style="border-bottom: 1px solid #e9ecef;">
            <td style="padding: 12px; color: #2c3e50; font-weight: 600;">{ticker}</td>
            <td style="padding: 12px; text-align: right; color: #2c3e50;">${value:,.2f}</td>
            <td style="padding: 12px; text-align: right; color: {color}; font-weight: 600;">{sign}{gain_loss_pct:.2f}%</td>
        </tr>
        """

    html += "</tbody></table></div>"
    return html


def _build_recommendations(recommendations: List[Dict]) -> str:
    """Build recommendations section with causality flow diagrams."""
    if not recommendations:
        return '<p style="color: #7f8c8d; font-size: 14px;">No recommendations today</p>'

    html = '<div style="display: grid; gap: 24px;">'

    for rec in recommendations:
        symbol = rec.get("symbol", "")
        action = rec.get("action", "")
        conviction_score = rec.get("conviction_score", 0)
        current_price = rec.get("current_price", 0)
        target_price = rec.get("target_price", 0)
        reasoning = rec.get("reasoning", "")
        causality_data = rec.get("causality_data", {})

        action_color = "#27ae60" if action == "BUY" else "#FFC107" if action == "HOLD" else "#e74c3c"
        action_emoji = "🟢" if action == "BUY" else "�" if action == "HOLD" else "�🔴"
        upside = ((target_price / current_price - 1) * 100) if current_price > 0 else 0

        html += f"""
        <div style="background: #ffffff; padding: 20px; border-radius: 8px; border: 2px solid {action_color}20; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
            <!-- Header -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 2px solid #f1f3f5;">
                <div>
                    <span style="color: #2c3e50; font-weight: 700; font-size: 22px;">{action_emoji} {symbol}</span>
                    <span style="background: {action_color}; color: #ffffff; padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 700; margin-left: 12px;">{action}</span>
                </div>
                <div style="text-align: right;">
                    <div style="color: #7f8c8d; font-size: 11px; text-transform: uppercase;">Conviction</div>
                    <div style="color: {action_color}; font-size: 20px; font-weight: 700;">{conviction_score}/10</div>
                </div>
            </div>

            <!-- Price Info -->
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px;">
                <div style="background: #f8f9fa; padding: 12px; border-radius: 6px; text-align: center;">
                    <div style="color: #7f8c8d; font-size: 11px; text-transform: uppercase;">Current</div>
                    <div style="color: #2c3e50; font-size: 18px; font-weight: 700; margin-top: 4px;">${current_price:.2f}</div>
                </div>
                <div style="background: #f8f9fa; padding: 12px; border-radius: 6px; text-align: center;">
                    <div style="color: #7f8c8d; font-size: 11px; text-transform: uppercase;">Target</div>
                    <div style="color: #2c3e50; font-size: 18px; font-weight: 700; margin-top: 4px;">${target_price:.2f}</div>
                </div>
                <div style="background: #e8f5e9; padding: 12px; border-radius: 6px; text-align: center;">
                    <div style="color: #7f8c8d; font-size: 11px; text-transform: uppercase;">Upside</div>
                    <div style="color: #27ae60; font-size: 18px; font-weight: 700; margin-top: 4px;">+{upside:.1f}%</div>
                </div>
            </div>

            <!-- Key Insight -->
            <div style="background: #e3f2fd; padding: 14px; border-radius: 6px; border-left: 4px solid #2196F3; margin-bottom: 16px;">
                <div style="color: #1976D2; font-size: 11px; font-weight: 700; text-transform: uppercase; margin-bottom: 6px;">💡 Key Insight</div>
                <div style="color: #2c3e50; font-size: 14px; line-height: 1.5;">{reasoning}</div>
            </div>

            <!-- Causality Flow Diagram -->
            <div style="background: #fafafa; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                <div style="color: #2c3e50; font-size: 14px; font-weight: 700; margin-bottom: 12px;">📊 Decision Flow: Why {action} {symbol}</div>
                
                <!-- Events Flow -->
                <div style="margin-bottom: 16px;">
                    <div style="color: #546e7a; font-size: 12px; font-weight: 600; margin-bottom: 8px;">1️⃣ KEY EVENTS & CATALYSTS</div>
        """

        # Add events with flow boxes
        events = causality_data.get("events", [])
        for i, event in enumerate(events):
            event_color = {"positive": "#27ae60", "negative": "#e74c3c", "neutral": "#FFC107"}.get(
                event.get("impact", "neutral"), "#7f8c8d"
            )
            event_bg = {"positive": "#e8f5e9", "negative": "#ffebee", "neutral": "#fff3e0"}.get(
                event.get("impact", "neutral"), "#f8f9fa"
            )

            html += f"""
                    <div style="margin-bottom: 8px;">
                        <div style="background: {event_bg}; border: 2px solid {event_color}; padding: 12px 14px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.08);">
                            <div style="color: {event_color}; font-size: 10px; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">{event.get('type', '')} • {event.get('impact', '').upper()}</div>
                            <div style="color: #2c3e50; font-size: 13px; line-height: 1.4;">{event.get('description', '')}</div>
                        </div>
            """

            # Add connecting box if not last event
            if i < len(events) - 1:
                html += f"""
                        <div style="text-align: center; margin: 6px 0;">
                            <div style="width: 2px; height: 12px; background: {event_color}; margin: 0 auto;"></div>
                            <div style="background: {event_color}; color: #ffffff; padding: 4px 12px; border-radius: 4px; display: inline-block; font-size: 11px; font-weight: 700; margin: 4px 0;">↓ LEADS TO</div>
                            <div style="width: 2px; height: 12px; background: {event_color}; margin: 0 auto;"></div>
                        </div>
                    </div>
            """
            else:
                html += "</div>"

        html += """
                </div>

                <!-- Technical Signals -->
                <div style="margin-bottom: 12px;">
                    <div style="color: #546e7a; font-size: 12px; font-weight: 600; margin-bottom: 8px;">2️⃣ TECHNICAL CONFIRMATION</div>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px;">
        """

        # Add technical signals
        technical = causality_data.get("technical_signals", [])
        for tech in technical:
            html += f"""
                        <div style="background: #ffffff; border: 1px solid #e0e0e0; padding: 10px; border-radius: 4px;">
                            <div style="color: #2c3e50; font-size: 12px; font-weight: 600;">{tech.get('indicator', '')}: {tech.get('value', '')}</div>
                            <div style="color: #7f8c8d; font-size: 11px; margin-top: 2px;">{tech.get('signal', '')}</div>
                        </div>
            """

        html += f"""
                    </div>
                </div>

                <!-- Final Recommendation -->
                <div style="text-align: center; padding-top: 12px; border-top: 2px dashed #e0e0e0;">
                    <div style="color: #546e7a; font-size: 12px; font-weight: 600; margin-bottom: 6px;">3️⃣ RECOMMENDATION</div>
                    <div style="background: {action_color}; color: #ffffff; padding: 10px 20px; border-radius: 6px; display: inline-block; font-size: 16px; font-weight: 700;">
                        {action} {symbol} at ${current_price:.2f}
                    </div>
                </div>
            </div>

        </div>
        """

    html += "</div>"
    return html


def _build_holdings_news(holdings_news: List[Dict]) -> str:
    """Build holdings-specific news section."""
    if not holdings_news:
        return ""

    html = '<div style="padding: 24px; border-bottom: 2px solid #f1f3f5;">'
    html += '<h3 style="color: #2c3e50; margin: 0 0 12px 0; font-size: 16px; font-weight: 600;">News About Your Holdings</h3>'
    html += '<div style="display: grid; gap: 12px;">'

    for news in holdings_news:
        ticker = news.get("ticker", "")
        title = news.get("title", "")
        summary = news.get("summary", "")
        sentiment = news.get("sentiment", "Neutral")

        sentiment_color = {"Bullish": "#27ae60", "Bearish": "#e74c3c", "Neutral": "#7f8c8d"}.get(sentiment, "#7f8c8d")

        html += f"""
        <div style="background: #f8f9fa; padding: 12px; border-radius: 6px;">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 4px;">
                <span style="color: #2c3e50; font-weight: 700; font-size: 13px;">{ticker}</span>
                <span style="color: {sentiment_color}; font-size: 11px; font-weight: 600;">{sentiment}</span>
            </div>
            <p style="color: #2c3e50; font-size: 13px; font-weight: 600; margin: 0 0 4px 0; line-height: 1.4;">{title}</p>
            <p style="color: #7f8c8d; font-size: 12px; margin: 0; line-height: 1.4;">{summary}</p>
        </div>
        """

    html += "</div></div>"
    return html
