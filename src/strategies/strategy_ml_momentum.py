#!/usr/bin/env python3
"""
Strategy 3: ML Momentum
Machine learning-based momentum prediction using classification
IMPROVED: Uses classifier (probability of positive return) instead of regressor
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategy_base import TradingStrategy
from typing import List, Dict
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import pickle


class MLMomentumStrategy(TradingStrategy):
    """Machine Learning momentum strategy using Random Forest"""
    
    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="ML Momentum",
            capital=capital
        )
        self.hold_days = 5
        # IMPROVED: Use Logistic Regression classifier
        self.model = LogisticRegression(max_iter=1000, random_state=42)
        self.scaler = StandardScaler()
        self.model_trained = False
        self.min_probability = 0.6  # Minimum probability for buy signal
        self.model_path = Path(__file__).parent.parent / "data" / "ml_momentum_model.pkl"
        self.scaler_path = Path(__file__).parent.parent / "data" / "ml_momentum_scaler.pkl"
        self._load_model()

    def _load_model(self):
        """Load model and scaler from disk if available."""
        try:
            if self.model_path.exists() and self.scaler_path.exists():
                with open(self.model_path, "rb") as model_file:
                    self.model = pickle.load(model_file)
                with open(self.scaler_path, "rb") as scaler_file:
                    self.scaler = pickle.load(scaler_file)
                self.model_trained = True
        except Exception:
            self.model_trained = False
        
    def _prepare_features(self, symbol_data: pd.DataFrame) -> np.array:
        """Extract features for ML model"""
        features = []
        
        # Technical indicators
        features.append(symbol_data['rsi'].iloc[-1] if 'rsi' in symbol_data else 50)
        features.append(symbol_data['close'].iloc[-1] / symbol_data['close'].iloc[-5] - 1 if len(symbol_data) >= 5 else 0)  # 5-day return
        features.append(symbol_data['close'].iloc[-1] / symbol_data['close'].iloc[-20] - 1 if len(symbol_data) >= 20 else 0)  # 20-day return
        features.append(symbol_data['volume'].iloc[-1] / symbol_data['volume'].iloc[-20:].mean() if len(symbol_data) >= 20 else 1)  # Volume ratio
        
        # Price momentum
        if len(symbol_data) >= 10:
            features.append((symbol_data['close'].iloc[-1] - symbol_data['close'].iloc[-10]) / symbol_data['close'].iloc[-10])
        else:
            features.append(0)
        
        return np.array(features).reshape(1, -1)
    
    def _train_model(self, market_data: pd.DataFrame):
        """Train model on historical data (simplified for demo)"""
        # In production, this would use historical data
        # For now, use a simple heuristic-based training
        X_train = []
        y_train = []
        
        for symbol in market_data['symbol'].unique():
            symbol_data = market_data[market_data['symbol'] == symbol]
            if len(symbol_data) < 30:
                continue
            
            for i in range(20, len(symbol_data) - 5):
                window = symbol_data.iloc[i-20:i]
                future_return = (symbol_data.iloc[i+5]['close'] - symbol_data.iloc[i]['close']) / symbol_data.iloc[i]['close']
                
                features = [
                    window['rsi'].iloc[-1] if 'rsi' in window else 50,
                    window['close'].iloc[-1] / window['close'].iloc[0] - 1,
                    window['volume'].iloc[-1] / window['volume'].mean(),
                ]
                
                X_train.append(features)
                y_train.append(1 if future_return > 0.02 else 0)
        
        if len(X_train) > 50:
            X_train = self.scaler.fit_transform(X_train)
            # Train model
            self.model.fit(X_train, y_train)
            self.model_trained = True
            self._save_model()

    def _save_model(self):
        """Persist model and scaler to disk."""
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.model_path, "wb") as model_file:
                pickle.dump(self.model, model_file)
            with open(self.scaler_path, "wb") as scaler_file:
                pickle.dump(self.scaler, scaler_file)
        except Exception:
            pass
    
    def generate_signals(self, market_data: pd.DataFrame) -> List[Dict]:
        """Generate signals using ML predictions"""
        signals = []
        
        # Train model if not trained
        if not self.model_trained:
            self._train_model(market_data)
        
        for symbol in market_data['symbol'].unique():
            symbol_data = market_data[market_data['symbol'] == symbol]
            
            if len(symbol_data) < 20:
                continue
            
            price = symbol_data['close'].iloc[-1]
            
            # Get features and predict
            try:
                if not self.model_trained:
                    continue

                features = self._prepare_features(symbol_data)
                features_scaled = self.scaler.transform(features)
                prediction = self.model.predict(features_scaled)[0]
                confidence = self.model.predict_proba(features_scaled)[0][1]
                
                # Buy signal: Model predicts positive return with high confidence
                if prediction == 1 and confidence > self.min_probability and symbol not in self.positions:
                    shares = self.calculate_position_size(price, max_position_pct=0.10)
                    latest_date = symbol_data.index[-1]
                    
                    signals.append({
                        'symbol': symbol,
                        'action': 'BUY',
                        'shares': shares,
                        'price': price,
                        'value': shares * price,
                        'confidence': confidence,
                        'reasoning': f'ML probability of positive return: {confidence*100:.1f}%',
                        'asof_date': latest_date
                    })
                
                # Sell signal: Held for target days or model predicts negative
                elif symbol in self.positions:
                    days_held = self.get_days_held(symbol, symbol_data.index[-1])
                    if days_held >= self.hold_days or (prediction == 0 and confidence < 0.4):
                        shares = self.positions[symbol]
                        latest_date = symbol_data.index[-1]
                        
                        signals.append({
                            'symbol': symbol,
                            'action': 'SELL',
                            'shares': shares,
                            'price': price,
                            'value': shares * price,
                            'confidence': 1.0 if days_held >= self.hold_days else confidence,
                            'reasoning': f'Held {days_held} days' if days_held >= self.hold_days else 'ML predicts reversal',
                            'asof_date': latest_date
                        })
            except:
                continue
        
        return signals
    
    def get_description(self) -> str:
        return "Logistic Regression classifier predicting probability of positive 5-day return"
