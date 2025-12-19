#!/usr/bin/env python3
"""
Automated ML Pipeline

Runs continuous data collection, feature engineering, and model training.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import schedule
import time
from datetime import datetime
from typing import List

from ml.data_collection_pipeline import collect_comprehensive_data, EnhancedDataCollector
from ml.feature_engineering_pipeline import generate_training_data, FeatureEngineer
from ml.continuous_learning_engine import ContinuousLearningEngine
from utils.enhanced_logging import get_logger
from utils.monitoring import monitor
from utils.notifications import notify, NotificationChannel, NotificationPriority

logger = get_logger(__name__)


class AutomatedMLPipeline:
    """Manages automated ML pipeline execution."""

    def __init__(self, tickers: List[str]):
        self.tickers = tickers
        self.data_collector = EnhancedDataCollector()
        self.feature_engineer = FeatureEngineer()
        self.learning_engine = ContinuousLearningEngine()

    def hourly_data_collection(self):
        """Collect real-time data every hour."""
        logger.info("Starting hourly data collection")
        
        try:
            for ticker in self.tickers:
                # Collect news
                articles = self.data_collector.collect_news_sentiment(ticker, days=1)
                self.data_collector.store_news_articles(articles)
                
            logger.info("Hourly data collection complete")
            
        except Exception as e:
            logger.error(f"Hourly data collection failed: {e}", error=e)
            notify(
                f"Hourly data collection failed: {e}",
                channel=NotificationChannel.SLACK,
                priority=NotificationPriority.HIGH
            )

    def daily_feature_generation(self):
        """Generate features for today's data."""
        logger.info("Starting daily feature generation")
        
        try:
            # Generate features for yesterday (data is complete)
            yesterday = datetime.now().date()
            
            for ticker in self.tickers:
                features = self.feature_engineer.create_features_for_ticker(ticker, yesterday)
                targets = self.feature_engineer.calculate_target_returns(ticker, yesterday)
                
                if features:
                    self.feature_engineer._store_training_sample(ticker, yesterday, features, targets)
            
            logger.info("Daily feature generation complete")
            
        except Exception as e:
            logger.error(f"Daily feature generation failed: {e}", error=e)
            notify(
                f"Daily feature generation failed: {e}",
                channel=NotificationChannel.SLACK,
                priority=NotificationPriority.HIGH
            )

    def daily_model_evaluation(self):
        """Evaluate model performance daily."""
        logger.info("Starting daily model evaluation")
        
        try:
            current_version = self.learning_engine._get_production_model_version()
            
            if not current_version:
                logger.warning("No production model found")
                return
            
            metrics = self.learning_engine.evaluate_model_performance(current_version, days=7)
            
            # Check if retraining needed
            if self.learning_engine.should_retrain(current_version):
                logger.info("Model performance degraded, scheduling retraining")
                notify(
                    f"Model {current_version} performance degraded. Retraining scheduled.",
                    channel=NotificationChannel.SLACK,
                    priority=NotificationPriority.MEDIUM
                )
                # Trigger immediate retraining
                self.weekly_model_training()
            else:
                logger.info(f"Model performance acceptable: {metrics}")
            
        except Exception as e:
            logger.error(f"Daily model evaluation failed: {e}", error=e)

    def weekly_model_training(self):
        """Train new model weekly."""
        logger.info("Starting weekly model training")
        
        try:
            notify(
                "Weekly model training started",
                channel=NotificationChannel.SLACK,
                priority=NotificationPriority.MEDIUM
            )
            
            # Run automated retraining
            self.learning_engine.automated_retraining_cycle()
            
            notify(
                "Weekly model training complete",
                channel=NotificationChannel.SLACK,
                priority=NotificationPriority.MEDIUM
            )
            
        except Exception as e:
            logger.error(f"Weekly model training failed: {e}", error=e)
            notify(
                f"Weekly model training FAILED: {e}",
                channel=NotificationChannel.SLACK,
                priority=NotificationPriority.CRITICAL
            )

    def weekly_comprehensive_data_collection(self):
        """Collect comprehensive data weekly."""
        logger.info("Starting weekly comprehensive data collection")
        
        try:
            # Collect fundamentals for all tickers
            for ticker in self.tickers:
                fundamentals = self.data_collector.collect_fundamentals(ticker)
                self.data_collector.store_fundamentals(fundamentals)
            
            logger.info("Weekly comprehensive data collection complete")
            
        except Exception as e:
            logger.error(f"Weekly data collection failed: {e}", error=e)

    def monthly_performance_report(self):
        """Generate monthly performance report."""
        logger.info("Generating monthly performance report")
        
        try:
            current_version = self.learning_engine._get_production_model_version()
            
            if not current_version:
                return
            
            metrics = self.learning_engine.evaluate_model_performance(current_version, days=30)
            
            report = f"""
📊 Monthly ML Performance Report

Model Version: {current_version}
Period: Last 30 days

Performance Metrics:
- Accuracy: {metrics.get('accuracy', 0):.2%}
- MAE: {metrics.get('mae', 0):.6f}
- MSE: {metrics.get('mse', 0):.6f}
- Predictions: {metrics.get('count', 0)}

Status: {'✅ Performing well' if metrics.get('accuracy', 0) > 0.55 else '⚠️ Needs attention'}
            """
            
            notify(
                report,
                channel=NotificationChannel.SLACK,
                priority=NotificationPriority.LOW
            )
            
            logger.info("Monthly performance report generated")
            
        except Exception as e:
            logger.error(f"Monthly report generation failed: {e}", error=e)

    def setup_schedule(self):
        """Set up automated schedule."""
        logger.info("Setting up automated ML pipeline schedule")
        
        # Hourly: Data collection
        schedule.every().hour.at(":00").do(self.hourly_data_collection)
        
        # Daily: Feature generation (6 AM)
        schedule.every().day.at("06:00").do(self.daily_feature_generation)
        
        # Daily: Model evaluation (7 AM)
        schedule.every().day.at("07:00").do(self.daily_model_evaluation)
        
        # Weekly: Model training (Sunday 2 AM)
        schedule.every().sunday.at("02:00").do(self.weekly_model_training)
        
        # Weekly: Comprehensive data collection (Saturday 1 AM)
        schedule.every().saturday.at("01:00").do(self.weekly_comprehensive_data_collection)
        
        # Monthly: Performance report (1st of month, 9 AM)
        schedule.every().month.at("09:00").do(self.monthly_performance_report)
        
        logger.info("Schedule configured:")
        logger.info("  - Hourly: Data collection")
        logger.info("  - Daily 6 AM: Feature generation")
        logger.info("  - Daily 7 AM: Model evaluation")
        logger.info("  - Sunday 2 AM: Model training")
        logger.info("  - Saturday 1 AM: Comprehensive data collection")
        logger.info("  - Monthly 1st 9 AM: Performance report")

    def run(self):
        """Run the automated pipeline."""
        logger.info("Starting automated ML pipeline")
        
        notify(
            "🚀 Automated ML Pipeline Started",
            channel=NotificationChannel.SLACK,
            priority=NotificationPriority.LOW
        )
        
        self.setup_schedule()
        
        # Run initial data collection
        logger.info("Running initial data collection...")
        self.hourly_data_collection()
        
        # Main loop
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
            except KeyboardInterrupt:
                logger.info("Pipeline stopped by user")
                notify(
                    "⏹️ Automated ML Pipeline Stopped",
                    channel=NotificationChannel.SLACK,
                    priority=NotificationPriority.LOW
                )
                break
                
            except Exception as e:
                logger.error(f"Pipeline error: {e}", error=e)
                notify(
                    f"⚠️ Pipeline Error: {e}",
                    channel=NotificationChannel.SLACK,
                    priority=NotificationPriority.CRITICAL
                )
                time.sleep(300)  # Wait 5 minutes before retrying


def main():
    """Main entry point."""
    # S&P 500 tickers (top 100 for now)
    tickers = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "BRK.B", "JPM", "JNJ",
        "V", "PG", "UNH", "HD", "MA", "DIS", "PYPL", "NFLX", "ADBE", "CRM",
        "INTC", "CSCO", "PFE", "KO", "PEP", "ABT", "TMO", "AVGO", "COST", "NKE",
        "MRK", "WMT", "DHR", "VZ", "CMCSA", "MCD", "NEE", "UPS", "HON", "QCOM",
        "TXN", "LIN", "BMY", "PM", "UNP", "RTX", "LOW", "ORCL", "IBM", "BA",
        # Add more as needed
    ]
    
    pipeline = AutomatedMLPipeline(tickers)
    pipeline.run()


if __name__ == "__main__":
    main()
