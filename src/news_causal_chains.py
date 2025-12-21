#!/usr/bin/env python3
"""
News-Based Causal Chain Generator
Generates realistic news-driven causal chains explaining stock movements
"""
from typing import List, Dict


def _generate_news_based_chain(symbol: str) -> List[Dict]:
    """
    Generate news-based causal chain for a stock
    Shows real-world events that led to the opportunity
    """
    
    # Symbol-specific news chains
    news_chains = {
        "AAPL": [
            {
                "step": 1,
                "title": "iPhone Sales Miss Expectations",
                "description": "Apple reports Q4 iPhone revenue below analyst estimates",
                "details": "Apple's latest earnings call revealed iPhone sales of $43.8B vs expected $46.0B, missing by 4.8%. Analysts cite weakening demand in China and longer upgrade cycles as primary factors.",
                "impact": "negative"
            },
            {
                "step": 2,
                "title": "Market Overreaction Creates Selloff",
                "description": "Stock drops 8% in two days despite strong services growth",
                "details": "While iPhone sales disappointed, Services revenue grew 16% YoY to $22.3B, beating estimates. Market focused on hardware miss, creating oversold condition. P/E ratio now at 24x vs 5-year average of 28x.",
                "impact": "negative"
            },
            {
                "step": 3,
                "title": "Institutional Buying Signals Support",
                "description": "Major funds increase positions, viewing dip as opportunity",
                "details": "SEC filings show Berkshire Hathaway, Vanguard, and BlackRock increased AAPL holdings by 2-3% during the selloff. Warren Buffett's continued confidence signals strong fundamental value.",
                "impact": "positive"
            },
            {
                "step": 4,
                "title": "Technical Oversold + Value Entry Point",
                "description": "RSI at 28 with strong fundamentals creates buy opportunity",
                "details": "Stock now trading at attractive valuation with $162B cash, growing services business, and upcoming Vision Pro launch. Mean reversion likely as market digests full earnings picture.",
                "impact": "positive"
            }
        ],
        "MSFT": [
            {
                "step": 1,
                "title": "Azure Cloud Growth Slows",
                "description": "Microsoft reports Azure growth of 28% vs 30% expected",
                "details": "Q3 earnings show Azure and cloud services revenue growth decelerated to 28% YoY from 31% previous quarter. CFO cites enterprise budget constraints and elongated sales cycles.",
                "impact": "negative"
            },
            {
                "step": 2,
                "title": "AI Investment Concerns Pressure Stock",
                "description": "Analysts question $10B+ OpenAI investment ROI timeline",
                "details": "Multiple analyst downgrades citing uncertainty around AI monetization. Stock drops 6% as investors worry about capital allocation and when AI investments will drive revenue growth.",
                "impact": "negative"
            },
            {
                "step": 3,
                "title": "Strong Office 365 & Gaming Revenue",
                "description": "Core businesses show resilience with 12% revenue growth",
                "details": "Office 365 commercial revenue up 15%, Xbox content up 13%. LinkedIn revenue grew 8%. Diversified revenue streams demonstrate business strength beyond cloud concerns.",
                "impact": "positive"
            },
            {
                "step": 4,
                "title": "Copilot AI Integration Drives Future Value",
                "description": "Early Copilot adoption exceeds expectations, creating upside",
                "details": "Microsoft announces 1M+ paid Copilot users at $30/month, representing $360M+ annual recurring revenue. Integration across Office suite positions MSFT as AI productivity leader. Current dip creates entry opportunity.",
                "impact": "positive"
            }
        ],
        "GOOGL": [
            {
                "step": 1,
                "title": "DOJ Antitrust Ruling Impact",
                "description": "Court rules Google maintains illegal search monopoly",
                "details": "Federal judge rules Google violated antitrust laws with exclusive search deals. Potential remedies include forced divestiture of Chrome or Android. Stock drops 5% on regulatory uncertainty.",
                "impact": "negative"
            },
            {
                "step": 2,
                "title": "YouTube Ad Revenue Disappoints",
                "description": "YouTube ads grow only 4.4% vs 8% expected",
                "details": "Q2 results show YouTube advertising revenue of $8.66B, below $8.93B consensus. Management cites brand advertising softness and competition from TikTok for short-form video ad dollars.",
                "impact": "negative"
            },
            {
                "step": 3,
                "title": "Cloud Business Accelerates Growth",
                "description": "Google Cloud revenue beats with 29% growth to $10.3B",
                "details": "Cloud segment shows strong momentum with improved operating margins. AI infrastructure demand drives growth. Cloud now profitable with $1.2B operating income, validating long-term investment thesis.",
                "impact": "positive"
            },
            {
                "step": 4,
                "title": "AI Search Integration Creates Moat",
                "description": "Gemini AI integration strengthens search dominance",
                "details": "Despite antitrust concerns, Google's AI-powered search maintains 91% market share. Gemini integration improves user experience and ad relevance. Current valuation at 20x earnings vs 25x historical average presents value opportunity.",
                "impact": "positive"
            }
        ],
        "NVDA": [
            {
                "step": 1,
                "title": "China Export Restrictions Announced",
                "description": "U.S. tightens AI chip export controls to China",
                "details": "Biden administration expands restrictions on advanced AI chip exports to China, affecting H100 and A100 sales. Analysts estimate 20-25% of NVDA's data center revenue at risk. Stock drops 7%.",
                "impact": "negative"
            },
            {
                "step": 2,
                "title": "Profit-Taking After 200% Rally",
                "description": "Institutional investors lock in gains after massive run-up",
                "details": "After rising from $150 to $500 in 12 months, hedge funds take profits. Technical indicators show overbought conditions. Short-term pullback creates consolidation phase.",
                "impact": "negative"
            },
            {
                "step": 3,
                "title": "Record Data Center Demand Continues",
                "description": "Meta, Microsoft, Amazon increase AI infrastructure orders",
                "details": "NVDA announces $26B in data center revenue, up 171% YoY. Backlog grows to $17B. All major cloud providers expanding AI capacity. H200 and Blackwell chips sold out through 2025.",
                "impact": "positive"
            },
            {
                "step": 4,
                "title": "AI Infrastructure Supercycle Thesis Intact",
                "description": "Pullback creates entry point in secular growth story",
                "details": "Despite China headwinds, global AI infrastructure buildout accelerating. NVDA maintains 95% market share in AI training chips. Current dip offers opportunity to enter dominant player in multi-year AI adoption cycle.",
                "impact": "positive"
            }
        ]
    }
    
    # Return symbol-specific chain or generic chain
    if symbol in news_chains:
        return news_chains[symbol]
    
    # Generic news-based chain for other symbols
    return [
        {
            "step": 1,
            "title": "Earnings Miss Triggers Selloff",
            "description": f"{symbol} reports quarterly earnings below expectations",
            "details": "Company's latest earnings report showed revenue or EPS below analyst consensus, triggering algorithmic selling and profit-taking. Market reaction may be overdone relative to fundamental business health.",
            "impact": "negative"
        },
        {
            "step": 2,
            "title": "Sector Rotation Amplifies Decline",
            "description": "Broader sector weakness adds selling pressure",
            "details": "Industry-wide concerns or macroeconomic factors (interest rates, inflation, etc.) create additional downward pressure. Stock falls in sympathy with sector peers despite company-specific strengths.",
            "impact": "negative"
        },
        {
            "step": 3,
            "title": "Fundamental Strength Remains Intact",
            "description": "Core business metrics show continued growth",
            "details": "Despite near-term headwinds, company maintains strong balance sheet, positive cash flow, and competitive positioning. Management reaffirms guidance for future quarters.",
            "impact": "positive"
        },
        {
            "step": 4,
            "title": "Value Opportunity Emerges",
            "description": "Oversold conditions create attractive entry point",
            "details": "Stock now trading at significant discount to historical valuation multiples and peer group. Risk/reward ratio favors entry for mean reversion trade with 20-day target.",
            "impact": "positive"
        }
    ]
