"""
Stock Causality Analyzer

Analyzes the causal chain of events leading to stock recommendations.
Scrapes real news, earnings, insider trades, and market events to build
a comprehensive flow chart of factors affecting stock price.
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from utils.enhanced_logging import get_logger
from utils.environment import env
from db.connection_pool import get_db_session

logger = get_logger(__name__)


@dataclass
class CausalEvent:
    """Represents a single event in the causal chain."""

    event_type: str  # earnings, news, insider_trade, technical, institutional
    timestamp: datetime
    title: str
    description: str
    impact: str  # positive, negative, neutral
    magnitude: float  # 0-1 scale
    source: str
    url: Optional[str] = None


class StockCausalityAnalyzer:
    """Analyzes causal factors for stock recommendations."""

    def __init__(self):
        self.alpha_vantage_key = env.get("ALPHA_VANTAGE_API_KEY")
        self.finnhub_key = env.get("FINNHUB_API_KEY")

    def analyze_recommendation(self, ticker: str, action: str, signal_score: float) -> Dict:
        """
        Analyze all factors leading to a recommendation.

        Args:
            ticker: Stock ticker
            action: BUY or SELL
            signal_score: Recommendation confidence score

        Returns:
            Dictionary with causal chain and flow chart data
        """
        logger.info(f"Analyzing causality for {ticker} {action} recommendation")

        # Gather all causal events
        events = []

        # 1. Recent news events
        news_events = self._get_news_events(ticker)
        events.extend(news_events)

        # 2. Earnings events
        earnings_events = self._get_earnings_events(ticker)
        events.extend(earnings_events)

        # 3. Insider trading activity
        insider_events = self._get_insider_events(ticker)
        events.extend(insider_events)

        # 4. Institutional activity (13F)
        institutional_events = self._get_institutional_events(ticker)
        events.extend(institutional_events)

        # 5. Technical indicators
        technical_events = self._get_technical_events(ticker)
        events.extend(technical_events)

        # 6. Price movements
        price_events = self._get_price_events(ticker)
        events.extend(price_events)

        # Sort events chronologically
        events.sort(key=lambda x: x.timestamp, reverse=True)

        # Build causal chain
        causal_chain = self._build_causal_chain(events, action, signal_score)

        return {
            "ticker": ticker,
            "action": action,
            "signal_score": signal_score,
            "causal_chain": causal_chain,
            "total_events": len(events),
            "analyzed_at": datetime.now(),
        }

    def _get_news_events(self, ticker: str) -> List[CausalEvent]:
        """Scrape recent news events for the stock."""
        events = []

        try:
            # Alpha Vantage News
            if self.alpha_vantage_key:
                url = "https://www.alphavantage.co/query"
                params = {
                    "function": "NEWS_SENTIMENT",
                    "tickers": ticker,
                    "apikey": self.alpha_vantage_key,
                    "limit": 10,
                    "time_from": (datetime.now() - timedelta(days=30)).strftime("%Y%m%dT%H%M"),
                }

                response = requests.get(url, params=params, timeout=30)
                data = response.json()

                for item in data.get("feed", [])[:5]:
                    sentiment_score = float(item.get("overall_sentiment_score", 0))

                    events.append(
                        CausalEvent(
                            event_type="news",
                            timestamp=datetime.strptime(item.get("time_published"), "%Y%m%dT%H%M%S"),
                            title=item.get("title", ""),
                            description=item.get("summary", "")[:200],
                            impact=(
                                "positive"
                                if sentiment_score > 0.15
                                else "negative" if sentiment_score < -0.15 else "neutral"
                            ),
                            magnitude=abs(sentiment_score),
                            source=item.get("source", ""),
                            url=item.get("url"),
                        )
                    )

            # Finnhub News
            if self.finnhub_key:
                url = "https://finnhub.io/api/v1/company-news"
                params = {
                    "symbol": ticker,
                    "from": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                    "to": datetime.now().strftime("%Y-%m-%d"),
                    "token": self.finnhub_key,
                }

                response = requests.get(url, params=params, timeout=30)
                data = response.json()

                for item in data[:5]:
                    # Simple sentiment analysis
                    headline = item.get("headline", "").lower()
                    sentiment = self._analyze_headline_sentiment(headline)

                    events.append(
                        CausalEvent(
                            event_type="news",
                            timestamp=datetime.fromtimestamp(item.get("datetime")),
                            title=item.get("headline", ""),
                            description=item.get("summary", "")[:200],
                            impact=sentiment["impact"],
                            magnitude=sentiment["magnitude"],
                            source=item.get("source", ""),
                            url=item.get("url"),
                        )
                    )

        except Exception as e:
            logger.error(f"Error fetching news events: {e}")

        return events

    def _get_earnings_events(self, ticker: str) -> List[CausalEvent]:
        """Get recent earnings announcements and surprises."""
        events = []

        try:
            if self.alpha_vantage_key:
                url = "https://www.alphavantage.co/query"
                params = {"function": "EARNINGS", "symbol": ticker, "apikey": self.alpha_vantage_key}

                response = requests.get(url, params=params, timeout=30)
                data = response.json()

                for earnings in data.get("quarterlyEarnings", [])[:2]:
                    reported_eps = float(earnings.get("reportedEPS", 0) or 0)
                    estimated_eps = float(earnings.get("estimatedEPS", 0) or 0)
                    surprise = reported_eps - estimated_eps
                    surprise_pct = (surprise / estimated_eps * 100) if estimated_eps != 0 else 0

                    events.append(
                        CausalEvent(
                            event_type="earnings",
                            timestamp=datetime.strptime(earnings.get("reportedDate"), "%Y-%m-%d"),
                            title=f"Q{earnings.get('fiscalDateEnding', '')[-5:-3]} Earnings Report",
                            description=f"Reported EPS: ${reported_eps:.2f} vs Est: ${estimated_eps:.2f}. Surprise: {surprise_pct:+.1f}%",
                            impact="positive" if surprise > 0 else "negative" if surprise < 0 else "neutral",
                            magnitude=min(abs(surprise_pct) / 20, 1.0),
                            source="Alpha Vantage",
                        )
                    )

        except Exception as e:
            logger.error(f"Error fetching earnings events: {e}")

        return events

    def _get_insider_events(self, ticker: str) -> List[CausalEvent]:
        """Get recent insider trading activity."""
        events = []

        try:
            with get_db_session() as session:
                query = """
                    SELECT 
                        transaction_date,
                        insider_name,
                        transaction_type,
                        shares,
                        price_per_share
                    FROM insider_trades
                    WHERE ticker = :ticker
                      AND transaction_date >= :start_date
                    ORDER BY transaction_date DESC
                    LIMIT 5
                """

                result = session.execute(query, {"ticker": ticker, "start_date": datetime.now() - timedelta(days=90)})

                for row in result.fetchall():
                    trans_type = row[2]
                    shares = float(row[3])
                    price = float(row[4])
                    value = shares * price

                    events.append(
                        CausalEvent(
                            event_type="insider_trade",
                            timestamp=row[0],
                            title=f"Insider {trans_type}",
                            description=f"{row[1]} {trans_type.lower()} {shares:,.0f} shares at ${price:.2f} (${value:,.0f} total)",
                            impact="positive" if trans_type == "BUY" else "negative",
                            magnitude=min(value / 1000000, 1.0),
                            source="SEC Form 4",
                        )
                    )

        except Exception as e:
            logger.error(f"Error fetching insider events: {e}")

        return events

    def _get_institutional_events(self, ticker: str) -> List[CausalEvent]:
        """Get recent institutional activity from 13F filings."""
        events = []

        try:
            with get_db_session() as session:
                query = """
                    SELECT 
                        filing_date,
                        investor_name,
                        shares,
                        change_type,
                        change_pct
                    FROM holdings
                    WHERE ticker = :ticker
                      AND filing_date >= :start_date
                      AND change_type IN ('NEW', 'INCREASED', 'DECREASED', 'SOLD_OUT')
                    ORDER BY filing_date DESC, shares DESC
                    LIMIT 5
                """

                result = session.execute(query, {"ticker": ticker, "start_date": datetime.now() - timedelta(days=180)})

                for row in result.fetchall():
                    change_type = row[3]
                    change_pct = float(row[4] or 0)

                    impact_map = {
                        "NEW": "positive",
                        "INCREASED": "positive",
                        "DECREASED": "negative",
                        "SOLD_OUT": "negative",
                    }

                    events.append(
                        CausalEvent(
                            event_type="institutional",
                            timestamp=row[0],
                            title=f"Institutional {change_type.title()}",
                            description=f"{row[1]} {change_type.lower()} position: {row[2]:,.0f} shares ({change_pct:+.1f}%)",
                            impact=impact_map.get(change_type, "neutral"),
                            magnitude=min(abs(change_pct) / 50, 1.0),
                            source="13F Filing",
                        )
                    )

        except Exception as e:
            logger.error(f"Error fetching institutional events: {e}")

        return events

    def _get_technical_events(self, ticker: str) -> List[CausalEvent]:
        """Get significant technical indicator signals."""
        events = []

        try:
            with get_db_session() as session:
                query = """
                    SELECT 
                        date,
                        rsi_14,
                        macd,
                        macd_signal,
                        adx_14,
                        volume_ratio
                    FROM technical_indicators
                    WHERE ticker = :ticker
                      AND date >= :start_date
                    ORDER BY date DESC
                    LIMIT 5
                """

                result = session.execute(query, {"ticker": ticker, "start_date": datetime.now() - timedelta(days=30)})

                for row in result.fetchall():
                    rsi = float(row[1] or 50)
                    macd = float(row[2] or 0)
                    macd_signal = float(row[3] or 0)
                    adx = float(row[4] or 0)
                    volume_ratio = float(row[5] or 1)

                    # RSI signals
                    if rsi > 70:
                        events.append(
                            CausalEvent(
                                event_type="technical",
                                timestamp=row[0],
                                title="Overbought Signal",
                                description=f"RSI at {rsi:.1f}, indicating overbought conditions",
                                impact="negative",
                                magnitude=(rsi - 70) / 30,
                                source="Technical Analysis",
                            )
                        )
                    elif rsi < 30:
                        events.append(
                            CausalEvent(
                                event_type="technical",
                                timestamp=row[0],
                                title="Oversold Signal",
                                description=f"RSI at {rsi:.1f}, indicating oversold conditions",
                                impact="positive",
                                magnitude=(30 - rsi) / 30,
                                source="Technical Analysis",
                            )
                        )

                    # MACD crossover
                    if macd > macd_signal and abs(macd - macd_signal) > 0.5:
                        events.append(
                            CausalEvent(
                                event_type="technical",
                                timestamp=row[0],
                                title="Bullish MACD Crossover",
                                description=f"MACD crossed above signal line, indicating bullish momentum",
                                impact="positive",
                                magnitude=min(abs(macd - macd_signal) / 2, 1.0),
                                source="Technical Analysis",
                            )
                        )

        except Exception as e:
            logger.error(f"Error fetching technical events: {e}")

        return events

    def _get_price_events(self, ticker: str) -> List[CausalEvent]:
        """Get significant price movements."""
        events = []

        try:
            with get_db_session() as session:
                query = """
                    SELECT 
                        date,
                        close,
                        volume,
                        LAG(close) OVER (ORDER BY date) as prev_close
                    FROM price_history
                    WHERE ticker = :ticker
                      AND date >= :start_date
                    ORDER BY date DESC
                    LIMIT 20
                """

                result = session.execute(query, {"ticker": ticker, "start_date": datetime.now() - timedelta(days=30)})

                for row in result.fetchall():
                    if row[3]:  # prev_close exists
                        price_change_pct = ((row[1] - row[3]) / row[3]) * 100

                        if abs(price_change_pct) > 5:  # Significant move
                            events.append(
                                CausalEvent(
                                    event_type="price_movement",
                                    timestamp=row[0],
                                    title=f"Significant Price {'Increase' if price_change_pct > 0 else 'Decrease'}",
                                    description=f"Stock moved {price_change_pct:+.1f}% to ${row[1]:.2f} on volume {row[2]:,.0f}",
                                    impact="positive" if price_change_pct > 0 else "negative",
                                    magnitude=min(abs(price_change_pct) / 10, 1.0),
                                    source="Market Data",
                                )
                            )

        except Exception as e:
            logger.error(f"Error fetching price events: {e}")

        return events

    def _analyze_headline_sentiment(self, headline: str) -> Dict:
        """Simple sentiment analysis for headlines."""
        positive_words = [
            "beat",
            "surge",
            "growth",
            "profit",
            "gain",
            "up",
            "rise",
            "strong",
            "positive",
            "bullish",
            "upgrade",
            "buy",
        ]
        negative_words = [
            "miss",
            "drop",
            "loss",
            "decline",
            "down",
            "fall",
            "weak",
            "negative",
            "bearish",
            "downgrade",
            "sell",
        ]

        headline_lower = headline.lower()
        positive_count = sum(1 for word in positive_words if word in headline_lower)
        negative_count = sum(1 for word in negative_words if word in headline_lower)

        total = positive_count + negative_count
        if total == 0:
            return {"impact": "neutral", "magnitude": 0.1}

        score = (positive_count - negative_count) / total

        if score > 0.3:
            return {"impact": "positive", "magnitude": min(score, 1.0)}
        elif score < -0.3:
            return {"impact": "negative", "magnitude": min(abs(score), 1.0)}
        else:
            return {"impact": "neutral", "magnitude": 0.2}

    def _build_causal_chain(self, events: List[CausalEvent], action: str, signal_score: float) -> List[Dict]:
        """Build the causal chain from events to recommendation."""
        chain = []

        # Group events by type and impact
        positive_events = [e for e in events if e.impact == "positive"]
        negative_events = [e for e in events if e.impact == "negative"]

        # Step 1: Market Context
        chain.append(
            {
                "step": 1,
                "title": "Market Context",
                "description": f"Analyzed {len(events)} events over the past 30-90 days",
                "details": f"Found {len(positive_events)} positive signals and {len(negative_events)} negative signals",
                "impact": "neutral",
                "events": [],
            }
        )

        # Step 2: Key Events (top 3-5 most impactful)
        sorted_events = sorted(events, key=lambda x: x.magnitude, reverse=True)[:5]
        for i, event in enumerate(sorted_events):
            chain.append(
                {
                    "step": i + 2,
                    "title": event.title,
                    "description": event.description,
                    "details": f"Source: {event.source} | Date: {event.timestamp.strftime('%Y-%m-%d')} | Impact: {event.impact.title()}",
                    "impact": event.impact,
                    "events": [event],
                }
            )

        # Final step: Recommendation
        chain.append(
            {
                "step": len(chain) + 1,
                "title": f"{action} Recommendation",
                "description": f"Based on analysis of all factors, system recommends {action}",
                "details": f"Signal Score: {signal_score:.2f} | Confidence: {signal_score * 100:.0f}%",
                "impact": "positive" if action == "BUY" else "negative",
                "events": [],
            }
        )

        return chain


def analyze_stock_recommendation(ticker: str, action: str, signal_score: float) -> Dict:
    """
    Main entry point for stock causality analysis.

    Args:
        ticker: Stock ticker
        action: BUY or SELL
        signal_score: Recommendation confidence

    Returns:
        Complete causality analysis with flow chart data
    """
    analyzer = StockCausalityAnalyzer()
    return analyzer.analyze_recommendation(ticker, action, signal_score)
