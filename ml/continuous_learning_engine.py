"""
Continuous Learning Engine

Automatically trains, evaluates, and deploys improved models.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import pickle
import json
from pathlib import Path

from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.preprocessing import StandardScaler

from ml.ensemble_models import EnsembleOptimizer, StackedEnsemble
from utils.enhanced_logging import get_logger
from utils.monitoring import monitor
from db.connection_pool import get_db_session

logger = get_logger(__name__)


class ContinuousLearningEngine:
    """Manages continuous model training and improvement."""

    def __init__(self, model_dir: str = "models/"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.current_model_version = None
        self.scaler = StandardScaler()

    def create_training_dataset(self, lookback_days: int = 1095) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Create comprehensive training dataset from database.

        Args:
            lookback_days: Days of historical data (default: 3 years)

        Returns:
            (features_df, target_series)
        """
        logger.info(f"Creating training dataset with {lookback_days} days of data")

        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)

        with get_db_session() as session:
            # Get all training data
            query = """
                SELECT 
                    t.ticker,
                    t.date,
                    t.features,
                    t.target_return_10d
                FROM training_data t
                WHERE t.date >= :start_date 
                  AND t.date <= :end_date
                  AND t.target_return_10d IS NOT NULL
                ORDER BY t.date
            """

            result = session.execute(query, {"start_date": start_date, "end_date": end_date})
            rows = result.fetchall()

        if not rows:
            logger.warning("No training data found!")
            return pd.DataFrame(), pd.Series()

        # Parse features and create DataFrame
        data = []
        for row in rows:
            features = json.loads(row[2]) if isinstance(row[2], str) else row[2]
            features["ticker"] = row[0]
            features["date"] = row[1]
            features["target"] = row[3]
            data.append(features)

        df = pd.DataFrame(data)

        # Separate features and target
        feature_cols = [col for col in df.columns if col not in ["ticker", "date", "target"]]
        X = df[feature_cols]
        y = df["target"]

        logger.info(f"Training dataset created: {len(X)} samples, {len(feature_cols)} features")

        return X, y

    def train_new_model(self, X: pd.DataFrame, y: pd.Series, model_type: str = "ensemble") -> Tuple[object, Dict]:
        """
        Train a new model on the data.

        Args:
            X: Feature matrix
            y: Target variable
            model_type: Type of model to train

        Returns:
            (trained_model, metrics)
        """
        logger.info(f"Training new {model_type} model on {len(X)} samples")

        # Split data (time series split)
        tscv = TimeSeriesSplit(n_splits=5)
        train_idx, test_idx = list(tscv.split(X))[-1]  # Use last split for final evaluation

        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train model
        if model_type == "ensemble":
            model = EnsembleOptimizer(n_models=3)
            training_metrics = model.train(pd.DataFrame(X_train_scaled, columns=X_train.columns), y_train)
        elif model_type == "stacked":
            model = StackedEnsemble()
            training_metrics = model.train(pd.DataFrame(X_train_scaled, columns=X_train.columns), y_train)
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        # Evaluate on test set
        y_pred = model.predict(pd.DataFrame(X_test_scaled, columns=X_test.columns))

        # Calculate metrics
        mse = mean_squared_error(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)

        # Calculate directional accuracy
        direction_correct = ((y_test > 0) == (y_pred > 0)).sum()
        accuracy = direction_correct / len(y_test)

        # Calculate Sharpe ratio (assuming daily returns)
        returns = y_pred
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0

        metrics = {
            "test_mse": float(mse),
            "test_mae": float(mae),
            "test_accuracy": float(accuracy),
            "test_sharpe": float(sharpe),
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "features": list(X.columns),
            "feature_count": len(X.columns),
        }

        logger.info(f"Model trained - Accuracy: {accuracy:.2%}, Sharpe: {sharpe:.2f}, MSE: {mse:.6f}")

        return model, metrics

    def save_model(self, model: object, version: str, metrics: Dict):
        """Save model and metadata."""
        model_path = self.model_dir / f"model_{version}.pkl"
        scaler_path = self.model_dir / f"scaler_{version}.pkl"
        metrics_path = self.model_dir / f"metrics_{version}.json"

        # Save model
        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        # Save scaler
        with open(scaler_path, "wb") as f:
            pickle.dump(self.scaler, f)

        # Save metrics
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)

        logger.info(f"Model {version} saved to {model_path}")

        # Store in database
        self._store_model_metrics(version, metrics)

    def load_model(self, version: str) -> Tuple[object, StandardScaler]:
        """Load model and scaler."""
        model_path = self.model_dir / f"model_{version}.pkl"
        scaler_path = self.model_dir / f"scaler_{version}.pkl"

        with open(model_path, "rb") as f:
            model = pickle.load(f)

        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)

        logger.info(f"Model {version} loaded")
        return model, scaler

    def _store_model_metrics(self, version: str, metrics: Dict):
        """Store model metrics in database."""
        with get_db_session() as session:
            try:
                session.execute(
                    """
                    INSERT INTO model_metrics 
                    (model_version, training_date, test_sharpe, test_accuracy, 
                     test_mse, test_mae, training_samples, hyperparameters)
                    VALUES (:version, :date, :sharpe, :accuracy, :mse, :mae, :samples, :params)
                    ON CONFLICT (model_version) DO UPDATE SET
                        test_sharpe = EXCLUDED.test_sharpe,
                        test_accuracy = EXCLUDED.test_accuracy,
                        test_mse = EXCLUDED.test_mse,
                        test_mae = EXCLUDED.test_mae
                    """,
                    {
                        "version": version,
                        "date": datetime.now(),
                        "sharpe": metrics.get("test_sharpe"),
                        "accuracy": metrics.get("test_accuracy"),
                        "mse": metrics.get("test_mse"),
                        "mae": metrics.get("test_mae"),
                        "samples": metrics.get("training_samples"),
                        "params": json.dumps(metrics),
                    },
                )
                logger.info(f"Metrics stored for model {version}")
            except Exception as e:
                logger.error(f"Error storing model metrics: {e}")

    def evaluate_model_performance(self, version: str, days: int = 7) -> Dict:
        """
        Evaluate model performance over recent period.

        Args:
            version: Model version to evaluate
            days: Number of days to evaluate

        Returns:
            Performance metrics
        """
        logger.info(f"Evaluating model {version} over last {days} days")

        with get_db_session() as session:
            query = """
                SELECT 
                    AVG(ABS(prediction_error)) as mae,
                    AVG(prediction_error * prediction_error) as mse,
                    AVG(CASE WHEN 
                        (predicted_return > 0 AND actual_return > 0) OR
                        (predicted_return < 0 AND actual_return < 0)
                        THEN 1 ELSE 0 END) as accuracy,
                    COUNT(*) as predictions
                FROM model_predictions
                WHERE model_version = :version
                  AND prediction_date >= CURRENT_DATE - INTERVAL ':days days'
                  AND actual_return IS NOT NULL
            """

            result = session.execute(query, {"version": version, "days": days})
            row = result.fetchone()

        if not row or row[3] == 0:
            logger.warning(f"No predictions found for model {version}")
            return {}

        metrics = {
            "mae": float(row[0] or 0),
            "mse": float(row[1] or 0),
            "accuracy": float(row[2] or 0),
            "count": int(row[3]),
        }

        logger.info(f"Model {version} performance: Accuracy={metrics['accuracy']:.2%}, MAE={metrics['mae']:.6f}")

        return metrics

    def should_retrain(self, current_version: str, threshold_accuracy: float = 0.52) -> bool:
        """
        Determine if model should be retrained.

        Args:
            current_version: Current production model version
            threshold_accuracy: Minimum acceptable accuracy

        Returns:
            True if retraining recommended
        """
        metrics = self.evaluate_model_performance(current_version, days=7)

        if not metrics:
            logger.warning("No metrics available, recommending retrain")
            return True

        accuracy = metrics.get("accuracy", 0)

        if accuracy < threshold_accuracy:
            logger.info(f"Accuracy {accuracy:.2%} below threshold {threshold_accuracy:.2%}, recommending retrain")
            return True

        logger.info(f"Model performance acceptable: {accuracy:.2%}")
        return False

    def automated_retraining_cycle(self):
        """
        Execute automated retraining cycle.

        This should be run weekly or when performance degrades.
        """
        logger.info("Starting automated retraining cycle")

        try:
            # Create training dataset
            X, y = self.create_training_dataset(lookback_days=1095)

            if len(X) < 1000:
                logger.warning(f"Insufficient training data: {len(X)} samples")
                return

            # Generate new model version
            version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Train new model
            model, metrics = self.train_new_model(X, y, model_type="ensemble")

            # Save model
            self.save_model(model, version, metrics)

            # Compare with current production model
            current_version = self._get_production_model_version()

            if current_version:
                current_metrics = self.evaluate_model_performance(current_version, days=30)
                new_sharpe = metrics.get("test_sharpe", 0)
                current_sharpe = current_metrics.get("sharpe", 0)

                if new_sharpe > current_sharpe * 1.05:  # 5% improvement
                    logger.info(f"New model {version} outperforms current, promoting to production")
                    self._promote_to_production(version)
                else:
                    logger.info(f"New model {version} does not significantly improve, keeping current")
            else:
                logger.info(f"No current production model, promoting {version}")
                self._promote_to_production(version)

            # Record retraining
            self._record_retraining(version, metrics, "success")

            logger.info("Automated retraining cycle complete")

        except Exception as e:
            logger.error(f"Retraining cycle failed: {e}", error=e)
            self._record_retraining("failed", {}, "failed", str(e))

    def _get_production_model_version(self) -> Optional[str]:
        """Get current production model version."""
        with get_db_session() as session:
            result = session.execute(
                """
                SELECT model_version 
                FROM model_metrics 
                WHERE is_production = TRUE 
                ORDER BY deployed_at DESC 
                LIMIT 1
            """
            )
            row = result.fetchone()
            return row[0] if row else None

    def _promote_to_production(self, version: str):
        """Promote model to production."""
        with get_db_session() as session:
            # Retire current production model
            session.execute(
                """
                UPDATE model_metrics 
                SET is_production = FALSE, 
                    retired_at = NOW() 
                WHERE is_production = TRUE
            """
            )

            # Promote new model
            session.execute(
                """
                UPDATE model_metrics 
                SET is_production = TRUE, 
                    deployed_at = NOW() 
                WHERE model_version = :version
            """,
                {"version": version},
            )

        logger.info(f"Model {version} promoted to production")
        monitor.create_alert("info", f"New model {version} deployed to production", {"version": version})

    def _record_retraining(self, version: str, metrics: Dict, status: str, error: Optional[str] = None):
        """Record retraining attempt."""
        with get_db_session() as session:
            session.execute(
                """
                INSERT INTO model_retraining_schedule 
                (scheduled_time, status, model_version, samples_used, 
                 performance_improvement, error_message)
                VALUES (:time, :status, :version, :samples, :improvement, :error)
            """,
                {
                    "time": datetime.now(),
                    "status": status,
                    "version": version,
                    "samples": metrics.get("training_samples", 0),
                    "improvement": metrics.get("test_sharpe", 0),
                    "error": error,
                },
            )


def run_continuous_learning():
    """Main entry point for continuous learning."""
    engine = ContinuousLearningEngine()
    engine.automated_retraining_cycle()


if __name__ == "__main__":
    run_continuous_learning()
