#!/usr/bin/env python3
"""
Daily Execution Artifact Writer

Generates machine-readable JSON and human-readable markdown artifacts
for each trading day containing complete system state and execution details.

Critical Component for operational validation and audit trail.
"""
import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class DailyArtifactWriter:
    """
    Writes daily execution artifacts
    
    Artifacts contain:
    - VIX + regime
    - Raw signals per strategy
    - Rejected signals with reasons
    - Orders placed/filled/rejected
    - Heat, P&L, drawdown, circuit breaker state
    - Positions + exposure
    - System health (runtime, data freshness, errors)
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        """
        Initialize artifact writer
        
        Args:
            artifacts_dir: Directory to store artifacts
        """
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.artifacts_dir / "json").mkdir(exist_ok=True)
        (self.artifacts_dir / "markdown").mkdir(exist_ok=True)
    
    def write_daily_artifact(self, date: str, data: Dict) -> Tuple[str, str]:
        """
        Write daily artifact in both JSON and markdown formats
        
        Args:
            date: Trading date (YYYY-MM-DD)
            data: Complete daily data dictionary
            
        Returns:
            (json_path, markdown_path)
        """
        logger.info(f"Writing daily artifact for {date}")
        
        # Validate required fields
        self._validate_data(data)
        
        # Add metadata
        artifact = {
            'date': date,
            'generated_at': datetime.now().isoformat(),
            'version': '1.0',
            **data
        }
        
        # Write JSON
        json_path = self._write_json(date, artifact)
        
        # Write Markdown
        markdown_path = self._write_markdown(date, artifact)
        
        logger.info(f"✅ Artifact written: {json_path}")
        return json_path, markdown_path
    
    def _validate_data(self, data: Dict):
        """Validate that all required fields are present"""
        required_fields = [
            'regime', 'signals', 'trades', 'risk', 
            'positions', 'system_health'
        ]
        
        missing = [field for field in required_fields if field not in data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")
    
    def _write_json(self, date: str, artifact: Dict) -> str:
        """Write JSON artifact"""
        filepath = self.artifacts_dir / "json" / f"{date}.json"
        
        with open(filepath, 'w') as f:
            json.dump(artifact, f, indent=2, default=str)
        
        return str(filepath)
    
    def _write_markdown(self, date: str, artifact: Dict) -> str:
        """Write human-readable markdown artifact"""
        filepath = self.artifacts_dir / "markdown" / f"{date}.md"
        
        content = self._generate_markdown(artifact)
        
        with open(filepath, 'w') as f:
            f.write(content)
        
        return str(filepath)
    
    def _generate_markdown(self, artifact: Dict) -> str:
        """Generate markdown content from artifact data"""
        date = artifact['date']
        regime = artifact.get('regime', {})
        signals = artifact.get('signals', {})
        trades = artifact.get('trades', {})
        risk = artifact.get('risk', {})
        positions = artifact.get('positions', {})
        health = artifact.get('system_health', {})
        
        md = f"""# Daily Trading Artifact - {date}

**Generated:** {artifact.get('generated_at', 'N/A')}

---

## Market Regime

- **VIX Level:** {regime.get('vix', 'N/A')}
- **Classification:** {regime.get('classification', 'N/A')}
- **Volatility State:** {regime.get('volatility_state', 'N/A')}

---

## Signals

### Raw Signals Generated
"""
        
        # Raw signals by strategy
        raw_signals = signals.get('raw', {})
        if raw_signals:
            for strategy, sigs in raw_signals.items():
                md += f"\n**{strategy}:** {len(sigs)} signals\n"
                for sig in sigs:
                    md += f"- {sig.get('action', 'N/A')} {sig.get('symbol', 'N/A')} @ ${sig.get('price', 0):.2f}\n"
        else:
            md += "\n*No signals generated*\n"
        
        # Rejected signals
        md += "\n### Rejected Signals\n"
        rejected = signals.get('rejected', [])
        if rejected:
            for rej in rejected:
                md += f"- {rej.get('symbol', 'N/A')}: {rej.get('reason', 'N/A')}\n"
        else:
            md += "\n*No rejections*\n"
        
        # Executed signals
        md += "\n### Executed Signals\n"
        executed = signals.get('executed', [])
        if executed:
            for ex in executed:
                md += f"- {ex.get('action', 'N/A')} {ex.get('symbol', 'N/A')} @ ${ex.get('price', 0):.2f}\n"
        else:
            md += "\n*No executions*\n"
        
        # Trades
        md += "\n---\n\n## Trades\n\n"
        placed = trades.get('placed', [])
        filled = trades.get('filled', [])
        rejected_trades = trades.get('rejected', [])
        
        md += f"- **Orders Placed:** {len(placed)}\n"
        md += f"- **Orders Filled:** {len(filled)}\n"
        md += f"- **Orders Rejected:** {len(rejected_trades)}\n\n"
        
        if filled:
            md += "### Filled Orders\n"
            for trade in filled:
                md += f"- {trade.get('side', 'N/A')} {trade.get('qty', 0)} {trade.get('symbol', 'N/A')} @ ${trade.get('price', 0):.2f}\n"
        
        if rejected_trades:
            md += "\n### Rejected Orders\n"
            for trade in rejected_trades:
                md += f"- {trade.get('symbol', 'N/A')}: {trade.get('reason', 'N/A')}\n"
        
        # Risk
        md += "\n---\n\n## Risk Metrics\n\n"
        md += f"- **Portfolio Heat:** {risk.get('portfolio_heat', 0):.2f}%\n"
        md += f"- **Daily P&L:** ${risk.get('daily_pnl', 0):,.2f}\n"
        md += f"- **Cumulative P&L:** ${risk.get('cumulative_pnl', 0):,.2f}\n"
        md += f"- **Drawdown:** {risk.get('drawdown', 0):.2f}%\n"
        md += f"- **Max Drawdown:** {risk.get('max_drawdown', 0):.2f}%\n"
        md += f"- **Circuit Breaker:** {risk.get('circuit_breaker_state', 'INACTIVE')}\n"
        
        # Positions
        md += "\n---\n\n## Positions\n\n"
        open_positions = positions.get('open', [])
        md += f"**Total Positions:** {len(open_positions)}\n\n"
        
        if open_positions:
            md += "| Symbol | Qty | Avg Price | Market Value | Unrealized P&L | Exposure % |\n"
            md += "|--------|-----|-----------|--------------|----------------|------------|\n"
            for pos in open_positions:
                md += f"| {pos.get('symbol', 'N/A')} | {pos.get('qty', 0)} | ${pos.get('avg_price', 0):.2f} | ${pos.get('market_value', 0):,.2f} | ${pos.get('unrealized_pl', 0):,.2f} | {pos.get('exposure_pct', 0):.2f}% |\n"
        else:
            md += "*No open positions*\n"
        
        # System Health
        md += "\n---\n\n## System Health\n\n"
        md += f"- **Runtime:** {health.get('runtime_seconds', 0):.2f}s\n"
        md += f"- **Data Freshness:** {health.get('data_freshness', 'N/A')}\n"
        md += f"- **Errors:** {health.get('error_count', 0)}\n"
        md += f"- **Warnings:** {health.get('warning_count', 0)}\n"
        md += f"- **Reconciliation Status:** {health.get('reconciliation_status', 'N/A')}\n"
        
        if health.get('errors'):
            md += "\n### Errors\n"
            for err in health['errors']:
                md += f"- {err}\n"
        
        if health.get('warnings'):
            md += "\n### Warnings\n"
            for warn in health['warnings']:
                md += f"- {warn}\n"
        
        md += "\n---\n\n*End of Daily Artifact*\n"
        
        return md
    
    def read_artifact(self, date: str) -> Optional[Dict]:
        """
        Read artifact for a specific date
        
        Args:
            date: Trading date (YYYY-MM-DD)
            
        Returns:
            Artifact data or None if not found
        """
        filepath = self.artifacts_dir / "json" / f"{date}.json"
        
        if not filepath.exists():
            logger.warning(f"Artifact not found for {date}")
            return None
        
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def list_artifacts(self) -> List[str]:
        """List all available artifact dates"""
        json_dir = self.artifacts_dir / "json"
        if not json_dir.exists():
            return []
        
        dates = [f.stem for f in json_dir.glob("*.json")]
        return sorted(dates)


# Helper function to create artifact data structure
def create_artifact_data(
    vix: float,
    regime_classification: str,
    raw_signals: Dict[str, List[Dict]],
    rejected_signals: List[Dict],
    executed_signals: List[Dict],
    placed_orders: List[Dict],
    filled_orders: List[Dict],
    rejected_orders: List[Dict],
    portfolio_heat: float,
    daily_pnl: float,
    cumulative_pnl: float,
    drawdown: float,
    max_drawdown: float,
    circuit_breaker_state: str,
    open_positions: List[Dict],
    runtime_seconds: float,
    data_freshness: str,
    errors: List[str] = None,
    warnings: List[str] = None,
    reconciliation_status: str = "UNKNOWN"
) -> Dict:
    """
    Helper to create properly structured artifact data
    
    Returns:
        Dict ready for write_daily_artifact()
    """
    return {
        'regime': {
            'vix': vix,
            'classification': regime_classification,
            'volatility_state': 'HIGH' if vix > 25 else 'NORMAL' if vix > 15 else 'LOW'
        },
        'signals': {
            'raw': raw_signals,
            'rejected': rejected_signals or [],
            'executed': executed_signals or []
        },
        'trades': {
            'placed': placed_orders or [],
            'filled': filled_orders or [],
            'rejected': rejected_orders or []
        },
        'risk': {
            'portfolio_heat': portfolio_heat,
            'daily_pnl': daily_pnl,
            'cumulative_pnl': cumulative_pnl,
            'drawdown': drawdown,
            'max_drawdown': max_drawdown,
            'circuit_breaker_state': circuit_breaker_state
        },
        'positions': {
            'open': open_positions or []
        },
        'system_health': {
            'runtime_seconds': runtime_seconds,
            'data_freshness': data_freshness,
            'error_count': len(errors) if errors else 0,
            'warning_count': len(warnings) if warnings else 0,
            'errors': errors or [],
            'warnings': warnings or [],
            'reconciliation_status': reconciliation_status
        }
    }


if __name__ == "__main__":
    # Test artifact writer
    logging.basicConfig(level=logging.INFO)
    
    writer = DailyArtifactWriter()
    
    # Create sample artifact
    test_data = create_artifact_data(
        vix=18.5,
        regime_classification="NORMAL",
        raw_signals={
            'RSI_Mean_Reversion': [
                {'symbol': 'AAPL', 'action': 'BUY', 'price': 150.00}
            ]
        },
        rejected_signals=[
            {'symbol': 'MSFT', 'reason': 'REJECTED_BY_HEAT'}
        ],
        executed_signals=[
            {'symbol': 'AAPL', 'action': 'BUY', 'price': 150.00}
        ],
        placed_orders=[
            {'symbol': 'AAPL', 'side': 'BUY', 'qty': 10, 'price': 150.00}
        ],
        filled_orders=[
            {'symbol': 'AAPL', 'side': 'BUY', 'qty': 10, 'price': 150.05}
        ],
        rejected_orders=[],
        portfolio_heat=15.5,
        daily_pnl=250.00,
        cumulative_pnl=1500.00,
        drawdown=-2.5,
        max_drawdown=-5.2,
        circuit_breaker_state="INACTIVE",
        open_positions=[
            {
                'symbol': 'AAPL',
                'qty': 10,
                'avg_price': 150.05,
                'market_value': 1505.00,
                'unrealized_pl': 5.00,
                'exposure_pct': 1.5
            }
        ],
        runtime_seconds=2.5,
        data_freshness="CURRENT",
        errors=[],
        warnings=[],
        reconciliation_status="PASS"
    )
    
    # Write test artifact
    date = datetime.now().strftime('%Y-%m-%d')
    json_path, md_path = writer.write_daily_artifact(date, test_data)
    
    print(f"\n✅ Test artifact written:")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    
    # Read it back
    artifact = writer.read_artifact(date)
    print(f"\n✅ Artifact read back successfully")
    print(f"Date: {artifact['date']}")
    print(f"Positions: {len(artifact['positions']['open'])}")
