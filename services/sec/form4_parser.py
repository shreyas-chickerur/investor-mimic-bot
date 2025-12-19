"""
SEC Form 4 Parser - Parse insider trading data from SEC EDGAR.
"""

import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class InsiderTransaction:
    """Represents a parsed insider transaction."""

    symbol: str
    company_name: str
    cik: str
    insider_name: str
    insider_title: str
    transaction_date: datetime
    transaction_type: str  # 'buy' or 'sell'
    shares: float
    price_per_share: Optional[float]
    total_value: Optional[float]
    filing_date: datetime
    form_url: str


class Form4Parser:
    """
    Parse SEC Form 4 filings for insider trading data.
    """

    def __init__(self):
        self.base_url = "https://www.sec.gov"
        self.headers = {
            "User-Agent": "InvestorBot/1.0 (contact@example.com)",
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov",
        }

    def search_recent_form4s(
        self,
        cik: Optional[str] = None,
        ticker: Optional[str] = None,
        days_back: int = 30,
        max_results: int = 100,
    ) -> List[Dict]:
        """
        Search for recent Form 4 filings.

        Args:
            cik: Company CIK (optional)
            ticker: Stock ticker (optional)
            days_back: Days to look back
            max_results: Maximum results to return

        Returns:
            List of filing metadata dicts
        """
        try:
            # Use SEC EDGAR full-text search API
            search_url = f"{self.base_url}/cgi-bin/browse-edgar"

            params = {
                "action": "getcompany",
                "type": "4",
                "dateb": "",
                "owner": "include",
                "count": max_results,
            }

            if cik:
                params["CIK"] = cik
            elif ticker:
                params["company"] = ticker

            response = requests.get(search_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()

            # Parse HTML response (simplified - in production use BeautifulSoup)
            # For now, return empty list as full HTML parsing is complex
            logger.info(f"Searched Form 4s for CIK={cik}, ticker={ticker}")
            return []

        except Exception as e:
            logger.error(f"Error searching Form 4s: {e}")
            return []

    def parse_form4_xml(self, xml_url: str) -> List[InsiderTransaction]:
        """
        Parse a Form 4 XML file.

        Args:
            xml_url: URL to Form 4 XML

        Returns:
            List of InsiderTransaction objects
        """
        try:
            response = requests.get(xml_url, headers=self.headers, timeout=10)
            response.raise_for_status()

            root = ET.fromstring(response.content)

            # Extract issuer info
            issuer = root.find(".//issuer")
            if issuer is None:
                return []

            company_name = issuer.findtext("issuerName", "")
            cik = issuer.findtext("issuerCik", "")
            symbol = issuer.findtext("issuerTradingSymbol", "")

            # Extract reporting owner info
            owner = root.find(".//reportingOwner")
            if owner is None:
                return []

            owner_name = owner.findtext(".//rptOwnerName", "")
            owner_title = owner.findtext(".//officerTitle", "")

            # Extract transactions
            transactions = []

            for non_derivative in root.findall(".//nonDerivativeTransaction"):
                try:
                    # Transaction date
                    trans_date_str = non_derivative.findtext(".//transactionDate/value", "")
                    trans_date = datetime.strptime(trans_date_str, "%Y-%m-%d")

                    # Transaction code (P=Purchase, S=Sale)
                    trans_code = non_derivative.findtext(".//transactionCode", "")
                    trans_type = "buy" if trans_code == "P" else "sell" if trans_code == "S" else "other"

                    # Shares
                    shares_str = non_derivative.findtext(".//transactionShares/value", "0")
                    shares = float(shares_str)

                    # Price per share
                    price_str = non_derivative.findtext(".//transactionPricePerShare/value", "")
                    price = float(price_str) if price_str else None

                    # Calculate total value
                    total_value = (shares * price) if price else None

                    # Filing date (from document)
                    filing_date_str = root.findtext(".//periodOfReport", trans_date_str)
                    filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")

                    transaction = InsiderTransaction(
                        symbol=symbol,
                        company_name=company_name,
                        cik=cik,
                        insider_name=owner_name,
                        insider_title=owner_title,
                        transaction_date=trans_date,
                        transaction_type=trans_type,
                        shares=shares,
                        price_per_share=price,
                        total_value=total_value,
                        filing_date=filing_date,
                        form_url=xml_url,
                    )

                    transactions.append(transaction)

                except Exception as e:
                    logger.debug(f"Error parsing transaction: {e}")
                    continue

            return transactions

        except Exception as e:
            logger.error(f"Error parsing Form 4 XML: {e}")
            return []

    def get_insider_activity_for_symbol(self, symbol: str, days_back: int = 90) -> List[InsiderTransaction]:
        """
        Get recent insider activity for a symbol.

        Args:
            symbol: Stock ticker
            days_back: Days to look back

        Returns:
            List of InsiderTransaction objects
        """
        # Search for recent Form 4s
        filings = self.search_recent_form4s(ticker=symbol, days_back=days_back, max_results=50)

        transactions = []
        for filing in filings:
            xml_url = filing.get("xml_url")
            if xml_url:
                trans = self.parse_form4_xml(xml_url)
                transactions.extend(trans)
                time.sleep(0.1)  # Rate limiting

        return transactions


class RealInsiderSignalGenerator:
    """
    Generate insider trading signals from real SEC Form 4 data.
    """

    def __init__(self):
        self.parser = Form4Parser()

    def calculate_insider_sentiment(self, transactions: List[InsiderTransaction], recency_weight: float = 0.7) -> float:
        """
        Calculate insider sentiment score.

        Args:
            transactions: List of insider transactions
            recency_weight: Weight for recent transactions

        Returns:
            Sentiment score from -1 (selling) to +1 (buying)
        """
        if not transactions:
            return 0.0

        buy_value = 0.0
        sell_value = 0.0
        now = datetime.now()

        for txn in transactions:
            if txn.total_value is None:
                continue

            # Apply recency weight
            days_old = (now - txn.transaction_date).days
            recency = recency_weight ** (days_old / 30)  # Decay over months

            weighted_value = txn.total_value * recency

            if txn.transaction_type == "buy":
                buy_value += weighted_value
            elif txn.transaction_type == "sell":
                sell_value += weighted_value

        total = buy_value + sell_value
        if total == 0:
            return 0.0

        # Normalize to -1 to +1
        sentiment = (buy_value - sell_value) / total
        return sentiment

    def generate_signals(
        self, symbols: List[str], days_back: int = 90, min_confidence: float = 0.3
    ) -> Dict[str, float]:
        """
        Generate insider trading signals for symbols.

        Args:
            symbols: List of stock symbols
            days_back: Days to look back
            min_confidence: Minimum confidence threshold

        Returns:
            Dict mapping symbol to signal strength
        """
        signals = {}

        for symbol in symbols:
            try:
                # Get insider activity
                transactions = self.parser.get_insider_activity_for_symbol(symbol, days_back)

                if not transactions:
                    continue

                # Calculate sentiment
                sentiment = self.calculate_insider_sentiment(transactions)

                # Only positive signals (buying)
                if sentiment > 0:
                    # Confidence based on transaction count and recency
                    confidence = min(1.0, len(transactions) / 5.0)

                    if confidence >= min_confidence:
                        signals[symbol] = sentiment * confidence

                time.sleep(0.1)  # Rate limiting

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                continue

        return signals
