"""
Configuration for institutional investors to track.
"""

from typing import List, TypedDict


class InvestorConfig(TypedDict):
    name: str
    cik: str  # SEC Central Index Key
    aliases: List[str]  # Alternative names the investor might use


# List of institutional investors to track
INVESTORS: List[InvestorConfig] = [
    {"name": "Berkshire Hathaway", "cik": "0001067983", "aliases": ["BERKSHIRE HATHAWAY INC"]},
    {
        "name": "Pershing Square Capital Management",
        "cik": "0001336528",
        "aliases": ["PERSHING SQUARE CAPITAL MANAGEMENT, L.P."],
    },
    {
        "name": "Bridgewater Associates",
        "cik": "0001350694",
        "aliases": ["BRIDGEWATER ASSOCIATES, LP"],
    },
    {
        "name": "Tiger Global Management",
        "cik": "0001167483",
        "aliases": ["TIGER GLOBAL MANAGEMENT, LLC"],
    },
    {
        "name": "Renaissance Technologies",
        "cik": "0001037389",
        "aliases": ["RENAISSANCE TECHNOLOGIES LLC"],
    },
    {"name": "D1 Capital Partners", "cik": "0001732419", "aliases": ["D1 CAPITAL PARTNERS L.P."]},
    {
        "name": "Viking Global Investors",
        "cik": "0001029159",
        "aliases": ["VIKING GLOBAL INVESTORS LP"],
    },
]

# Mapping of CIK to investor name for easy lookup
INVESTOR_MAP = {investor["cik"]: investor["name"] for investor in INVESTORS}
