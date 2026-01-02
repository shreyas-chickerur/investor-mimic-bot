#!/usr/bin/env python3
"""
Signal Funnel Tracker
Tracks signals through each stage: raw → regime → correlation → risk → executed
Provides "Why No Trade" audit trail
"""
import logging
from typing import Dict, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FunnelStage:
    """Tracks counts at each funnel stage"""
    raw_signals: int = 0
    after_regime: int = 0
    after_correlation: int = 0
    after_risk: int = 0
    executed: int = 0
    
    def get_drop_summary(self) -> Dict[str, int]:
        """Calculate drops at each stage"""
        return {
            'regime_filtered': self.raw_signals - self.after_regime,
            'correlation_filtered': self.after_regime - self.after_correlation,
            'risk_filtered': self.after_correlation - self.after_risk,
            'execution_filtered': self.after_risk - self.executed
        }


class SignalFunnelTracker:
    """Tracks signal flow through execution pipeline"""
    
    def __init__(self, db):
        self.db = db
        self.strategy_funnels: Dict[int, FunnelStage] = {}
        self.rejections: List[Dict] = []
    
    def init_strategy(self, strategy_id: int):
        """Initialize funnel tracking for a strategy"""
        if strategy_id not in self.strategy_funnels:
            self.strategy_funnels[strategy_id] = FunnelStage()
    
    def record_raw_signals(self, strategy_id: int, count: int):
        """Record raw signal count"""
        self.init_strategy(strategy_id)
        self.strategy_funnels[strategy_id].raw_signals = count
        logger.info(f"Strategy {strategy_id}: {count} raw signals")
    
    def record_after_regime(self, strategy_id: int, count: int):
        """Record count after regime filter"""
        self.init_strategy(strategy_id)
        self.strategy_funnels[strategy_id].after_regime = count
        dropped = self.strategy_funnels[strategy_id].raw_signals - count
        if dropped > 0:
            logger.info(f"Strategy {strategy_id}: {dropped} signals filtered by regime")
    
    def record_after_correlation(self, strategy_id: int, count: int):
        """Record count after correlation filter"""
        self.init_strategy(strategy_id)
        self.strategy_funnels[strategy_id].after_correlation = count
        dropped = self.strategy_funnels[strategy_id].after_regime - count
        if dropped > 0:
            logger.info(f"Strategy {strategy_id}: {dropped} signals filtered by correlation")
    
    def record_after_risk(self, strategy_id: int, count: int):
        """Record count after risk checks"""
        self.init_strategy(strategy_id)
        self.strategy_funnels[strategy_id].after_risk = count
        dropped = self.strategy_funnels[strategy_id].after_correlation - count
        if dropped > 0:
            logger.info(f"Strategy {strategy_id}: {dropped} signals filtered by risk/cash")
    
    def record_executed(self, strategy_id: int, count: int):
        """Record executed count"""
        self.init_strategy(strategy_id)
        self.strategy_funnels[strategy_id].executed = count
        logger.info(f"Strategy {strategy_id}: {count} signals executed")
    
    def log_rejection(self, strategy_id: int, symbol: str, stage: str, 
                     reason_code: str, details: dict = None, signal_id: int = None):
        """Log a signal rejection with reason"""
        self.rejections.append({
            'strategy_id': strategy_id,
            'symbol': symbol,
            'stage': stage,
            'reason_code': reason_code,
            'details': details,
            'signal_id': signal_id
        })
        
        # Persist to database
        self.db.log_signal_rejection(
            strategy_id=strategy_id,
            symbol=symbol,
            stage=stage,
            reason_code=reason_code,
            details=details,
            signal_id=signal_id
        )
        
        logger.debug(f"Rejection: {symbol} at {stage} - {reason_code}")
    
    def save_to_database(self, strategy_id: int, strategy_name: str):
        """Persist funnel data to database"""
        if strategy_id not in self.strategy_funnels:
            return
        
        funnel = self.strategy_funnels[strategy_id]
        self.db.save_signal_funnel(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            raw=funnel.raw_signals,
            regime=funnel.after_regime,
            correlation=funnel.after_correlation,
            risk=funnel.after_risk,
            executed=funnel.executed
        )
        
        logger.info(f"Saved funnel data for {strategy_name}")
    
    def get_funnel_summary(self, strategy_id: int) -> Dict:
        """Get funnel summary for a strategy"""
        if strategy_id not in self.strategy_funnels:
            return {}
        
        funnel = self.strategy_funnels[strategy_id]
        drops = funnel.get_drop_summary()
        
        return {
            'raw': funnel.raw_signals,
            'regime': funnel.after_regime,
            'correlation': funnel.after_correlation,
            'risk': funnel.after_risk,
            'executed': funnel.executed,
            'drops': drops
        }
    
    def get_why_no_trade_report(self, strategy_id: int, strategy_name: str) -> str:
        """Generate 'Why No Trade' report for email"""
        if strategy_id not in self.strategy_funnels:
            return f"{strategy_name}: No signals generated"
        
        funnel = self.strategy_funnels[strategy_id]
        
        if funnel.executed > 0:
            return f"{strategy_name}: ✅ {funnel.executed} trades executed"
        
        # Find the blocker
        if funnel.raw_signals == 0:
            return f"{strategy_name}: ❌ No raw signals generated"
        
        drops = funnel.get_drop_summary()
        blockers = []
        
        if drops['regime_filtered'] > 0:
            blockers.append(f"regime filter ({drops['regime_filtered']})")
        if drops['correlation_filtered'] > 0:
            blockers.append(f"correlation filter ({drops['correlation_filtered']})")
        if drops['risk_filtered'] > 0:
            blockers.append(f"risk/cash limits ({drops['risk_filtered']})")
        if drops['execution_filtered'] > 0:
            blockers.append(f"execution issues ({drops['execution_filtered']})")
        
        if not blockers:
            return f"{strategy_name}: ⚠️ Unknown blocker (funnel: {funnel.raw_signals}→{funnel.executed})"
        
        # Get example symbols for top blocker
        stage_map = {
            'regime filter': 'REGIME',
            'correlation filter': 'CORRELATION',
            'risk/cash limits': 'RISK'
        }
        
        top_blocker = blockers[0]
        stage = next((stage_map[k] for k in stage_map if k in top_blocker), None)
        
        examples = []
        if stage:
            for rej in self.rejections:
                if rej['strategy_id'] == strategy_id and rej['stage'] == stage:
                    examples.append(rej['symbol'])
                    if len(examples) >= 3:
                        break
        
        example_str = f" (e.g., {', '.join(examples)})" if examples else ""
        
        return f"{strategy_name}: ❌ Blocked by {', '.join(blockers)}{example_str}"
    
    def get_all_funnels_summary(self) -> List[Dict]:
        """Get summary of all strategy funnels"""
        return [
            {
                'strategy_id': sid,
                **self.get_funnel_summary(sid)
            }
            for sid in self.strategy_funnels.keys()
        ]
    
    def generate_funnel_artifact(self, strategy_id: int, strategy_name: str, 
                                run_id: str, artifacts_dir: str = 'artifacts/funnel') -> str:
        """
        Generate signal_funnel.json artifact for this strategy.
        
        Args:
            strategy_id: Strategy ID
            strategy_name: Strategy name
            run_id: Run ID
            artifacts_dir: Directory for artifacts
        
        Returns:
            Path to generated artifact
        """
        import os
        import json
        from datetime import datetime
        
        os.makedirs(artifacts_dir, exist_ok=True)
        
        if strategy_id not in self.strategy_funnels:
            return ""
        
        funnel = self.strategy_funnels[strategy_id]
        
        funnel_data = {
            'run_id': run_id,
            'strategy_id': strategy_id,
            'strategy_name': strategy_name,
            'funnel': {
                'raw_signals': funnel.raw_signals,
                'after_regime': funnel.after_regime,
                'after_correlation': funnel.after_correlation,
                'after_risk': funnel.after_risk,
                'executed': funnel.executed
            },
            'conversion_rates': {
                'regime_pass_rate': funnel.after_regime / funnel.raw_signals if funnel.raw_signals > 0 else 0,
                'correlation_pass_rate': funnel.after_correlation / funnel.after_regime if funnel.after_regime > 0 else 0,
                'risk_pass_rate': funnel.after_risk / funnel.after_correlation if funnel.after_correlation > 0 else 0,
                'execution_rate': funnel.executed / funnel.after_risk if funnel.after_risk > 0 else 0,
                'overall_conversion': funnel.executed / funnel.raw_signals if funnel.raw_signals > 0 else 0
            },
            'timestamp': datetime.now().isoformat()
        }
        
        filename = f"signal_funnel_{strategy_name.replace(' ', '_')}_{run_id}.json"
        filepath = os.path.join(artifacts_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(funnel_data, f, indent=2)
        
        logger.info(f"Generated funnel artifact: {filepath}")
        return filepath
    
    def generate_rejections_artifact(self, strategy_id: int, strategy_name: str,
                                    run_id: str, artifacts_dir: str = 'artifacts/funnel') -> str:
        """
        Generate signal_rejections.json artifact for this strategy.
        
        Args:
            strategy_id: Strategy ID
            strategy_name: Strategy name
            run_id: Run ID
            artifacts_dir: Directory for artifacts
        
        Returns:
            Path to generated artifact
        """
        import os
        import json
        from datetime import datetime
        
        os.makedirs(artifacts_dir, exist_ok=True)
        
        # Filter rejections for this strategy
        strategy_rejections = [r for r in self.rejections if r['strategy_id'] == strategy_id]
        
        # Group rejections by stage and reason
        rejections_by_stage = {}
        for rejection in strategy_rejections:
            stage = rejection['stage']
            if stage not in rejections_by_stage:
                rejections_by_stage[stage] = {}
            
            reason = rejection['reason_code']
            if reason not in rejections_by_stage[stage]:
                rejections_by_stage[stage][reason] = []
            
            rejections_by_stage[stage][reason].append({
                'symbol': rejection['symbol'],
                'details': rejection['details']
            })
        
        # Get rejection summary
        summary = {}
        for rejection in strategy_rejections:
            reason = rejection['reason_code']
            if reason not in summary:
                summary[reason] = 0
            summary[reason] += 1
        
        rejections_data = {
            'run_id': run_id,
            'strategy_id': strategy_id,
            'strategy_name': strategy_name,
            'total_rejections': len(strategy_rejections),
            'rejections_by_stage': rejections_by_stage,
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        }
        
        filename = f"signal_rejections_{strategy_name.replace(' ', '_')}_{run_id}.json"
        filepath = os.path.join(artifacts_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(rejections_data, f, indent=2)
        
        logger.info(f"Generated rejections artifact: {filepath}")
        return filepath
    
    def generate_why_no_trade_artifact(self, run_id: str, 
                                      artifacts_dir: str = 'artifacts/funnel') -> str:
        """
        Generate why_no_trade_summary.json artifact (only when executed trades == 0).
        
        Args:
            run_id: Run ID
            artifacts_dir: Directory for artifacts
        
        Returns:
            Path to generated artifact (empty string if trades were executed)
        """
        import os
        import json
        from datetime import datetime
        
        # Check if any trades were executed
        total_executed = sum(f.executed for f in self.strategy_funnels.values())
        
        if total_executed > 0:
            logger.info("Trades were executed, skipping why_no_trade artifact")
            return ""
        
        os.makedirs(artifacts_dir, exist_ok=True)
        
        # Build why no trade summary
        strategy_reports = []
        for strategy_id, funnel in self.strategy_funnels.items():
            drops = funnel.get_drop_summary()
            
            # Identify primary blocker
            primary_blocker = None
            if funnel.raw_signals == 0:
                primary_blocker = "NO_RAW_SIGNALS"
            elif drops['regime_filtered'] > 0:
                primary_blocker = "REGIME_FILTER"
            elif drops['correlation_filtered'] > 0:
                primary_blocker = "CORRELATION_FILTER"
            elif drops['risk_filtered'] > 0:
                primary_blocker = "RISK_LIMITS"
            elif drops['execution_filtered'] > 0:
                primary_blocker = "EXECUTION_ISSUES"
            
            # Get example symbols for primary blocker
            stage_map = {
                'REGIME_FILTER': 'REGIME',
                'CORRELATION_FILTER': 'CORRELATION',
                'RISK_LIMITS': 'RISK'
            }
            
            examples = []
            if primary_blocker in stage_map:
                stage = stage_map[primary_blocker]
                for rej in self.rejections:
                    if rej['strategy_id'] == strategy_id and rej['stage'] == stage:
                        examples.append({
                            'symbol': rej['symbol'],
                            'reason_code': rej['reason_code'],
                            'details': rej['details']
                        })
                        if len(examples) >= 5:
                            break
            
            strategy_reports.append({
                'strategy_id': strategy_id,
                'funnel': {
                    'raw': funnel.raw_signals,
                    'regime': funnel.after_regime,
                    'correlation': funnel.after_correlation,
                    'risk': funnel.after_risk,
                    'executed': funnel.executed
                },
                'primary_blocker': primary_blocker,
                'drops': drops,
                'example_rejections': examples
            })
        
        why_no_trade_data = {
            'run_id': run_id,
            'total_executed': total_executed,
            'strategies': strategy_reports,
            'timestamp': datetime.now().isoformat()
        }
        
        filename = f"why_no_trade_summary_{run_id}.json"
        filepath = os.path.join(artifacts_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(why_no_trade_data, f, indent=2)
        
        logger.info(f"Generated why_no_trade artifact: {filepath}")
        return filepath
