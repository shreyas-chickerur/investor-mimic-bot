"""
Ensemble Models for Factor Weight Optimization

Combines multiple ML models for more robust predictions.
"""

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit

from utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class EnsembleOptimizer:
    """Ensemble model for factor weight optimization."""

    def __init__(self, n_models: int = 3):
        self.n_models = n_models
        self.models = []
        self.weights = None
        self.feature_importance = None

    def _create_models(self) -> List:
        """Create ensemble of models."""
        return (
            [
                RandomForestRegressor(n_estimators=100, max_depth=10, min_samples_split=5, random_state=42 + i)
                for i in range(self.n_models)
            ]
            + [
                GradientBoostingRegressor(n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42 + i)
                for i in range(self.n_models)
            ]
            + [Ridge(alpha=1.0, random_state=42)]
        )

    def train(self, X: pd.DataFrame, y: pd.Series, cv_splits: int = 5) -> Dict[str, Any]:
        """
        Train ensemble models.

        Args:
            X: Feature matrix
            y: Target variable (returns)
            cv_splits: Number of cross-validation splits

        Returns:
            Training metrics
        """
        logger.info(f"Training ensemble with {len(self._create_models())} models")

        self.models = self._create_models()
        tscv = TimeSeriesSplit(n_splits=cv_splits)

        # Train each model
        cv_scores = []
        for i, model in enumerate(self.models):
            model_scores = []

            for train_idx, val_idx in tscv.split(X):
                X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

                model.fit(X_train, y_train)
                score = model.score(X_val, y_val)
                model_scores.append(score)

            avg_score = np.mean(model_scores)
            cv_scores.append(avg_score)
            logger.info(f"Model {i+1} CV score: {avg_score:.4f}")

        # Train on full dataset
        for model in self.models:
            model.fit(X, y)

        # Calculate model weights based on CV performance
        cv_scores = np.array(cv_scores)
        cv_scores = np.maximum(cv_scores, 0)  # Ensure non-negative
        self.weights = cv_scores / cv_scores.sum() if cv_scores.sum() > 0 else np.ones(len(cv_scores)) / len(cv_scores)

        # Calculate feature importance
        self._calculate_feature_importance(X)

        return {
            "n_models": len(self.models),
            "cv_scores": cv_scores.tolist(),
            "model_weights": self.weights.tolist(),
            "avg_cv_score": np.mean(cv_scores),
        }

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make ensemble predictions."""
        if not self.models:
            raise ValueError("Models not trained. Call train() first.")

        # Get predictions from all models
        predictions = np.array([model.predict(X) for model in self.models])

        # Weighted average
        ensemble_pred = np.average(predictions, axis=0, weights=self.weights)

        return ensemble_pred

    def _calculate_feature_importance(self, X: pd.DataFrame):
        """Calculate aggregated feature importance."""
        importances = []

        for model in self.models:
            if hasattr(model, "feature_importances_"):
                importances.append(model.feature_importances_)
            elif hasattr(model, "coef_"):
                importances.append(np.abs(model.coef_))

        if importances:
            # Weighted average of importances
            self.feature_importance = pd.Series(
                np.average(importances, axis=0, weights=self.weights[: len(importances)]),
                index=X.columns,
            ).sort_values(ascending=False)

    def get_feature_importance(self) -> pd.Series:
        """Get feature importance scores."""
        if self.feature_importance is None:
            raise ValueError("Feature importance not calculated. Train model first.")
        return self.feature_importance


class StackedEnsemble:
    """Stacked ensemble with meta-learner."""

    def __init__(self):
        self.base_models = []
        self.meta_model = None

    def train(self, X: pd.DataFrame, y: pd.Series, cv_splits: int = 5) -> Dict[str, Any]:
        """Train stacked ensemble."""

        # Base models
        self.base_models = [
            RandomForestRegressor(n_estimators=100, random_state=42),
            GradientBoostingRegressor(n_estimators=100, random_state=42),
            Ridge(alpha=1.0),
        ]

        # Meta model
        self.meta_model = Ridge(alpha=0.1)

        tscv = TimeSeriesSplit(n_splits=cv_splits)

        # Generate meta-features
        meta_features = np.zeros((len(X), len(self.base_models)))

        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train = y.iloc[train_idx]

            for i, model in enumerate(self.base_models):
                model.fit(X_train, y_train)
                meta_features[val_idx, i] = model.predict(X_val)

        # Train base models on full data
        for model in self.base_models:
            model.fit(X, y)

        # Train meta model
        self.meta_model.fit(meta_features, y)

        logger.info("Stacked ensemble trained successfully")

        return {
            "n_base_models": len(self.base_models),
            "meta_model": type(self.meta_model).__name__,
        }

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make stacked predictions."""
        if not self.base_models or self.meta_model is None:
            raise ValueError("Models not trained. Call train() first.")

        # Get base model predictions
        base_predictions = np.column_stack([model.predict(X) for model in self.base_models])

        # Meta model prediction
        final_pred = self.meta_model.predict(base_predictions)

        return final_pred


def optimize_factor_weights_ensemble(
    historical_data: pd.DataFrame, factor_columns: List[str], target_column: str = "returns"
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """
    Optimize factor weights using ensemble methods.

    Args:
        historical_data: Historical data with factors and returns
        factor_columns: List of factor column names
        target_column: Target column name

    Returns:
        (optimized_weights, metrics)
    """

    X = historical_data[factor_columns]
    y = historical_data[target_column]

    # Train ensemble
    ensemble = EnsembleOptimizer(n_models=3)
    metrics = ensemble.train(X, y)

    # Get feature importance as weights
    importance = ensemble.get_feature_importance()

    # Normalize to sum to 1
    weights = {}
    total = importance.sum()
    for factor in factor_columns:
        weights[factor] = float(importance.get(factor, 0) / total)

    logger.info(f"Optimized weights: {weights}")

    return weights, metrics
