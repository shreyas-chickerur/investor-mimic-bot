#!/usr/bin/env python3
"""
Shared symbol → sector-ETF mapping for the full trading universe.

Single source of truth consumed by Factor Momentum (sector relative-strength
factor) and Sector Rotation (constituent selection). Before 2026-06 each
strategy carried its own partial hardcoded map (~24 and ~34 names), so the
128-symbol universe expansion was invisible to both — and Factor Momentum
mapped unmapped names to SPY, making its sector-RS factor spurious for them.

Sectors follow GICS via the SPDR sector ETFs. Note two deliberate
corrections from the old maps: GOOGL/META/NFLX/DIS are XLC (Communication
Services, post-2018 GICS), and AMZN/TSLA are XLY while WMT/COST are XLP.
"""
from __future__ import annotations

SYMBOL_SECTOR: dict[str, str] = {
    # --- Information Technology (XLK) ---
    **dict.fromkeys(
        [
            "AAPL",
            "MSFT",
            "NVDA",
            "ADBE",
            "AVGO",
            "CRM",
            "AMD",
            "ACN",
            "ORCL",
            "CSCO",
            "INTC",
            "QCOM",
            "TXN",
            "IBM",
            "NOW",
            "INTU",
            "AMAT",
            "MU",
            "LRCX",
            "KLAC",
            "PANW",
            "ANET",
            "ADI",
        ],
        "XLK",
    ),
    # --- Communication Services (XLC) ---
    **dict.fromkeys(["GOOGL", "META", "NFLX", "DIS", "VZ", "T", "TMUS", "CMCSA"], "XLC"),
    # --- Consumer Discretionary (XLY) ---
    **dict.fromkeys(
        [
            "AMZN",
            "TSLA",
            "MCD",
            "NKE",
            "HD",
            "SBUX",
            "TGT",
            "LOW",
            "TJX",
            "BKNG",
            "CMG",
            "ORLY",
            "ROST",
            "GM",
            "UBER",
        ],
        "XLY",
    ),
    # --- Consumer Staples (XLP) ---
    **dict.fromkeys(
        ["COST", "KO", "PEP", "PG", "WMT", "CL", "KMB", "MDLZ", "MO", "PM", "GIS"],
        "XLP",
    ),
    # --- Health Care (XLV) ---
    **dict.fromkeys(
        [
            "JNJ",
            "ABBV",
            "MRK",
            "TMO",
            "DHR",
            "ABT",
            "UNH",
            "LLY",
            "PFE",
            "BMY",
            "AMGN",
            "GILD",
            "CVS",
            "CI",
            "ISRG",
            "SYK",
            "BSX",
            "MDT",
            "REGN",
            "VRTX",
            "ZTS",
            "MCK",
            "ELV",
            "HCA",
        ],
        "XLV",
    ),
    # --- Financials (XLF) ---
    **dict.fromkeys(
        [
            "MA",
            "JPM",
            "V",
            "BAC",
            "WFC",
            "GS",
            "MS",
            "C",
            "SCHW",
            "BLK",
            "AXP",
            "SPGI",
            "COF",
            "BRK.B",
        ],
        "XLF",
    ),
    # --- Energy (XLE) ---
    **dict.fromkeys(["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX"], "XLE"),
    # --- Industrials (XLI) ---
    **dict.fromkeys(
        [
            "CAT",
            "DE",
            "BA",
            "GE",
            "HON",
            "UNP",
            "UPS",
            "FDX",
            "LMT",
            "RTX",
            "ETN",
            "EMR",
            "CSX",
            "WM",
        ],
        "XLI",
    ),
    # --- Materials (XLB) ---
    **dict.fromkeys(["LIN", "APD", "SHW", "FCX"], "XLB"),
    # --- Utilities (XLU) ---
    **dict.fromkeys(["NEE", "DUK", "SO"], "XLU"),
    # --- Real Estate (XLRE) ---
    **dict.fromkeys(["PLD", "AMT"], "XLRE"),
}


def sector_of(symbol: str) -> str | None:
    """Sector ETF for a symbol, or None if unmapped (never silently SPY)."""
    return SYMBOL_SECTOR.get(symbol.upper())


def constituents_by_sector() -> dict[str, list[str]]:
    """Inverted map: sector ETF → sorted list of constituent symbols."""
    out: dict[str, list[str]] = {}
    for sym, etf in SYMBOL_SECTOR.items():
        out.setdefault(etf, []).append(sym)
    return {etf: sorted(syms) for etf, syms in out.items()}
