#!/usr/bin/env python3
"""
Enhanced Daily Workflow - Complete system with all enhancements.

Includes:
- Real-time price data for technical indicators
- SEC Form 4 parsing for insider trading
- Ticker mapping (CUSIP to ticker)
- Performance tracking
"""

import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from alpaca.trading.client import TradingClient

from services.approval.trade_approval import TradeApprovalManager
from services.data.price_fetcher import PriceDataFetcher
from services.data.ticker_mapper import TickerMapper
from services.monitoring.email_notifier import EmailConfig, EmailNotifier
from services.sec.form4_parser import RealInsiderSignalGenerator
from services.strategy.complete_signal_engine import CompleteSignalEngine, CompleteSignalWeights
from services.technical.indicators import TechnicalSignalGenerator
from services.tracking.performance_tracker import PerformanceTracker
from utils.logging_config import setup_logger

logger = setup_logger(__name__)


def main():
    print("=" * 80)
    print("ENHANCED DAILY INVESTMENT WORKFLOW")
    print("All Future Enhancements Enabled")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Initialize all services
    print("Initializing enhanced services...")

    alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    approval_email = os.getenv("ALERT_EMAIL", "schickerur2020@gmail.com")

    # Price data fetcher
    price_fetcher = PriceDataFetcher(alpha_vantage_key=alpha_vantage_key)
    print("  ✓ Price data fetcher initialized")

    # Ticker mapper
    ticker_mapper = TickerMapper()
    print(f"  ✓ Ticker mapper initialized ({len(ticker_mapper.cusip_to_ticker_cache)} mappings cached)")

    # Real insider signal generator
    insider_generator = RealInsiderSignalGenerator()
    print("  ✓ Insider trading analyzer initialized")

    # Technical signal generator
    technical_generator = TechnicalSignalGenerator()
    print("  ✓ Technical indicators initialized")

    # Performance tracker
    performance_tracker = PerformanceTracker()
    print(f"  ✓ Performance tracker initialized ({len(performance_tracker.snapshots)} snapshots)")

    print()

    # Get Alpaca account info
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    paper = os.getenv("ALPACA_PAPER", "True").lower() == "true"

    client = TradingClient(api_key, secret_key, paper=paper)
    account = client.get_account()
    buying_power = Decimal(str(account.buying_power))

    print(f"Alpaca Account:")
    print(f"  Mode: {'Paper Trading' if paper else 'Live Trading'}")
    print(f"  Buying Power: ${buying_power:,.2f}")
    print()

    # Check minimum cash
    min_cash = Decimal("1000")
    if buying_power < min_cash:
        print(f"⚠️  Buying power ${buying_power:,.2f} below minimum ${min_cash:,.2f}")
        print("Waiting for more funds...")
        return

    # Initialize complete signal engine
    print("Running complete multi-signal analysis...")
    print("  Signal Sources:")
    print("    - 13F Filings (40%)")
    print("    - News Sentiment (20%)")
    print("    - Insider Trading (20%) - Real SEC Form 4 data")
    print("    - Technical Indicators (20%) - Real price data")
    print()

    engine = CompleteSignalEngine(
        signal_weights=CompleteSignalWeights(
            conviction_13f=0.40, news_sentiment=0.20, insider_trading=0.20, technical=0.20
        ),
        alpha_vantage_key=alpha_vantage_key,
    )

    try:
        # Get recommendations
        print("Analyzing market (this may take 1-2 minutes)...")
        recommendations = engine.get_recommendations(top_n=10)

        print(f"✓ Generated {len(recommendations)} recommendations")
        print()

        # Normalize symbols (convert CUSIPs to tickers)
        print("Normalizing symbols...")
        symbols = [rec.symbol for rec in recommendations]
        normalized = ticker_mapper.normalize_symbols(symbols)
        print(f"  ✓ Normalized {len(symbols)} symbols to {len(normalized)} tickers")
        print()

        # Display recommendations
        print("TOP 10 RECOMMENDATIONS:")
        print("-" * 80)
        print(f"{'Rank':<6} {'Symbol':<10} {'Score':<10} {'Recommendation':<15} {'Confidence':<12}")
        print("-" * 80)

        for i, rec in enumerate(recommendations, 1):
            # Try to get ticker if it's a CUSIP
            display_symbol = ticker_mapper.cusip_to_ticker(rec.symbol) or rec.symbol
            print(f"{i:<6} {display_symbol:<10} {rec.final_score:.4f}    {rec.recommendation:<15} {rec.confidence:.1%}")

        print()

        # Show detailed analysis
        print("DETAILED ANALYSIS (Top 3):")
        print("-" * 80)

        for rec in recommendations[:3]:
            display_symbol = ticker_mapper.cusip_to_ticker(rec.symbol) or rec.symbol
            print(f"\n{display_symbol}:")
            print(f"  Final Score:      {rec.final_score:.4f}")
            print(f"  Recommendation:   {rec.recommendation.upper()} (confidence: {rec.confidence:.1%})")
            print(f"  Signal Breakdown:")
            print(f"    13F Conviction:   {rec.conviction_score:.4f} (40% weight)")
            print(f"    News Sentiment:   {rec.sentiment_score:.4f} (20% weight)")
            print(f"    Insider Trading:  {rec.insider_score:.4f} (20% weight)")
            print(f"    Technical:        {rec.technical_score:.4f} (20% weight)")

        print()
        print("=" * 80)

        # Calculate investment allocation
        cash_buffer_pct = 0.10
        cash_buffer = buying_power * Decimal(str(cash_buffer_pct))
        investable_cash = buying_power - cash_buffer

        print(f"\nInvestment Allocation:")
        print(f"  Available Cash:    ${buying_power:,.2f}")
        print(f"  Cash Buffer (10%): ${cash_buffer:,.2f}")
        print(f"  Investable:        ${investable_cash:,.2f}")
        print()

        # Prepare trades
        trades = []
        for rec in recommendations:
            display_symbol = ticker_mapper.cusip_to_ticker(rec.symbol) or rec.symbol
            allocation = float(investable_cash) * rec.final_score

            # Get real current price
            current_price = price_fetcher.get_current_price(display_symbol)
            if not current_price:
                current_price = 100.0  # Fallback

            shares = allocation / current_price

            trades.append(
                {
                    "symbol": display_symbol,
                    "quantity": shares,
                    "estimated_price": current_price,
                    "estimated_value": allocation,
                    "allocation_pct": rec.final_score * 100,
                }
            )

        total_investment = sum(t["estimated_value"] for t in trades)

        print("PROPOSED TRADES:")
        print("-" * 80)
        for trade in trades:
            print(
                f"  {trade['symbol']:<10} {trade['quantity']:>8.2f} shares @ ${trade['estimated_price']:>8.2f} = ${trade['estimated_value']:>10,.2f} ({trade['allocation_pct']:>5.1f}%)"
            )
        print("-" * 80)
        print(f"  {'TOTAL':<10} {'':<8} {'':<8} {'':<3} ${total_investment:>10,.2f}")
        print()

        # Record performance snapshot
        positions = client.get_all_positions()
        positions_dict = {
            p.symbol: {
                "quantity": float(p.qty),
                "value": float(p.market_value),
                "price": float(p.current_price),
            }
            for p in positions
        }

        positions_value = Decimal(str(sum(p["value"] for p in positions_dict.values())))
        performance_tracker.record_snapshot(
            total_value=buying_power, cash=buying_power - positions_value, positions=positions_dict
        )

        # Get performance summary
        perf_summary = performance_tracker.get_performance_summary()

        print("PERFORMANCE SUMMARY:")
        print("-" * 80)
        print(f"  Current Value:     ${perf_summary['current_value']:,.2f}")
        print(f"  Total Trades:      {perf_summary['total_trades']}")

        if perf_summary.get("overall"):
            overall = perf_summary["overall"]
            print(f"  Total Return:      {overall['total_return_pct']:.2f}%")
            print(f"  Sharpe Ratio:      {overall['sharpe_ratio']:.2f}")
            print(f"  Max Drawdown:      {overall['max_drawdown']:.2f}%")
            print(f"  Win Rate:          {overall['win_rate']:.1f}%")

        print()

        # Create approval request
        print("Creating approval request...")
        approval_manager = TradeApprovalManager()

        request = approval_manager.create_approval_request(
            trades=trades,
            total_investment=total_investment,
            available_cash=float(buying_power),
            cash_buffer=float(cash_buffer),
            expiry_hours=24,
        )

        print(f"✓ Approval request created: {request.request_id}")
        print()

        # Send approval email
        print(f"Sending approval email to {approval_email}...")

        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")

        if not all([smtp_server, smtp_username, smtp_password]):
            print("✗ Email not configured")
            return

        email_config = EmailConfig(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            from_email=smtp_username,
        )

        notifier = EmailNotifier(email_config)

        # Build email
        trade_summary = "\n".join(
            [
                f"  • {t['symbol']}: {t['quantity']:.2f} shares @ ${t['estimated_price']:.2f} = ${t['estimated_value']:,.2f}"
                for t in trades
            ]
        )

        perf_text = ""
        if perf_summary.get("overall"):
            overall = perf_summary["overall"]
            perf_text = f"""
PERFORMANCE TO DATE:
-------------------
Total Return: {overall['total_return_pct']:.2f}%
Sharpe Ratio: {overall['sharpe_ratio']:.2f}
Win Rate: {overall['win_rate']:.1f}%
"""

        approve_url = f"http://localhost:8000/api/v1/approve/{request.request_id}/approve"

        message = f"""
Enhanced Multi-Signal Analysis Complete

Your investment bot analyzed the market using ALL available signals:
- 13F Filings (40%)
- News Sentiment (20%)
- Real Insider Trading Data (20%)
- Real-Time Technical Indicators (20%)

SUMMARY:
--------
Total Investment: ${total_investment:,.2f}
Available Cash: ${buying_power:,.2f}
Number of Trades: {len(trades)}

TOP RECOMMENDATIONS:
-------------------
{chr(10).join([f'{i}. {ticker_mapper.cusip_to_ticker(rec.symbol) or rec.symbol} - {rec.recommendation.upper()} (confidence: {rec.confidence:.0%})' for i, rec in enumerate(recommendations[:5], 1)])}

PROPOSED TRADES:
---------------
{trade_summary}
{perf_text}
APPROVAL:
---------
To approve: {approve_url}

Request ID: {request.request_id}

---
Enhanced System with Real-Time Data
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        success = notifier.send_alert(
            to_emails=[approval_email],
            subject=f"Enhanced Trade Approval: ${total_investment:,.2f}",
            message=message,
            level="INFO",
        )

        if success:
            print(f"✓ Approval email sent")
        else:
            print("✗ Failed to send email")

        print()
        print("=" * 80)
        print("ENHANCED WORKFLOW COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
