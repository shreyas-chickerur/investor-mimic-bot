"""
ML-Based Adaptive Learning Engine

Uses machine learning to iteratively optimize factor weights based on
historical performance. Learns which factors work best in different conditions.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


@dataclass
class MLConfig:
    """ML configuration."""

    lookback_periods: int = 252  # 1 year of trading days
    validation_split: float = 0.2
    n_splits: int = 5  # Time series cross-validation
    random_state: int = 42


@dataclass
class FactorPerformance:
    """Performance of a factor over time."""

    factor_name: str
    weights_history: List[float]
    returns_history: List[float]
    sharpe_history: List[float]
    optimal_weight: float
    confidence: float


class AdaptiveLearningEngine:
    """
    ML-based engine that learns optimal factor weights from historical data.
    """

    def __init__(self, config: Optional[MLConfig] = None):
        """
        Initialize adaptive learning engine.

        Args:
            config: ML configuration
        """
        self.config = config or MLConfig()
        self.models = {
            "random_forest": RandomForestRegressor(
                n_estimators=100, max_depth=10, random_state=self.config.random_state
            ),
            "gradient_boosting": GradientBoostingRegressor(
                n_estimators=100, max_depth=5, random_state=self.config.random_state
            ),
            "ridge": Ridge(alpha=1.0),
        }
        self.scaler = StandardScaler()
        self.best_model = None
        self.feature_importance = {}

    def prepare_training_data(
        self, factor_scores: pd.DataFrame, returns: pd.Series, market_features: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare training data from historical factor scores and returns.

        Args:
            factor_scores: DataFrame with factor scores over time
                          Columns: date, conviction, news, insider, technical, etc.
            returns: Series of forward returns
            market_features: DataFrame with market regime features
                           Columns: vix, breadth, trend_strength, etc.

        Returns:
            Tuple of (X, y) for training
        """
        # Combine factor scores with market features
        X = pd.concat([factor_scores, market_features], axis=1)

        # Remove date column if present
        if "date" in X.columns:
            X = X.drop("date", axis=1)

        # Handle missing values
        X = X.fillna(X.mean())

        # Align with returns
        X, y = X.align(returns, join="inner", axis=0)

        return X.values, y.values

    def train_models(self, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
        """
        Train multiple models and select the best one.

        Args:
            X: Feature matrix
            y: Target returns

        Returns:
            Dictionary of model scores
        """
        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Time series cross-validation
        tscv = TimeSeriesSplit(n_splits=self.config.n_splits)

        model_scores = {}

        for name, model in self.models.items():
            # Cross-validation score
            scores = cross_val_score(model, X_scaled, y, cv=tscv, scoring="neg_mean_squared_error")

            mean_score = -scores.mean()  # Convert back to positive MSE
            model_scores[name] = mean_score

            logger.info(f"{name}: MSE = {mean_score:.6f}")

        # Select best model
        best_model_name = min(model_scores, key=model_scores.get)
        self.best_model = self.models[best_model_name]

        # Train best model on full dataset
        self.best_model.fit(X_scaled, y)

        logger.info(f"Best model: {best_model_name}")

        # Calculate feature importance
        if hasattr(self.best_model, "feature_importances_"):
            self.feature_importance = dict(
                zip(range(X.shape[1]), self.best_model.feature_importances_)
            )

        return model_scores

    def optimize_factor_weights(
        self,
        factor_scores: pd.DataFrame,
        returns: pd.Series,
        market_features: pd.DataFrame,
        current_weights: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Optimize factor weights using ML.

        Args:
            factor_scores: Historical factor scores
            returns: Historical returns
            market_features: Market regime features
            current_weights: Current factor weights

        Returns:
            Optimized factor weights
        """
        # Prepare data
        X, y = self.prepare_training_data(factor_scores, returns, market_features)

        # Train models
        model_scores = self.train_models(X, y)

        # Get feature importance (factor importance)
        if self.feature_importance:
            factor_names = list(factor_scores.columns)
            if "date" in factor_names:
                factor_names.remove("date")

            # Normalize importance to weights
            total_importance = sum(self.feature_importance.values())
            optimized_weights = {}

            for i, factor in enumerate(factor_names):
                if i in self.feature_importance:
                    optimized_weights[factor] = self.feature_importance[i] / total_importance
                else:
                    optimized_weights[factor] = current_weights.get(factor, 0.0)

            # Ensure weights sum to 1
            total_weight = sum(optimized_weights.values())
            optimized_weights = {k: v / total_weight for k, v in optimized_weights.items()}

            return optimized_weights

        return current_weights

    def predict_optimal_weights(
        self, current_factor_scores: Dict[str, float], current_market_features: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Predict optimal factor weights for current conditions.

        Args:
            current_factor_scores: Current factor scores
            current_market_features: Current market features

        Returns:
            Predicted optimal weights
        """
        if self.best_model is None:
            logger.warning("No trained model available")
            return current_factor_scores

        # Combine features
        features = {**current_factor_scores, **current_market_features}
        X = np.array([list(features.values())])

        # Scale
        X_scaled = self.scaler.transform(X)

        # Predict
        prediction = self.best_model.predict(X_scaled)[0]

        # Convert prediction to weights (simplified)
        # In practice, this would be more sophisticated
        return current_factor_scores

    def save_model(self, path: Path):
        """Save trained model."""
        if self.best_model is not None:
            joblib.dump(
                {
                    "model": self.best_model,
                    "scaler": self.scaler,
                    "feature_importance": self.feature_importance,
                },
                path,
            )
            logger.info(f"Model saved to {path}")

    def load_model(self, path: Path):
        """Load trained model."""
        if path.exists():
            data = joblib.load(path)
            self.best_model = data["model"]
            self.scaler = data["scaler"]
            self.feature_importance = data.get("feature_importance", {})
            logger.info(f"Model loaded from {path}")


class ReinforcementLearningOptimizer:
    """
    Reinforcement learning approach to optimize factor weights.
    Uses Q-learning to learn optimal weight adjustments.
    """

    def __init__(
        self,
        n_factors: int = 8,
        learning_rate: float = 0.01,
        discount_factor: float = 0.95,
        epsilon: float = 0.1,
    ):
        """
        Initialize RL optimizer.

        Args:
            n_factors: Number of factors
            learning_rate: Learning rate for Q-learning
            discount_factor: Discount factor for future rewards
            epsilon: Exploration rate
        """
        self.n_factors = n_factors
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon

        # Q-table: state -> action -> value
        # State: discretized market regime + current weights
        # Action: weight adjustment direction for each factor
        self.q_table = {}

        self.state_history = []
        self.action_history = []
        self.reward_history = []

    def discretize_state(
        self,
        market_regime: str,
        current_weights: Dict[str, float],
        performance_metrics: Dict[str, float],
    ) -> str:
        """
        Discretize continuous state into discrete state representation.

        Args:
            market_regime: Current market regime (bull, bear, etc.)
            current_weights: Current factor weights
            performance_metrics: Recent performance metrics

        Returns:
            State string
        """
        # Discretize weights into bins
        weight_bins = {
            factor: int(weight * 10) for factor, weight in current_weights.items()  # 0-10 bins
        }

        # Discretize performance
        sharpe_bin = int(performance_metrics.get("sharpe_ratio", 0) * 2)  # 0-10 bins

        state = f"{market_regime}_{sharpe_bin}_" + "_".join(
            f"{k}:{v}" for k, v in sorted(weight_bins.items())
        )

        return state

    def select_action(self, state: str) -> Dict[str, int]:
        """
        Select action using epsilon-greedy policy.

        Args:
            state: Current state

        Returns:
            Action (weight adjustments: -1, 0, +1 for each factor)
        """
        # Epsilon-greedy exploration
        if np.random.random() < self.epsilon:
            # Random action
            return {f"factor_{i}": np.random.choice([-1, 0, 1]) for i in range(self.n_factors)}

        # Greedy action (best known action for this state)
        if state not in self.q_table:
            self.q_table[state] = {}

        if not self.q_table[state]:
            # No actions tried yet, random
            return {f"factor_{i}": np.random.choice([-1, 0, 1]) for i in range(self.n_factors)}

        # Best action
        best_action = max(self.q_table[state], key=self.q_table[state].get)
        return eval(best_action)  # Convert string back to dict

    def update_q_value(self, state: str, action: Dict[str, int], reward: float, next_state: str):
        """
        Update Q-value using Q-learning update rule.

        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
        """
        if state not in self.q_table:
            self.q_table[state] = {}

        action_str = str(action)

        # Current Q-value
        current_q = self.q_table[state].get(action_str, 0.0)

        # Max Q-value for next state
        if next_state in self.q_table and self.q_table[next_state]:
            max_next_q = max(self.q_table[next_state].values())
        else:
            max_next_q = 0.0

        # Q-learning update
        new_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_next_q - current_q
        )

        self.q_table[state][action_str] = new_q

    def train_episode(
        self, historical_data: pd.DataFrame, initial_weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Train one episode on historical data.

        Args:
            historical_data: Historical market data with returns
            initial_weights: Starting factor weights

        Returns:
            Final optimized weights
        """
        current_weights = initial_weights.copy()
        total_reward = 0.0

        for i in range(len(historical_data) - 1):
            # Get current state
            row = historical_data.iloc[i]
            state = self.discretize_state(
                market_regime=row.get("regime", "unknown"),
                current_weights=current_weights,
                performance_metrics={"sharpe_ratio": row.get("sharpe", 0)},
            )

            # Select action
            action = self.select_action(state)

            # Apply action (adjust weights)
            new_weights = self._apply_action(current_weights, action)

            # Calculate reward (next period return with new weights)
            next_row = historical_data.iloc[i + 1]
            reward = self._calculate_reward(new_weights, next_row)

            # Get next state
            next_state = self.discretize_state(
                market_regime=next_row.get("regime", "unknown"),
                current_weights=new_weights,
                performance_metrics={"sharpe_ratio": next_row.get("sharpe", 0)},
            )

            # Update Q-value
            self.update_q_value(state, action, reward, next_state)

            # Update state
            current_weights = new_weights
            total_reward += reward

        logger.info(f"Episode total reward: {total_reward:.4f}")

        return current_weights

    def _apply_action(self, weights: Dict[str, float], action: Dict[str, int]) -> Dict[str, float]:
        """Apply weight adjustments from action."""
        new_weights = weights.copy()

        # Apply adjustments
        factor_names = list(weights.keys())
        for i, factor in enumerate(factor_names):
            adjustment = action.get(f"factor_{i}", 0) * 0.05  # 5% adjustment
            new_weights[factor] = max(0.0, min(1.0, weights[factor] + adjustment))

        # Normalize to sum to 1
        total = sum(new_weights.values())
        new_weights = {k: v / total for k, v in new_weights.items()}

        return new_weights

    def _calculate_reward(self, weights: Dict[str, float], next_period_data: pd.Series) -> float:
        """Calculate reward for given weights."""
        # Simplified: use Sharpe ratio as reward
        return next_period_data.get("sharpe", 0.0)


class EnsembleOptimizer:
    """
    Ensemble approach combining multiple optimization methods.
    """

    def __init__(self):
        """Initialize ensemble optimizer."""
        self.ml_engine = AdaptiveLearningEngine()
        self.rl_optimizer = ReinforcementLearningOptimizer()
        self.optimizers = {"ml": self.ml_engine, "rl": self.rl_optimizer}
        self.weights_history = []

    def optimize(
        self, historical_data: pd.DataFrame, current_weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Optimize weights using ensemble of methods.

        Args:
            historical_data: Historical performance data
            current_weights: Current factor weights

        Returns:
            Optimized weights
        """
        optimized_weights = {}

        # Get predictions from each optimizer
        # (Simplified - would need proper implementation)

        # Average the predictions
        all_weights = [current_weights]  # Start with current

        # Ensemble average
        final_weights = {}
        for factor in current_weights.keys():
            final_weights[factor] = np.mean([w[factor] for w in all_weights])

        # Normalize
        total = sum(final_weights.values())
        final_weights = {k: v / total for k, v in final_weights.items()}

        self.weights_history.append({"timestamp": pd.Timestamp.now(), "weights": final_weights})

        return final_weights
