"""
Daily Digest Generator - Morning Brew Style

Generates personalized daily investment digest with market news and recommendations.
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from utils.enhanced_logging import get_logger
from utils.environment import env
from db.connection_pool import get_db_session

logger = get_logger(__name__)


class DailyDigestGenerator:
    """Generates daily investment digest content."""

    def __init__(self):
        self.alpha_vantage_key = env.get("ALPHA_VANTAGE_API_KEY")

    def generate_market_news_section(self) -> Dict:
        """
        Generate generic market news and highlights.

        Returns:
            Dictionary with market news content
        """
        try:
            # Get market overview
            market_data = self._get_market_overview()

            # Get top news headlines
            headlines = self._get_top_headlines()

            # Get sector performance
            sectors = self._get_sector_performance()

            return {
                "market_summary": market_data,
                "headlines": headlines[:5],  # Top 5 headlines
                "sectors": sectors,
                "generated_at": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Error generating market news: {e}")
            return {"error": str(e)}

    def generate_portfolio_section(self, user_email: str) -> Dict:
        """
        Generate personalized portfolio section.

        Args:
            user_email: User's email address

        Returns:
            Dictionary with portfolio content
        """
        try:
            # Get user's current holdings
            holdings = self._get_user_holdings(user_email)

            # Get today's recommendations
            recommendations = self._get_todays_recommendations(user_email)

            # Get portfolio performance
            performance = self._get_portfolio_performance(user_email)

            # Get holdings news
            holdings_news = self._get_holdings_news(holdings)

            return {
                "holdings": holdings,
                "recommendations": recommendations,
                "performance": performance,
                "holdings_news": holdings_news,
                "generated_at": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Error generating portfolio section: {e}")
            return {"error": str(e)}

    def _get_market_overview(self) -> Dict:
        """Get major indices and market summary."""
        try:
            # Major indices to track
            indices = {"SPY": "S&P 500", "QQQ": "NASDAQ", "DIA": "Dow Jones"}

            market_data = {}

            for symbol, name in indices.items():
                try:
                    # Get quote from Alpha Vantage
                    url = "https://www.alphavantage.co/query"
                    params = {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": self.alpha_vantage_key}

                    response = requests.get(url, params=params, timeout=10)
                    data = response.json()

                    if "Global Quote" in data:
                        quote = data["Global Quote"]
                        market_data[name] = {
                            "price": float(quote.get("05. price", 0)),
                            "change": float(quote.get("09. change", 0)),
                            "change_pct": float(quote.get("10. change percent", "0").replace("%", "")),
                        }
                except Exception as e:
                    logger.error(f"Error fetching {symbol}: {e}")
                    market_data[name] = {"price": 0, "change": 0, "change_pct": 0}

            return market_data

        except Exception as e:
            logger.error(f"Error getting market overview: {e}")
            return {}

    def _get_top_headlines(self) -> List[Dict]:
        """Get top market news headlines."""
        try:
            url = "https://www.alphavantage.co/query"
            params = {"function": "NEWS_SENTIMENT", "apikey": self.alpha_vantage_key, "limit": 10}

            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            headlines = []
            for item in data.get("feed", [])[:5]:
                headlines.append(
                    {
                        "title": item.get("title"),
                        "summary": item.get("summary", "")[:150] + "...",
                        "source": item.get("source"),
                        "sentiment": item.get("overall_sentiment_label", "Neutral"),
                        "url": item.get("url"),
                    }
                )

            return headlines

        except Exception as e:
            logger.error(f"Error getting headlines: {e}")
            return []

    def _get_sector_performance(self) -> List[Dict]:
        """Get sector performance for the day."""
        sectors = [
            {"name": "Technology", "change": 0},
            {"name": "Healthcare", "change": 0},
            {"name": "Financials", "change": 0},
            {"name": "Energy", "change": 0},
            {"name": "Consumer", "change": 0},
        ]

        # In production, fetch real sector data
        # For now, return placeholder
        return sectors

    def _get_user_holdings(self, user_email: str) -> List[Dict]:
        """Get user's current holdings."""
        try:
            with get_db_session() as session:
                query = """
                    SELECT 
                        h.ticker,
                        h.shares,
                        h.avg_cost,
                        h.current_value,
                        h.unrealized_gain_loss,
                        h.unrealized_gain_loss_pct
                    FROM holdings h
                    JOIN investors i ON h.investor_id = i.investor_id
                    WHERE i.email = :email
                    ORDER BY h.current_value DESC
                """

                result = session.execute(query, {"email": user_email})
                rows = result.fetchall()

                holdings = []
                for row in rows:
                    holdings.append(
                        {
                            "ticker": row[0],
                            "shares": float(row[1]),
                            "avg_cost": float(row[2]),
                            "current_value": float(row[3]),
                            "gain_loss": float(row[4]),
                            "gain_loss_pct": float(row[5]),
                        }
                    )

                return holdings

        except Exception as e:
            logger.error(f"Error getting holdings: {e}")
            return []

    def _get_todays_recommendations(self, user_email: str) -> List[Dict]:
        """Get today's trade recommendations with causality analysis."""
        try:
            with get_db_session() as session:
                # Get latest recommendations from today
                query = """
                    SELECT 
                        ticker,
                        action,
                        quantity,
                        estimated_price,
                        signal_score,
                        reasoning
                    FROM trade_recommendations
                    WHERE user_email = :email
                      AND created_at >= CURRENT_DATE
                    ORDER BY signal_score DESC
                    LIMIT 5
                """

                result = session.execute(query, {"email": user_email})
                rows = result.fetchall()

                recommendations = []
                for row in rows:
                    rec = {
                        "ticker": row[0],
                        "action": row[1],
                        "quantity": float(row[2]),
                        "price": float(row[3]),
                        "score": float(row[4]),
                        "reasoning": row[5],
                    }

                    # Add causality analysis for each recommendation
                    try:
                        from services.analysis.stock_causality_analyzer import analyze_stock_recommendation

                        causality_data = analyze_stock_recommendation(rec["ticker"], rec["action"], rec["score"])
                        rec["causality_data"] = causality_data
                    except Exception as e:
                        logger.error(f"Error analyzing causality for {rec['ticker']}: {e}")
                        rec["causality_data"] = None

                    recommendations.append(rec)

                return recommendations

        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return []

    def _get_portfolio_performance(self, user_email: str) -> Dict:
        """Get portfolio performance metrics."""
        try:
            with get_db_session() as session:
                query = """
                    SELECT 
                        SUM(current_value) as total_value,
                        SUM(unrealized_gain_loss) as total_gain_loss,
                        AVG(unrealized_gain_loss_pct) as avg_gain_loss_pct
                    FROM holdings h
                    JOIN investors i ON h.investor_id = i.investor_id
                    WHERE i.email = :email
                """

                result = session.execute(query, {"email": user_email})
                row = result.fetchone()

                if row:
                    return {
                        "total_value": float(row[0] or 0),
                        "total_gain_loss": float(row[1] or 0),
                        "avg_gain_loss_pct": float(row[2] or 0),
                    }

                return {"total_value": 0, "total_gain_loss": 0, "avg_gain_loss_pct": 0}

        except Exception as e:
            logger.error(f"Error getting performance: {e}")
            return {"total_value": 0, "total_gain_loss": 0, "avg_gain_loss_pct": 0}

    def _get_holdings_news(self, holdings: List[Dict]) -> List[Dict]:
        """Get news specific to user's holdings."""
        if not holdings:
            return []

        try:
            # Get news for top 3 holdings
            top_tickers = [h["ticker"] for h in holdings[:3]]
            holdings_news = []

            for ticker in top_tickers:
                try:
                    url = "https://www.alphavantage.co/query"
                    params = {
                        "function": "NEWS_SENTIMENT",
                        "tickers": ticker,
                        "apikey": self.alpha_vantage_key,
                        "limit": 2,
                    }

                    response = requests.get(url, params=params, timeout=10)
                    data = response.json()

                    for item in data.get("feed", [])[:1]:  # One news per holding
                        holdings_news.append(
                            {
                                "ticker": ticker,
                                "title": item.get("title"),
                                "summary": item.get("summary", "")[:100] + "...",
                                "sentiment": item.get("overall_sentiment_label", "Neutral"),
                            }
                        )

                except Exception as e:
                    logger.error(f"Error getting news for {ticker}: {e}")

            return holdings_news

        except Exception as e:
            logger.error(f"Error getting holdings news: {e}")
            return []


def generate_daily_digest(user_email: str) -> Dict:
    """
    Generate complete daily digest for user.

    Args:
        user_email: User's email address

    Returns:
        Dictionary with all digest content
    """
    generator = DailyDigestGenerator()

    return {
        "market_section": generator.generate_market_news_section(),
        "portfolio_section": generator.generate_portfolio_section(user_email),
        "generated_at": datetime.now(),
    }
