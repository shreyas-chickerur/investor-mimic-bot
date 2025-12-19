"""SEC EDGAR API client for fetching 13F filings."""

# Standard library imports
import asyncio
import logging
import ssl
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

# Third-party imports
import aiohttp
import certifi
import pandas as pd
from bs4 import BeautifulSoup

# Local application imports
from config import settings
from config.investors import INVESTORS

logger = logging.getLogger(__name__)

BASE_URL = "https://www.sec.gov/"
EDGAR_SEARCH_URL = urljoin(BASE_URL, "cgi-bin/browse-edgar")
EDGAR_ARCHIVE_URL = "https://www.sec.gov/Archives/"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/"

# SEC rate limiting: 10 requests per second, so we'll be conservative
REQUEST_DELAY = 0.2  # 200ms between requests


class SECClient:
    """Client for interacting with SEC EDGAR system."""

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """Initialize the SEC client.

        Args:
            session: Optional aiohttp ClientSession for making HTTP requests.
        """
        contact_email = getattr(settings, "CONTACT_EMAIL", None)
        contact = contact_email or "admin@example.com"
        if session is not None:
            self.session = session
            return

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(
            connector=connector,
            headers={
                "User-Agent": f"InvestorMimicBot/1.0 ({contact})",
                "Accept": (
                    "application/json,text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),
                "Accept-Encoding": "gzip, deflate",
            },
        )

    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _get(self, url: str, params: Optional[Dict] = None) -> str:
        """Make a GET request to the SEC EDGAR system.

        Args:
            url: URL to fetch
            params: Query parameters

        Returns:
            Response text

        Raises:
            aiohttp.ClientError: If the request fails
        """
        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            logger.error(f"Failed to fetch {url}: {str(e)}")
            raise

    async def _get_json(self, url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a GET request expecting JSON."""
        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                # SEC sometimes serves JSON with a text/html content-type.
                # aiohttp will refuse to decode unless we disable the content-type check.
                return await response.json(content_type=None)
        except aiohttp.ContentTypeError as e:
            status = getattr(e, "status", None)
            content_type = getattr(e, "content_type", None)
            logger.error(
                f"Failed to decode JSON {url}: status={status} "
                f"content_type={content_type} error={str(e)}"
            )
            raise
        except aiohttp.ClientResponseError as e:
            logger.error(f"Failed to fetch JSON {url}: status={e.status} message={e.message}")
            raise
        except aiohttp.ClientError as e:
            logger.error(f"Failed to fetch JSON {url}: {str(e)}")
            raise

    async def _get_filing_urls(
        self,
        cik: str,
        form_type: str = "13F-HR",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        count: int = 10,
    ) -> List[Dict]:
        """Get filing metadata for all filings matching the criteria."""
        try:
            cik_padded = cik.zfill(10)
            submissions_url = urljoin(SUBMISSIONS_URL, f"CIK{cik_padded}.json")
            submissions = await self._get_json(submissions_url)

            recent = submissions.get("filings", {}).get("recent", {})
            forms: List[str] = recent.get("form", [])
            accession_numbers: List[str] = recent.get("accessionNumber", [])
            filing_dates: List[str] = recent.get("filingDate", [])

            filings: List[Dict[str, Any]] = []
            for form, accession, filing_date in zip(forms, accession_numbers, filing_dates):
                if form != form_type:
                    continue

                try:
                    filing_dt = datetime.strptime(filing_date, "%Y-%m-%d")
                except ValueError:
                    continue

                if start_date and filing_dt < start_date:
                    continue
                if end_date and filing_dt > end_date:
                    continue

                accession_no_dashes = accession.replace("-", "")
                cik_no_leading_zeros = str(int(cik_padded))
                filing_base_url = urljoin(
                    EDGAR_ARCHIVE_URL,
                    f"edgar/data/{cik_no_leading_zeros}/{accession_no_dashes}/",
                )
                index_json_url = urljoin(filing_base_url, "index.json")
                index_html_url = urljoin(filing_base_url, f"{accession}-index.html")

                filings.append(
                    {
                        "cik": cik_padded,
                        "filing_date": filing_date,
                        "form_type": form,
                        "accession_number": accession,
                        "filing_url": index_html_url,
                        "index_json_url": index_json_url,
                        "filing_base_url": filing_base_url,
                    }
                )

                if len(filings) >= count:
                    break

                await asyncio.sleep(REQUEST_DELAY)

            return filings

        except Exception as e:
            logger.error(f"Error fetching filings for CIK {cik}: {str(e)}")
            return []

    async def _parse_13f_filing(self, index_json_url: str) -> pd.DataFrame:
        """Parse a 13F-HR filing and extract holdings from the information table XML."""
        try:
            index_json = await self._get_json(index_json_url)
            items = index_json.get("directory", {}).get("item", [])
            xml_files = [
                i.get("name", "") for i in items if str(i.get("name", "")).lower().endswith(".xml")
            ]
            if not xml_files:
                logger.warning(f"No XML files found in filing index: {index_json_url}")
                return pd.DataFrame()

            preferred = [
                f
                for f in xml_files
                if any(k in f.lower() for k in ["infotable", "informationtable", "form13f", "13f"])
            ]
            xml_name = preferred[0] if preferred else xml_files[0]
            base_url = index_json_url.rsplit("/", 1)[0] + "/"
            xml_url = urljoin(base_url, xml_name)

            xml_text = await self._get(xml_url)
            soup = BeautifulSoup(xml_text, "lxml-xml")

            def find_text(parent: Any, tag_name: str) -> str:
                tag = parent.find(lambda t: t.name and t.name.lower() == tag_name.lower())
                if not tag or tag.text is None:
                    return ""
                return tag.text.strip()

            holdings = []
            for info_table in soup.find_all(lambda t: t.name and t.name.lower() == "infotable"):
                shrs_or_prn_amt = info_table.find(
                    lambda t: t.name and t.name.lower() == "shrsorprnamt"
                )
                voting_auth = info_table.find(
                    lambda t: t.name and t.name.lower() == "votingauthority"
                )

                shares = "0"
                if shrs_or_prn_amt is not None:
                    shares = find_text(shrs_or_prn_amt, "sshPrnamt") or find_text(
                        shrs_or_prn_amt, "sshprnamt"
                    )

                holding = {
                    "nameOfIssuer": find_text(info_table, "nameOfIssuer"),
                    "titleOfClass": find_text(info_table, "titleOfClass"),
                    "cusip": find_text(info_table, "cusip"),
                    "value": int(float(find_text(info_table, "value") or "0") * 1000),
                    "shares": int(float(shares or "0")),
                    "putCall": find_text(info_table, "putCall"),
                    "investmentDiscretion": find_text(info_table, "investmentDiscretion"),
                    "votingAuthority": {
                        "sole": (
                            int(float(find_text(voting_auth, "sole") or "0")) if voting_auth else 0
                        ),
                        "shared": (
                            int(float(find_text(voting_auth, "shared") or "0"))
                            if voting_auth
                            else 0
                        ),
                        "none": (
                            int(float(find_text(voting_auth, "none") or "0")) if voting_auth else 0
                        ),
                    },
                }
                holdings.append(holding)

            return pd.DataFrame(holdings) if holdings else pd.DataFrame()

        except Exception as e:
            logger.error(f"Error parsing 13F filing index {index_json_url}: {str(e)}")
            return pd.DataFrame()

    async def get_latest_13f_holdings(self, cik: str, max_filings: int = 1) -> Dict:
        """Get the latest 13F holdings for a given CIK.

        Args:
            cik: Company/Investor CIK number (with leading zeros)
            max_filings: Maximum number of filings to process

        Returns:
            Dictionary containing filing metadata and holdings DataFrame
        """
        # Get the most recent filings
        filings = await self._get_filing_urls(cik, form_type="13F-HR", count=max_filings)

        if not filings:
            return {}

        # Process each filing
        results = []
        for filing in filings[:max_filings]:
            holdings = await self._parse_13f_filing(filing["index_json_url"])
            if not holdings.empty:
                filing["holdings"] = holdings
                results.append(filing)

        if not results:
            return {}

        # Backwards compatible: historically returned a single dict
        if max_filings <= 1:
            return results[0]

        return results

    async def get_all_investor_holdings(self, max_filings_per_investor: int = 1) -> Dict[str, Dict]:
        """Get holdings for all configured investors.

        Args:
            max_filings_per_investor: Maximum number of filings to process per investor

        Returns:
            Dictionary mapping investor names to their holdings data
        """
        results = {}

        for investor in INVESTORS:
            try:
                logger.info(f"Fetching holdings for {investor['name']} (CIK: {investor['cik']})")
                holdings = await self.get_latest_13f_holdings(
                    cik=investor["cik"], max_filings=max_filings_per_investor
                )

                if holdings:
                    results[investor["name"]] = holdings

                # Respect rate limiting between investors
                await asyncio.sleep(REQUEST_DELAY * 2)

            except Exception as e:
                logger.error(f"Error processing {investor['name']}: {str(e)}")
                continue

        return results
