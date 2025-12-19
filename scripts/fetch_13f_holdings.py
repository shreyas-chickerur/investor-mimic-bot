"""
Script to fetch 13F holdings for configured institutional investors.
"""

# Standard library imports
import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Third-party imports
import pandas as pd
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from services.sec.client import SECClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("sec_filings.log")],
)
logger = logging.getLogger(__name__)

# Output directories
DEFAULT_OUTPUT_DIR = Path("data/13f_holdings")
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def main(max_filings_per_investor: int, output_dir: Path):
    """Fetch and process 13F filings for all configured investors."""
    logger.info("Starting 13F holdings fetch")

    # Initialize the SEC client
    async with SECClient() as client:
        # Get holdings for all investors
        holdings = await client.get_all_investor_holdings(max_filings_per_investor=max_filings_per_investor)

        # Process and save results
        for investor_name, data in holdings.items():
            try:
                # If we fetched multiple filings, normalize to list
                filings = data if isinstance(data, list) else [data]

                # Create a clean filename
                safe_name = "".join(c if c.isalnum() else "_" for c in investor_name)

                for filing in filings:
                    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
                    acc = str(filing.get("accession_number") or "").replace("/", "-").replace(" ", "")
                    acc_suffix = f"_{acc}" if acc else ""

                    meta = {
                        "investor": investor_name,
                        "cik": filing["cik"],
                        "filing_date": filing["filing_date"],
                        "accession_number": filing["accession_number"],
                        "filing_url": filing["filing_url"],
                        "processed_at": datetime.utcnow().isoformat(),
                    }

                    meta_file = output_dir / f"{safe_name}_{timestamp}{acc_suffix}_meta.json"
                    with open(meta_file, "w") as f:
                        json.dump(meta, f, indent=2)

                    holdings_df = filing["holdings"]

                    if "votingAuthority" in holdings_df.columns:
                        va_df = pd.json_normalize(holdings_df["votingAuthority"])
                        va_df.columns = [f"va_{col}" for col in va_df.columns]
                        holdings_df = pd.concat([holdings_df.drop(["votingAuthority"], axis=1), va_df], axis=1)

                    csv_file = output_dir / f"{safe_name}_{timestamp}{acc_suffix}_holdings.csv"
                    holdings_df.to_csv(csv_file, index=False)

                    logger.info(f"Saved {len(holdings_df)} holdings for {investor_name} to {csv_file}")

            except Exception as e:
                logger.error(f"Error processing {investor_name}: {str(e)}", exc_info=True)
                continue

    logger.info("Completed 13F holdings fetch")


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()

    parser = argparse.ArgumentParser(description="Fetch SEC 13F holdings for configured investors")
    parser.add_argument(
        "--max-filings-per-investor",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    asyncio.run(main(max_filings_per_investor=args.max_filings_per_investor, output_dir=out_dir))
