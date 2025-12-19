#!/usr/bin/env python3
"""
Script to load 13F filings data into PostgreSQL database.
"""
# Standard library imports
import argparse
import csv
import json
import logging
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Third-party imports
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SEC13FLoader:
    def __init__(self, db_url: str = None):
        """Initialize the loader with database connection."""
        self.db_url = db_url or os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/investorbot")
        self.conn = None
        self.cur = None
        self.investor_cache = {}
        self.security_cache = {}

    def connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(self.db_url)
            self.conn.autocommit = False
            self.cur = self.conn.cursor()
            logger.info("Connected to database")
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    def close(self):
        """Close database connection."""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def load_investor(self, name: str, cik: str) -> str:
        """Load or get investor ID."""
        if cik in self.investor_cache:
            return self.investor_cache[cik]

        # Check if investor exists
        self.cur.execute(
            """
            INSERT INTO investors (name, cik)
            VALUES (%s, %s)
            ON CONFLICT (cik) DO UPDATE
            SET name = EXCLUDED.name
            RETURNING investor_id
            """,
            (name, cik),
        )
        investor_id = self.cur.fetchone()[0]
        self.investor_cache[cik] = investor_id
        return investor_id

    def load_security(self, name: str, cusip: str = None, ticker: str = None) -> str:
        """Load or get security ID."""
        # Create a unique key for the cache
        cache_key = (name, cusip, ticker)
        if cache_key in self.security_cache:
            return self.security_cache[cache_key]

        # First try to find an existing security by CUSIP or ticker
        if cusip:
            self.cur.execute("SELECT security_id FROM securities WHERE cusip = %s LIMIT 1", (cusip,))
            result = self.cur.fetchone()
            if result:
                return result[0]

        if ticker:
            self.cur.execute("SELECT security_id FROM securities WHERE ticker = %s LIMIT 1", (ticker,))
            result = self.cur.fetchone()
            if result:
                return result[0]

        # If not found, insert new security
        query = """
            INSERT INTO securities (name, ticker, cusip)
            VALUES (%s, %s, %s)
            RETURNING security_id
            """

        self.cur.execute(query, (name, ticker, cusip))
        security_id = self.cur.fetchone()[0]
        self.security_cache[cache_key] = security_id
        return security_id

    def process_filing(self, meta_file: Path):
        """Process a single 13F filing."""
        try:
            with open(meta_file, "r") as f:
                meta = json.load(f)

            # Get or create investor
            investor_id = self.load_investor(meta["investor"], meta["cik"])

            # Commit investor insert/update early so later row-level errors can't invalidate cached IDs
            self.conn.commit()

            # Insert filing
            self.cur.execute(
                """
                INSERT INTO filings (
                    investor_id, filing_date, accession_number, filing_url
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (investor_id, filing_date) DO UPDATE
                SET
                    accession_number = EXCLUDED.accession_number,
                    filing_url = EXCLUDED.filing_url
                RETURNING filing_id
                """,
                (investor_id, meta["filing_date"], meta["accession_number"], meta["filing_url"]),
            )
            filing_result = self.cur.fetchone()
            if not filing_result:
                logger.warning(f"Failed to insert filing for {meta_file}")
                return

            filing_id = filing_result[0]
            logger.info(
                "Processing filing %s for %s on %s",
                filing_id,
                meta["investor"],
                meta["filing_date"],
            )

            # Commit filing insert/update early so holdings processing can't rollback the filing row
            self.conn.commit()

            # Process holdings
            holdings_file = meta_file.parent / f"{meta_file.stem.replace('_meta', '_holdings')}.csv"
            if not holdings_file.exists():
                logger.warning(f"No holdings file found for {meta_file}")
                return

            self.process_holdings(filing_id, holdings_file)

            self.conn.commit()
            logger.info(f"Successfully processed {meta_file}")

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error processing {meta_file}: {e}", exc_info=True)
            raise

    def process_holdings(self, filing_id: str, holdings_file: Path):
        """Process holdings from a CSV file."""
        try:
            # Read all rows first (2-pass) so we can compute true filing total value.
            with open(holdings_file, "r") as f:
                first_line = f.readline().strip()
                f.seek(0)

                if not first_line:
                    logger.warning(f"Empty file: {holdings_file}")
                    return

                try:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                except Exception as e:
                    logger.warning(f"Error parsing CSV with default settings: {e}")
                    f.seek(0)
                    reader = csv.DictReader(f, delimiter="\t")
                    rows = list(reader)

            if not rows:
                logger.warning(f"No rows found in holdings file: {holdings_file}")
                return

            parsed_rows = []
            total_value = Decimal("0")

            for row in rows:
                name = (row.get("nameOfIssuer") or row.get("Name of Issuer") or "").strip()
                cusip = (row.get("cusip") or row.get("CUSIP") or "").strip()
                ticker = (row.get("ticker") or row.get("Ticker") or "").strip()

                if not name:
                    continue

                shares_str = row.get("shares") or row.get("Shares") or "0"
                value_str = row.get("value") or row.get("Value") or "0"

                try:
                    cleaned_shares = "".join(c for c in str(shares_str) if c.isdigit() or c == ".")
                    shares = int(float(cleaned_shares)) if cleaned_shares else 0
                except Exception:
                    shares = 0

                try:
                    cleaned = "".join(c for c in str(value_str) if c.isdigit() or c == ".")
                    value = Decimal(cleaned) if cleaned else Decimal("0")
                except (InvalidOperation, TypeError):
                    value = Decimal("0")

                if value < 0:
                    continue

                total_value += value

                parsed_rows.append(
                    {
                        "name": name,
                        "cusip": cusip,
                        "ticker": ticker,
                        "shares": shares,
                        "value": value,
                    }
                )

            if not parsed_rows:
                logger.warning(f"No valid holdings rows found in {holdings_file}")
                return

            if total_value <= 0:
                total_value = Decimal("1")

            # Process each parsed row with SAVEPOINT so one bad row doesn't rollback the filing.
            for idx, row in enumerate(parsed_rows, start=1):
                try:
                    if idx <= 2:
                        logger.info(f"Sample parsed row {idx}: {row}")

                    name = row["name"]
                    cusip = row["cusip"]
                    ticker = row["ticker"]
                    shares = row["shares"]
                    value = row["value"]

                    weight = (value / total_value) if total_value > 0 else Decimal("0")

                    # SAVEPOINT for row-level error isolation
                    sp_name = f"sp_h_{idx}"
                    self.cur.execute(f"SAVEPOINT {sp_name}")

                    # Get or create security
                    security_id = self.load_security(
                        name=name,
                        cusip=cusip if cusip and cusip.lower() not in ("none", "") else None,
                        ticker=ticker if ticker and ticker.lower() not in ("none", "") else None,
                    )

                    # Insert or update holding
                    self.cur.execute(
                        """
                        INSERT INTO holdings (
                            filing_id, security_id, shares, value_usd, weight_in_portfolio
                        ) VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (filing_id, security_id) DO UPDATE
                        SET
                            shares = EXCLUDED.shares,
                            value_usd = EXCLUDED.value_usd,
                            weight_in_portfolio = EXCLUDED.weight_in_portfolio
                        RETURNING holding_id
                    """,
                        (filing_id, security_id, shares, value, weight),
                    )

                    self.cur.execute(f"RELEASE SAVEPOINT {sp_name}")

                except Exception as e:
                    # Roll back only this row, keep the filing intact
                    try:
                        self.cur.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                        self.cur.execute(f"RELEASE SAVEPOINT {sp_name}")
                    except Exception:
                        pass

                    logger.error(f"Error processing holding row {idx}: {e}", exc_info=True)
                    continue

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error processing {holdings_file}: {e}", exc_info=True)
            raise

    def process_directory(self, directory: str):
        """Process all 13F filings in a directory."""
        try:
            self.connect()

            # Process all meta files
            data_dir = Path(directory)
            meta_files = sorted(data_dir.glob("*_meta.json"))

            if not meta_files:
                logger.warning(f"No meta files found in {directory}")
                return

            logger.info(f"Found {len(meta_files)} meta files to process")

            for meta_file in meta_files:
                try:
                    self.process_filing(meta_file)
                except Exception as e:
                    logger.error(f"Error processing {meta_file}: {e}", exc_info=True)
                    continue

        except Exception as e:
            logger.error(f"Error processing directory {directory}: {e}", exc_info=True)
            raise
        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(description="Load 13F filings into database.")
    parser.add_argument(
        "--dir",
        type=str,
        default="data/13f_holdings",
        help="Directory containing 13F filings (default: data/13f_holdings)",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/investorbot"),
        help="Database connection URL (default: postgresql://postgres@localhost:5432/investorbot)",
    )

    args = parser.parse_args()

    loader = SEC13FLoader(db_url=args.db_url)
    loader.process_directory(args.dir)


if __name__ == "__main__":
    main()
