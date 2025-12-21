#!/usr/bin/env python3
"""
Strategy 2: ML Momentum
Random Forest predicts next-day returns based on technical features
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategy_base import TradingStrategy
from typing import List, Dict
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler


class MLMomentumStrategy(TradingStrategy):
    """Machine Learning momentum strategy using Random Forest"""
    
    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="ML Momentum",
            capital=capital
        )
        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False
        self.hold_days = 15
        self.entry_dates = {}
    
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
            self.model.fit(X_train, y_train)
            self.is_trained = True
    
    def generate_signals(self, market_data: pd.DataFrame) -> List[Dict]:
        """Generate signals using ML predictions"""
        signals = []
        
        # Train model if not trained
        if not self.is_trained:
            self._train_model(market_data)
        
        for symbol in market_data['symbol'].unique():
            symbol_data = market_data[market_data['symbol'] == symbol]
            
            if len(symbol_data) < 20:
                continue
            
            price = symbol_data['close'].iloc[-1]
            
            # Get features and predict
            try:
                features = self._prepare_features(symbol_data)
                features_scaled = self.scaler.transform(features)
                prediction = self.model.predict(features_scaled)[0]
                confidence = self.model.predict_proba(features_scaled)[0][1]
                
                # Buy signal: Model predicts positive return with high confidence
                if prediction == 1 and confidence > 0.6 and symbol not in self.positions:
                    shares = self.calculate_position_size(price, max_position_pct=0.10)
                    
                    signals.append({
                        'symbol': symbol,
                        'action': 'BUY',
                        'shares': shares,
                        'price': price,
                        'value': shares * price,
                        'confidence': confidence,
                        'reasoning': f'ML predicts positive return (confidence: {confidence:.2f})'
                    })
                
                # Sell signal: Held for target days or model predicts negative
                elif symbol in self.positions:
                    days_held = self.entry_dates.get(symbol, 0)
                    if days_held >= self.hold_days or (prediction == 0 and confidence > 0.7):
                        shares = self.positions[symbol]
                        
                        signals.append({
                            'symbol': symbol,
                            'action': 'SELL',
                            'shares': shares,
                            'price': price,
                            'value': shares * price,
                            'confidence': 1.0 if days_held >= self.hold_days else confidence,
                            'reasoning': f'Held {days_held} days' if days_held >= self.hold_days else 'ML predicts reversal'
                        })
            except:
                continue
        
        return signals
    
    def get_description(self) -> str:
        return "Random Forest ML model predicts momentum based on technical features"
