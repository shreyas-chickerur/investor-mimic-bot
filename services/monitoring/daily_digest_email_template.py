"""
Daily Digest Email Template - Morning Brew Style

Professional, clean email template for daily investment digest.
"""

from datetime import datetime
from typing import Dict, List


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
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8f9fa; line-height: 1.6;">
        <div style="max-width: 680px; margin: 20px auto; background-color: #ffffff; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-radius: 8px; overflow: hidden;">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 32px 24px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">📈 Daily Investment Digest</h1>
                <p style="color: #e0e7ff; margin: 8px 0 0 0; font-size: 14px;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>
            
            <!-- Greeting -->
            <div style="padding: 24px 24px 16px 24px; border-bottom: 2px solid #f1f3f5;">
                <p style="color: #2c3e50; font-size: 16px; margin: 0;">Good morning, {user_name}! ☀️</p>
            </div>
            
            <!-- Market Section -->
            <div style="padding: 24px; border-bottom: 2px solid #f1f3f5;">
                <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 20px; font-weight: 700;">📊 Market Overview</h2>
                {market_summary_html}
            </div>
            
            <!-- Headlines Section -->
            <div style="padding: 24px; border-bottom: 2px solid #f1f3f5;">
                <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 20px; font-weight: 700;">📰 Top Headlines</h2>
                {headlines_html}
            </div>
            
            <!-- Portfolio Section -->
            <div style="padding: 24px; background-color: #f8f9fa; border-bottom: 2px solid #e9ecef;">
                <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 20px; font-weight: 700;">💼 Your Portfolio</h2>
                {performance_html}
            </div>
            
            <!-- Holdings Section -->
            <div style="padding: 24px; border-bottom: 2px solid #f1f3f5;">
                <h3 style="color: #2c3e50; margin: 0 0 12px 0; font-size: 16px; font-weight: 600;">Current Holdings</h3>
                {holdings_html}
            </div>
            
            <!-- Recommendations Section -->
            <div style="padding: 24px; background-color: #fff8e1; border-bottom: 2px solid #ffe082;">
                <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 20px; font-weight: 700;">🎯 Today's Recommendations</h2>
                {recommendations_html}
            </div>
            
            <!-- Holdings News Section -->
            {holdings_news_html}
            
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
    """Build market summary section."""
    if not market_data:
        return '<p style="color: #7f8c8d; font-size: 14px;">Market data unavailable</p>'

    html = '<div style="display: grid; gap: 12px;">'

    for name, data in market_data.items():
        change = data.get("change", 0)
        change_pct = data.get("change_pct", 0)
        color = "#27ae60" if change >= 0 else "#e74c3c"
        arrow = "↑" if change >= 0 else "↓"

        html += f"""
        <div style="background: #f8f9fa; padding: 12px 16px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
            <span style="color: #2c3e50; font-weight: 600; font-size: 14px;">{name}</span>
            <span style="color: {color}; font-weight: 600; font-size: 14px;">{arrow} {abs(change_pct):.2f}%</span>
        </div>
        """

    html += "</div>"
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
    """Build recommendations section."""
    if not recommendations:
        return '<p style="color: #7f8c8d; font-size: 14px;">No recommendations today</p>'

    html = '<div style="display: grid; gap: 12px;">'

    for rec in recommendations:
        ticker = rec.get("ticker", "")
        action = rec.get("action", "")
        score = rec.get("score", 0)
        reasoning = rec.get("reasoning", "")

        action_color = "#27ae60" if action == "BUY" else "#e74c3c"
        action_emoji = "🟢" if action == "BUY" else "🔴"

        html += f"""
        <div style="background: #ffffff; padding: 16px; border-radius: 6px; border-left: 4px solid {action_color};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="color: #2c3e50; font-weight: 700; font-size: 16px;">{action_emoji} {ticker}</span>
                <span style="background: {action_color}; color: #ffffff; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: 600;">{action}</span>
            </div>
            <p style="color: #7f8c8d; font-size: 12px; margin: 0; line-height: 1.5;">{reasoning[:100]}...</p>
            <p style="color: #95a5a6; font-size: 11px; margin: 8px 0 0 0;">Signal Score: {score:.2f}</p>
        </div>
        """

    html += "</div>"
    return html


def _build_holdings_news(holdings_news: List[Dict]) -> str:
    """Build holdings-specific news section."""
    if not holdings_news:
        return ""

    html = '<div style="padding: 24px; border-bottom: 2px solid #f1f3f5;">'
    html += '<h3 style="color: #2c3e50; margin: 0 0 12px 0; font-size: 16px; font-weight: 600;">📢 News About Your Holdings</h3>'
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
