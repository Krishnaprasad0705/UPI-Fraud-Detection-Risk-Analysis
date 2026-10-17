"""
==============================================================================
AI-Driven UPI Fraud Detection System - Complete Implementation
==============================================================================

Features:
1. Real-Time Fraud Risk Scoring Engine (0-100 score)
2. UPI Transaction Pattern Analyzer (Behavioral Learning)
3. Device + SIM + App Fingerprinting Module
4. Rule + ML Hybrid Detection System
5. Fraud Alert & Step-Up Authentication
6. Fraud Case Management Dashboard
7. Continuous Learning + Feedback Loop
8. Blacklist / Whitelist & Reputation System
9. API Integration + Report Generator

Author: AI Fraud Detection Team
Version: 2.0
"""

import numpy as np
import pandas as pd
import random
import time
import json
from datetime import datetime, timedelta
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# SECTION 1: CUSTOMER BEHAVIORAL PROFILE & PATTERN ANALYZER
# ============================================================================

class CustomerBehaviorAnalyzer:
    """
    Learns user transaction patterns: time, location, amount, merchant category
    Detects abnormal behavior based on historical patterns
    """
    
    def __init__(self):
        # Store customer profiles
        self.customer_profiles = defaultdict(lambda: {
            'transaction_count': 0,
            'avg_amount': 0,
            'amounts': [],
            'common_hours': defaultdict(int),
            'common_locations': defaultdict(int),
            'common_merchants': defaultdict(int),
            'common_devices': defaultdict(int),
            'common_payment_methods': defaultdict(int),
            'first_seen': datetime.now(),
            'last_transaction': None,
            'total_amount': 0,
            'fraud_count': 0,
            'legit_count': 0,
            'reputation_score': 100  # Start with perfect reputation
        })
    
    def update_profile(self, customer_id, transaction):
        """Update customer profile with new transaction"""
        profile = self.customer_profiles[customer_id]
        
        # Update transaction count
        profile['transaction_count'] += 1
        
        # Update amount statistics
        amount = transaction['transaction_amount']
        profile['amounts'].append(amount)
        profile['total_amount'] += amount
        profile['avg_amount'] = profile['total_amount'] / profile['transaction_count']
        
        # Update time patterns
        profile['common_hours'][transaction['transaction_hour']] += 1
        
        # Update location patterns
        profile['common_locations'][transaction['location']] += 1
        
        # Update merchant patterns
        profile['common_merchants'][transaction['merchant_category']] += 1
        
        # Update device patterns
        profile['common_devices'][transaction['device_type']] += 1
        
        # Update payment method patterns
        profile['common_payment_methods'][transaction['payment_method']] += 1
        
        # Update last transaction time
        profile['last_transaction'] = transaction['transaction_time']
        
        # Update fraud/legit counts (handle missing is_fraud key)
        is_fraud = transaction.get('is_fraud', 0)
        if is_fraud == 1:
            profile['fraud_count'] += 1
        else:
            profile['legit_count'] += 1
        
        # Update reputation score
        self._update_reputation(customer_id)
    
    def _update_reputation(self, customer_id):
        """Update reputation score based on transaction history"""
        profile = self.customer_profiles[customer_id]
        total = profile['fraud_count'] + profile['legit_count']
        
        if total > 0:
            legit_ratio = profile['legit_count'] / total
            profile['reputation_score'] = max(0, min(100, legit_ratio * 100))
    
    def analyze_behavior(self, customer_id, transaction):
        """
        Analyze if transaction is abnormal for this customer
        Returns behavioral anomaly score (0-100)
        """
        profile = self.customer_profiles[customer_id]
        
        # If new customer, assume normal (will be updated)
        if profile['transaction_count'] < 3:
            return 0
        
        anomaly_score = 0
        
        # Check 1: Unusual Amount
        avg_amount = profile['avg_amount']
        if avg_amount > 0:
            amount_ratio = transaction['transaction_amount'] / avg_amount
            if amount_ratio > 5:  # 5x normal amount
                anomaly_score += 25
            elif amount_ratio > 3:  # 3x normal amount
                anomaly_score += 15
            elif amount_ratio > 2:  # 2x normal amount
                anomaly_score += 5
        
        # Check 2: Unusual Time
        current_hour = transaction['transaction_hour']
        hour_count = profile['common_hours'].get(current_hour, 0)
        if hour_count < profile['transaction_count'] * 0.1:  # Less than 10% of transactions at this hour
            anomaly_score += 15
        
        # Check 3: Unusual Location
        location = transaction['location']
        location_count = profile['common_locations'].get(location, 0)
        if location_count == 0:  # New location
            anomaly_score += 20
        
        # Check 4: New Device
        device = transaction['device_type']
        device_count = profile['common_devices'].get(device, 0)
        if device_count == 0:  # New device
            anomaly_score += 15
        
        # Check 5: Unusual Merchant Category
        merchant = transaction['merchant_category']
        merchant_count = profile['common_merchants'].get(merchant, 0)
        if merchant_count == 0:  # New merchant category
            anomaly_score += 10
        
        # Check 6: Transaction Velocity (rapid transactions)
        if profile['last_transaction']:
            time_diff = (transaction['transaction_time'] - profile['last_transaction']).total_seconds()
            if time_diff < 60:  # Less than 1 minute
                anomaly_score += 10
        
        return min(anomaly_score, 100)
    
    def get_profile(self, customer_id):
        """Get customer profile"""
        return self.customer_profiles[customer_id]
    
    def get_top_locations(self, customer_id, n=3):
        """Get top N common locations for customer"""
        profile = self.customer_profiles[customer_id]
        locations = profile['common_locations']
        return sorted(locations.items(), key=lambda x: x[1], reverse=True)[:n]


# ============================================================================
# SECTION 2: DEVICE & FINGERPRINTING MODULE
# ============================================================================

class DeviceFingerprinter:
    """
    Detects fraud using new device, SIM swap, emulator/rooted phone,
    unusual IP/device change
    """
    
    # Simulated device fingerprint database
    def __init__(self):
        self.device_database = defaultdict(lambda: {
            'first_seen': None,
            'last_seen': None,
            'login_count': 0,
            'fraud_count': 0,
            'is_verified': False,
            'is_rooted': False,
            'is_emulator': False,
            'sim_swap_detected': False,
            'ip_addresses': set(),
            'locations': set()
        })
        
        # Risk weights
        self.risk_weights = {
            'new_device': 15,
            'unverified_device': 10,
            'rooted_phone': 25,
            'emulator': 30,
            'sim_swap': 35,
            'new_ip_location': 12,
            'multiple_ips': 8
        }
    
    def analyze_device(self, customer_id, device_info):
        """
        Analyze device for fraud indicators
        Returns device risk score (0-100)
        """
        device_id = f"{customer_id}_{device_info.get('device_id', 'unknown')}"
        device_record = self.device_database[device_id]
        
        risk_score = 0
        
        # Check if new device
        if device_record['first_seen'] is None:
            device_record['first_seen'] = datetime.now()
            risk_score += self.risk_weights['new_device']
        
        # Check device verification status
        if not device_record['is_verified']:
            risk_score += self.risk_weights['unverified_device']
        
        # Check for rooted phone
        if device_info.get('is_rooted', False):
            risk_score += self.risk_weights['rooted_phone']
            device_record['is_rooted'] = True
        
        # Check for emulator
        if device_info.get('is_emulator', False):
            risk_score += self.risk_weights['emulator']
            device_record['is_emulator'] = True
        
        # Check for SIM swap
        if device_info.get('sim_swap_detected', False):
            risk_score += self.risk_weights['sim_swap']
            device_record['sim_swap_detected'] = True
        
        # Check IP/Location consistency
        ip_address = device_info.get('ip_address', '')
        location = device_info.get('location', '')
        
        if ip_address and ip_address not in device_record['ip_addresses']:
            if len(device_record['ip_addresses']) > 0:
                risk_score += self.risk_weights['new_ip_location']
            device_record['ip_addresses'].add(ip_address)
        
        if location and location not in device_record['locations']:
            device_record['locations'].add(location)
        
        if len(device_record['ip_addresses']) > 3:
            risk_score += self.risk_weights['multiple_ips']
        
        # Update device record
        device_record['last_seen'] = datetime.now()
        device_record['login_count'] += 1
        
        return min(risk_score, 100)
    
    def verify_device(self, customer_id, device_id):
        """Mark device as verified"""
        device_key = f"{customer_id}_{device_id}"
        self.device_database[device_key]['is_verified'] = True
    
    def flag_fraud_device(self, customer_id, device_id):
        """Flag device as associated with fraud"""
        device_key = f"{customer_id}_{device_id}"
        self.device_database[device_key]['fraud_count'] += 1


# ============================================================================
# SECTION 3: BLACKLIST / WHITELIST & REPUTATION SYSTEM
# ============================================================================

class ReputationManager:
    """
    Maintains reputation score for UPI IDs, devices, accounts, merchants
    Blocks repeat offenders
    """
    
    def __init__(self):
        # Blacklists
        self.blacklist = {
            'customer_ids': set(),
            'devices': set(),
            'ip_addresses': set(),
            'accounts': set(),
            'merchants': set()
        }
        
        # Whitelists
        self.whitelist = {
            'customer_ids': set(),
            'devices': set(),
            'merchants': set()
        }
        
        # Reputation scores (0-100)
        self.reputation_scores = defaultdict(lambda: 100)
        
        # Risk thresholds
        self.blacklist_threshold = 10  # Score below this gets blacklisted
        self.whitelist_threshold = 95  # Score above this gets whitelisted
    
    def check_blacklist(self, entity_type, entity_id):
        """Check if entity is blacklisted"""
        if entity_type in self.blacklist:
            return entity_id in self.blacklist[entity_type]
        return False
    
    def check_whitelist(self, entity_type, entity_id):
        """Check if entity is whitelisted"""
        if entity_type in self.whitelist:
            return entity_id in self.whitelist[entity_type]
        return False
    
    def add_to_blacklist(self, entity_type, entity_id, reason=""):
        """Add entity to blacklist"""
        if entity_type in self.blacklist:
            self.blacklist[entity_type].add(entity_id)
            print(f"ðŸš« BLACKLISTED: {entity_type} {entity_id} - Reason: {reason}")
    
    def add_to_whitelist(self, entity_type, entity_id):
        """Add entity to whitelist"""
        if entity_type in self.whitelist:
            self.whitelist[entity_type].add(entity_id)
            print(f"âœ… WHITELISTED: {entity_type} {entity_id}")
    
    def update_reputation(self, entity_type, entity_id, is_fraud, amount=0):
        """Update reputation score based on transaction outcome"""
        key = f"{entity_type}_{entity_id}"
        current_score = self.reputation_scores[key]
        
        if is_fraud:
            # Decrease score based on fraud severity
            fraud_penalty = min(30, 10 + (amount / 1000))  # Higher amount = higher penalty
            new_score = max(0, current_score - fraud_penalty)
        else:
            # Gradually increase for legitimate transactions
            new_score = min(100, current_score + 0.5)
        
        self.reputation_scores[key] = new_score
        
        # Auto blacklist if score too low
        if new_score < self.blacklist_threshold:
            self.add_to_blacklist(entity_type, entity_id, f"Low reputation: {new_score}")
        
        # Auto whitelist if score very high
        elif new_score > self.whitelist_threshold:
            if not self.check_whitelist(entity_type, entity_id):
                self.add_to_whitelist(entity_type, entity_id)
        
        return new_score
    
    def get_reputation(self, entity_type, entity_id):
        """Get reputation score for entity"""
        key = f"{entity_type}_{entity_id}"
        return self.reputation_scores[key]
    
    def get_blacklist_stats(self):
        """Get blacklist statistics"""
        return {
            'customer_ids': len(self.blacklist['customer_ids']),
            'devices': len(self.blacklist['devices']),
            'ip_addresses': len(self.blacklist['ip_addresses']),
            'accounts': len(self.blacklist['accounts']),
            'merchants': len(self.blacklist['merchants'])
        }


# ============================================================================
# SECTION 4: RULE-BASED FRAUD DETECTION ENGINE
# ============================================================================

class RuleBasedDetector:
    """
    Rule-based fraud detection with weighted rules
    """
    
    def __init__(self):
        # Define fraud detection rules with weights
        self.rules = {
            'high_amount': {
                'threshold': 15000,
                'weight': 4,
                'description': 'Transaction amount > INR 15,000'
            },
            'very_high_amount': {
                'threshold': 50000,
                'weight': 8,
                'description': 'Transaction amount > INR 50,000'
            },
            'unusual_time': {
                'threshold': 4,  # Hour < 4
                'weight': 2,
                'description': 'Transaction between midnight and 4 AM'
            },
            'very_unusual_time': {
                'threshold': 2,  # Hour < 2
                'weight': 4,
                'description': 'Transaction between midnight and 2 AM'
            },
            'foreign_transaction': {
                'threshold': 1,
                'weight': 3,
                'description': 'Foreign transaction'
            },
            'web_device': {
                'weight': 1,
                'description': 'Web browser transaction'
            },
            'failed_logins': {
                'threshold': 3,
                'weight': 2,
                'description': 'Multiple failed login attempts'
            },
            'many_failed_logins': {
                'threshold': 5,
                'weight': 4,
                'description': 'Many failed login attempts'
            },
            'new_account': {
                'threshold': 1,  # Account tenure < 1 year
                'weight': 3,
                'description': 'New account (< 1 year)'
            },
            'very_new_account': {
                'threshold': 0,  # Account tenure < 1 month (approx)
                'weight': 5,
                'description': 'Very new account (< 1 month)'
            },
            'insufficient_balance': {
                'weight': 2,
                'description': 'Insufficient account balance'
            },
            'high_risk_merchant': {
                'merchants': ['Electronics', 'Travel', 'Jewelry'],
                'weight': 2,
                'description': 'High-risk merchant category'
            },
            'rapid_transactions': {
                'threshold': 5,  # Transactions per minute
                'weight': 3,
                'description': 'Rapid-fire transactions'
            }
        }
    
    def apply_rules(self, transaction, velocity_info=None):
        """
        Apply all rules and calculate risk score
        Returns: (risk_score, triggered_rules)
        """
        base_probability = 2  # Base fraud rate
        risk_score = base_probability
        triggered_rules = []
        
        amount = transaction['transaction_amount']
        hour = transaction['transaction_hour']
        device = transaction['device_type']
        is_foreign = transaction['is_foreign_transaction']
        failed_logins = transaction['failed_login_attempts']
        tenure = transaction['account_tenure_years']
        balance = transaction['account_balance']
        merchant = transaction['merchant_category']
        
        # Rule 1: High Amount
        if amount > self.rules['very_high_amount']['threshold']:
            risk_score += self.rules['very_high_amount']['weight']
            triggered_rules.append(self.rules['very_high_amount']['description'])
        elif amount > self.rules['high_amount']['threshold']:
            risk_score += self.rules['high_amount']['weight']
            triggered_rules.append(self.rules['high_amount']['description'])
        
        # Rule 2: Unusual Time
        if hour < self.rules['very_unusual_time']['threshold']:
            risk_score += self.rules['very_unusual_time']['weight']
            triggered_rules.append(self.rules['very_unusual_time']['description'])
        elif hour < self.rules['unusual_time']['threshold']:
            risk_score += self.rules['unusual_time']['weight']
            triggered_rules.append(self.rules['unusual_time']['description'])
        
        # Rule 3: Foreign Transaction
        if is_foreign == 1:
            risk_score += self.rules['foreign_transaction']['weight']
            triggered_rules.append(self.rules['foreign_transaction']['description'])
        
        # Rule 4: Web Device
        if device in ['Web', 'Desktop']:
            risk_score += self.rules['web_device']['weight']
            triggered_rules.append(self.rules['web_device']['description'])
        
        # Rule 5: Failed Logins
        if failed_logins >= self.rules['many_failed_logins']['threshold']:
            risk_score += self.rules['many_failed_logins']['weight']
            triggered_rules.append(self.rules['many_failed_logins']['description'])
        elif failed_logins >= self.rules['failed_logins']['threshold']:
            risk_score += self.rules['failed_logins']['weight']
            triggered_rules.append(self.rules['failed_logins']['description'])
        
        # Rule 6: Account Tenure
        if tenure < self.rules['very_new_account']['threshold']:
            risk_score += self.rules['very_new_account']['weight']
            triggered_rules.append(self.rules['very_new_account']['description'])
        elif tenure < self.rules['new_account']['threshold']:
            risk_score += self.rules['new_account']['weight']
            triggered_rules.append(self.rules['new_account']['description'])
        
        # Rule 7: Insufficient Balance
        if balance < amount:
            risk_score += self.rules['insufficient_balance']['weight']
            triggered_rules.append(self.rules['insufficient_balance']['description'])
        
        # Rule 8: High Risk Merchant
        if merchant in self.rules['high_risk_merchant']['merchants']:
            risk_score += self.rules['high_risk_merchant']['weight']
            triggered_rules.append(self.rules['high_risk_merchant']['description'])
        
        # Rule 9: Rapid Transactions
        if velocity_info and velocity_info.get('transactions_per_minute', 0) > self.rules['rapid_transactions']['threshold']:
            risk_score += self.rules['rapid_transactions']['weight']
            triggered_rules.append(self.rules['rapid_transactions']['description'])
        
        # Cap at 100
        risk_score = min(risk_score, 100)
        
        return risk_score, triggered_rules


# ============================================================================
# SECTION 5: DEEP-LEARNING FRAUD DETECTION MODEL
# ============================================================================

class DeepLearningFraudDetector:
    """CPU-friendly neural classifier for imbalanced tabular fraud data."""

    def __init__(self):
        self.model = None
        self.scaler = None
        self.is_trained = False
        self.device = 'cpu'
        self.feature_names = [
            'transaction_amount', 'transaction_hour', 'is_foreign_transaction',
            'failed_login_attempts', 'account_tenure_years', 'device_risk',
            'behavioral_anomaly', 'velocity_score', 'reputation_score'
        ]

    def _build_model(self, input_size):
        import torch.nn as nn
        return nn.Sequential(
            nn.Linear(input_size, 64), nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.25),
            nn.Linear(64, 32), nn.BatchNorm1d(32), nn.ReLU(), nn.Dropout(0.15),
            nn.Linear(32, 1)
        )

    def train_model(self, training_data, epochs=80, batch_size=256, learning_rate=1e-3):
        """Train an MLP using class-weighted loss and validation early stopping."""
        try:
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import StandardScaler
            import torch
            from torch.utils.data import DataLoader, TensorDataset

            X = training_data[self.feature_names].fillna(0)
            y = training_data['is_fraud'].astype(int)
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)

            torch.manual_seed(42)
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            self.model = self._build_model(len(self.feature_names)).to(self.device)
            train_data = TensorDataset(
                torch.tensor(X_train_scaled, dtype=torch.float32),
                torch.tensor(y_train.to_numpy(), dtype=torch.float32).unsqueeze(1)
            )
            loader = DataLoader(train_data, batch_size=batch_size, shuffle=True)
            fraud_count = max(int(y_train.sum()), 1)
            safe_count = max(len(y_train) - fraud_count, 1)
            loss_fn = torch.nn.BCEWithLogitsLoss(
                pos_weight=torch.tensor([safe_count / fraud_count], dtype=torch.float32, device=self.device)
            )
            optimizer = torch.optim.AdamW(self.model.parameters(), lr=learning_rate, weight_decay=1e-4)
            X_val = torch.tensor(X_test_scaled, dtype=torch.float32, device=self.device)
            y_val = torch.tensor(y_test.to_numpy(), dtype=torch.float32, device=self.device).unsqueeze(1)

            best_state, best_loss, stale_epochs = None, float('inf'), 0
            for _ in range(epochs):
                self.model.train()
                for batch_x, batch_y in loader:
                    optimizer.zero_grad()
                    loss = loss_fn(self.model(batch_x.to(self.device)), batch_y.to(self.device))
                    loss.backward()
                    optimizer.step()
                self.model.eval()
                with torch.no_grad():
                    validation_loss = loss_fn(self.model(X_val), y_val).item()
                if validation_loss < best_loss - 1e-4:
                    best_loss = validation_loss
                    best_state = {name: value.detach().cpu().clone() for name, value in self.model.state_dict().items()}
                    stale_epochs = 0
                else:
                    stale_epochs += 1
                    if stale_epochs >= 10:
                        break

            self.model.load_state_dict(best_state)
            self.model.eval()
            with torch.no_grad():
                probabilities = torch.sigmoid(self.model(X_val)).cpu().numpy().ravel()
            accuracy = ((probabilities >= 0.5) == y_test.to_numpy()).mean()
            self.is_trained = True
            print(f"Deep-learning model trained successfully on {self.device}! Accuracy: {accuracy:.2%}")
            return accuracy
        except ImportError:
            print("PyTorch or scikit-learn is not installed; using rule-based scoring only.")
            return None

    def predict(self, features):
        """Return (fraud_probability_percent, binary_prediction)."""
        if not self.is_trained or self.model is None:
            return None, None
        try:
            import torch
            vector = [[features.get(name, 0) for name in self.feature_names]]
            scaled = self.scaler.transform(vector)
            self.model.eval()
            with torch.no_grad():
                probability = torch.sigmoid(
                    self.model(torch.tensor(scaled, dtype=torch.float32, device=self.device))
                ).item() * 100
            return probability, int(probability >= 50)
        except Exception as error:
            print(f"Deep-learning prediction error: {error}")
            return None, None

    def explain(self, features, top_k=5):
        """Return feature contributions using SHAP when installed, with a
        deterministic gradient*input fallback for lightweight deployments."""
        values = {name: float(features.get(name, 0) or 0) for name in self.feature_names}
        if not self.is_trained or self.model is None:
            return {'method': 'unavailable', 'contributions': []}
        try:
            import torch
            scaled = self.scaler.transform([[values[name] for name in self.feature_names]])
            tensor = torch.tensor(scaled, dtype=torch.float32, device=self.device, requires_grad=True)
            self.model.eval()
            output = self.model(tensor)
            self.model.zero_grad()
            output.backward()
            contributions = (tensor.grad * tensor).detach().cpu().numpy().ravel()
            method = 'gradient_input'
            try:
                import shap
                background = torch.zeros((1, len(self.feature_names)), dtype=torch.float32, device=self.device)
                shap_values = shap.GradientExplainer(self.model, background).shap_values(tensor)
                if isinstance(shap_values, list):
                    shap_values = shap_values[0]
                contributions = np.asarray(shap_values).reshape(-1)[:len(self.feature_names)]
                method = 'SHAP GradientExplainer'
            except ImportError:
                pass
            ranked = sorted(zip(self.feature_names, contributions), key=lambda item: abs(item[1]), reverse=True)
            return {'method': method, 'contributions': [
                {'feature': name, 'impact': round(float(value), 6),
                 'direction': 'fraud' if value > 0 else 'safe'}
                for name, value in ranked[:top_k]
            ]}
        except Exception as error:
            return {'method': 'unavailable', 'contributions': [], 'error': str(error)}

    def save_model(self, model_path):
        """Persist weights and normalisation parameters for production inference."""
        if not self.is_trained or self.model is None:
            raise RuntimeError('Train the model before saving it.')
        import torch
        from pathlib import Path
        destination = Path(model_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'feature_names': self.feature_names,
            'scaler_mean': torch.tensor(self.scaler.mean_),
            'scaler_scale': torch.tensor(self.scaler.scale_)
        }, destination)

    def load_model(self, model_path):
        """Load a saved neural model without retraining."""
        import torch
        from sklearn.preprocessing import StandardScaler
        checkpoint = torch.load(model_path, map_location='cpu', weights_only=True)
        if checkpoint.get('feature_names') != self.feature_names:
            raise ValueError('Model features do not match this detector version.')
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = self._build_model(len(self.feature_names)).to(self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        self.scaler = StandardScaler()
        self.scaler.mean_ = checkpoint['scaler_mean'].numpy()
        self.scaler.scale_ = checkpoint['scaler_scale'].numpy()
        self.scaler.var_ = self.scaler.scale_ ** 2
        self.scaler.n_features_in_ = len(self.feature_names)
        self.is_trained = True


# Backwards-compatible name used by the current API.
MLFraudDetector = DeepLearningFraudDetector

# ============================================================================
# SECTION 6: HYBRID FRAUD DETECTION ENGINE
# ============================================================================

class HybridFraudDetector:
    """
    Combines Rule-based + ML + Behavioral Analysis for better accuracy
    """
    
    # Risk thresholds
    SAFE_THRESHOLD = 30
    REVIEW_THRESHOLD = 70
    
    def __init__(self):
        # Initialize all detectors
        self.rule_detector = RuleBasedDetector()
        self.ml_detector = MLFraudDetector()
        self.behavior_analyzer = CustomerBehaviorAnalyzer()
        self.device_fingerprinter = DeviceFingerprinter()
        self.reputation_manager = ReputationManager()
        
        # Weights for hybrid scoring
        self.weights = {
            'rule_based': 0.35,
            'ml': 0.30,
            'behavioral': 0.20,
            'device': 0.10,
            'reputation': 0.05
        }
        
        # Track transaction velocity
        self.transaction_history = defaultdict(list)
    
    def calculate_velocity(self, customer_id, current_time):
        """Calculate transaction velocity for customer"""
        # Get recent transactions (last 10 minutes)
        cutoff_time = current_time - timedelta(minutes=10)
        recent_txns = [
            t for t in self.transaction_history[customer_id]
            if t > cutoff_time
        ]
        
        # Calculate rate
        if len(recent_txns) > 0:
            time_span = (current_time - recent_txns[0]).total_seconds() / 60
            if time_span > 0:
                transactions_per_minute = len(recent_txns) / time_span
            else:
                transactions_per_minute = 0
        else:
            transactions_per_minute = 0
        
        # Update history
        self.transaction_history[customer_id].append(current_time)
        
        return {
            'recent_count': len(recent_txns),
            'transactions_per_minute': transactions_per_minute
        }
    
    def analyze_transaction(self, transaction, use_ml=False):
        """
        Comprehensive transaction analysis
        Returns detailed risk assessment
        """
        customer_id = transaction['customer_id']
        current_time = transaction['transaction_time']
        
        # Step 1: Calculate velocity
        velocity_info = self.calculate_velocity(customer_id, current_time)
        
        # Step 2: Rule-based detection
        rule_score, triggered_rules = self.rule_detector.apply_rules(
            transaction, velocity_info
        )
        
        # Step 3: Behavioral analysis
        behavioral_score = self.behavior_analyzer.analyze_behavior(
            customer_id, transaction
        )
        
        # Step 4: Update customer profile
        self.behavior_analyzer.update_profile(customer_id, transaction)
        
        # Step 5: Device fingerprinting (simulated)
        device_info = {
            'device_id': transaction.get('device_id', 'unknown'),
            'device_type': transaction['device_type'],
            'ip_address': transaction.get('ip_address', ''),
            'location': transaction['location'],
            'is_rooted': random.random() < 0.05,  # 5% chance of rooted
            'is_emulator': random.random() < 0.03,  # 3% chance of emulator
            'sim_swap_detected': transaction.get('failed_login_attempts', 0) >= 3
        }
        device_score = self.device_fingerprinter.analyze_device(
            customer_id, device_info
        )
        
        # Step 6: Check reputation
        reputation = self.reputation_manager.get_reputation(
            'customer_id', customer_id
        )
        reputation_risk = 100 - reputation  # Lower reputation = higher risk
        
        # Step 7: Check blacklists
        is_blacklisted = self.reputation_manager.check_blacklist(
            'customer_ids', customer_id
        )
        
        # Step 8: ML Prediction (if enabled and trained)
        ml_score = None
        ml_probability = None
        explanation = {'method': 'unavailable', 'contributions': []}
        if use_ml and self.ml_detector.is_trained:
            ml_features = {
                'transaction_amount': transaction['transaction_amount'],
                'transaction_hour': transaction['transaction_hour'],
                'is_foreign_transaction': transaction['is_foreign_transaction'],
                'failed_login_attempts': transaction['failed_login_attempts'],
                'account_tenure_years': transaction['account_tenure_years'],
                'device_risk': device_score,
                'behavioral_anomaly': behavioral_score,
                'velocity_score': velocity_info['transactions_per_minute'] * 10,
                'reputation_score': reputation
            }
            ml_score, _ = self.ml_detector.predict(ml_features)
            ml_probability = ml_score
            explanation = self.ml_detector.explain(ml_features)
        
        # Step 9: Calculate hybrid score
        scores = {
            'rule_based': rule_score,
            'ml': ml_score if ml_score else rule_score,
            'behavioral': behavioral_score,
            'device': device_score,
            'reputation': reputation_risk
        }
        
        # Weighted average
        final_score = 0
        for key, weight in self.weights.items():
            final_score += scores.get(key, 0) * weight
        
        # Apply blacklist penalty
        if is_blacklisted:
            final_score = 100
        
        final_score = min(final_score, 100)
        
        # Step 10: Classification
        if final_score > self.REVIEW_THRESHOLD:
            classification = "BLOCK"
            action = "Decline transaction"
        elif final_score > self.SAFE_THRESHOLD:
            classification = "REVIEW"
            action = "Require additional verification"
        else:
            classification = "APPROVE"
            action = "Process normally"
        
        # Update reputation
        self.reputation_manager.update_reputation(
            'customer_id', customer_id,
            transaction.get('is_fraud', 0),
            transaction['transaction_amount']
        )
        
        return {
            'customer_id': customer_id,
            'transaction_amount': transaction['transaction_amount'],
            'risk_score': round(final_score, 2),
            'classification': classification,
            'action': action,
            'scores': {k: round(v, 2) if v else None for k, v in scores.items()},
            'triggered_rules': triggered_rules,
            'behavioral_anomaly': behavioral_score,
            'device_risk': device_score,
            'reputation_score': reputation,
            'velocity': velocity_info,
            'is_blacklisted': is_blacklisted
            , 'fraud_probability': round(float(ml_probability), 2) if ml_probability is not None else None
            , 'confidence': round(abs((ml_probability if ml_probability is not None else final_score) - 50) * 2, 2)
            , 'explanation': explanation
        }


# ============================================================================
# SECTION 7: FRAUD ALERT & NOTIFICATION SYSTEM
# ============================================================================

class FraudAlertSystem:
    """
    Manages fraud alerts and step-up authentication
    """
    
    def __init__(self):
        self.alerts = []
        self.pending_verifications = {}
        
    def create_alert(self, transaction_result, transaction):
        """Create fraud alert for high-risk transaction"""
        if transaction_result['classification'] in ['BLOCK', 'REVIEW']:
            alert = {
                'alert_id': len(self.alerts) + 1,
                'timestamp': datetime.now(),
                'customer_id': transaction_result['customer_id'],
                'transaction_amount': transaction['transaction_amount'],
                'risk_score': transaction_result['risk_score'],
                'classification': transaction_result['classification'],
                'triggered_rules': transaction_result.get('triggered_rules', []),
                'status': 'PENDING'
            }
            self.alerts.append(alert)
            return alert
        return None
    
    def request_step_up_auth(self, customer_id, reason):
        """Request additional verification"""
        verification_id = f"VER-{random.randint(10000, 99999)}"
        self.pending_verifications[customer_id] = {
            'verification_id': verification_id,
            'reason': reason,
            'requested_at': datetime.now(),
            'status': 'PENDING',
            'attempts': 0
        }
        return verification_id
    
    def verify_otp(self, customer_id, otp):
        """Verify OTP (simulated)"""
        if customer_id in self.pending_verifications:
            # Simulate OTP verification (in real system, compare with sent OTP)
            self.pending_verifications[customer_id]['status'] = 'VERIFIED'
            self.pending_verifications[customer_id]['attempts'] += 1
            return True
        return False
    
    def get_alerts(self, status=None):
        """Get alerts, optionally filtered by status"""
        if status:
            return [a for a in self.alerts if a['status'] == status]
        return self.alerts


# ============================================================================
# SECTION 8: REPORT GENERATOR
# ============================================================================

class ReportGenerator:
    """
    Generates fraud analytics reports
    """
    
    def __init__(self, transactions_db=None):
        self.transactions_db = transactions_db
    
    def generate_daily_report(self, date=None):
        """Generate daily fraud report"""
        if date is None:
            date = datetime.now().date()
        
        report = {
            'report_date': str(date),
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_transactions': 0,
                'total_frauds': 0,
                'fraud_rate': 0,
                'total_amount': 0,
                'fraud_amount': 0,
                'blocked_amount': 0
            },
            'breakdown': {
                'by_device': {},
                'by_location': {},
                'by_merchant': {},
                'by_hour': {},
                'by_payment_method': {}
            },
            'top_risk_customers': [],
            'recommendations': []
        }
        
        return report
    
    def generate_weekly_report(self):
        """Generate weekly fraud report"""
        report = {
            'report_period': 'Last 7 days',
            'generated_at': datetime.now().isoformat(),
            'trends': {
                'fraud_rate_change': 0,
                'total_transactions_change': 0,
                'blocked_transactions_change': 0
            },
            'summary': {},
            'insights': []
        }
        
        return report
    
    def export_to_json(self, report, filename):
        """Export report to JSON file"""
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"âœ“ Report exported to {filename}")
    
    def export_to_csv(self, data, filename):
        """Export data to CSV file"""
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        print(f"âœ“ Data exported to {filename}")


# ============================================================================
# SECTION 9: API ENDPOINTS (Flask)
# ============================================================================

class FraudDetectionAPI:
    """
    REST API for fraud detection integration
    """
    
    def __init__(self, detector):
        self.detector = detector
        self.app = None
        
    def create_app(self):
        """Create Flask application"""
        try:
            from flask import Flask, request, jsonify
            
            app = Flask(__name__)
            
            @app.route('/health', methods=['GET'])
            def health_check():
                return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})
            
            @app.route('/analyze', methods=['POST'])
            def analyze_transaction():
                """Analyze a single transaction"""
                data = request.get_json()
                
                # Add timestamp if not provided
                if 'transaction_time' not in data:
                    data['transaction_time'] = datetime.now()
                
                result = self.detector.analyze_transaction(data)
                return jsonify(result)
            
            @app.route('/batch_analyze', methods=['POST'])
            def batch_analyze():
                """Analyze multiple transactions"""
                data = request.get_json()
                transactions = data.get('transactions', [])
                
                results = []
                for txn in transactions:
                    if 'transaction_time' not in txn:
                        txn['transaction_time'] = datetime.now()
                    result = self.detector.analyze_transaction(txn)
                    results.append(result)
                
                return jsonify({'results': results, 'count': len(results)})
            
            @app.route('/customer/<customer_id>/profile', methods=['GET'])
            def get_customer_profile(customer_id):
                """Get customer behavior profile"""
                profile = self.detector.behavior_analyzer.get_profile(customer_id)
                return jsonify({'customer_id': customer_id, 'profile': dict(profile)})
            
            @app.route('/customer/<customer_id>/reputation', methods=['GET'])
            def get_customer_reputation(customer_id):
                """Get customer reputation score"""
                reputation = self.detector.reputation_manager.get_reputation(
                    'customer_id', customer_id
                )
                return jsonify({'customer_id': customer_id, 'reputation_score': reputation})
            
            @app.route('/blacklist/<entity_type>/<entity_id>', methods=['POST'])
            def add_to_blacklist(entity_type, entity_id):
                """Add entity to blacklist"""
                reason = request.get_json().get('reason', 'Manual blacklist')
                self.detector.reputation_manager.add_to_blacklist(
                    entity_type, entity_id, reason
                )
                return jsonify({'status': 'success', 'message': f'{entity_type} {entity_id} blacklisted'})
            
            @app.route('/whitelist/<entity_type>/<entity_id>', methods=['POST'])
            def add_to_whitelist(entity_type, entity_id):
                """Add entity to whitelist"""
                self.detector.reputation_manager.add_to_whitelist(
                    entity_type, entity_id
                )
                return jsonify({'status': 'success', 'message': f'{entity_type} {entity_id} whitelisted'})
            
            @app.route('/reports/daily', methods=['GET'])
            def get_daily_report():
                """Get daily fraud report"""
                report_gen = ReportGenerator()
                report = report_gen.generate_daily_report()
                return jsonify(report)
            
            @app.route('/statistics', methods=['GET'])
            def get_statistics():
                """Get system statistics"""
                stats = {
                    'active_customers': len(self.detector.behavior_analyzer.customer_profiles),
                    'blacklist_stats': self.detector.reputation_manager.get_blacklist_stats(),
                    'ml_model_trained': self.detector.ml_detector.is_trained
                }
                return jsonify(stats)
            
            self.app = app
            print("âœ“ Flask API created successfully")
            return app
            
        except ImportError:
            print("âš  Flask not available. Install flask to use API.")
            return None
    
    def run(self, host='0.0.0.0', port=5000):
        """Run the API server"""
        if self.app:
            print(f"\n{'='*60}")
            print(f"ðŸš€ Starting Fraud Detection API on http://{host}:{port}")
            print(f"{'='*60}")
            self.app.run(host=host, port=port, debug=True)
        else:
            print("âŒ No Flask app available")


# ============================================================================
# SECTION 10: MAIN EXECUTION
# ============================================================================

def run_fraud_detection_demo():
    """
    Run a complete demonstration of the fraud detection system
    """
    print("\n" + "="*80)
    print("ðŸ”’ AI-DRIVEN UPI FRAUD DETECTION SYSTEM - DEMONSTRATION")
    print("="*80)
    
    # Initialize the hybrid detector
    detector = HybridFraudDetector()
    
    # Initialize alert system
    alert_system = FraudAlertSystem()
    
    # Initialize report generator
    report_gen = ReportGenerator()
    
    # Generate sample transactions for testing
    print("\nðŸ“Š Generating sample transactions...")
    
    sample_transactions = []
    for i in range(20):
        txn = {
            'customer_id': f"C{random.randint(1000, 1050)}",
            'user_id': random.randint(1, 100),
            'transaction_amount': round(random.uniform(100, 100000), 2),
            'transaction_hour': random.randint(0, 23),
            'transaction_type': random.choice(['Debit', 'Credit']),
            'payment_method': random.choice(['Card', 'NetBanking', 'UPI', 'Wallet']),
            'merchant_category': random.choice(['Electronics', 'Grocery', 'Travel', 'Restaurant', 'Healthcare']),
            'device_type': random.choice(['Android', 'iOS', 'Web', 'Mobile']),
            'location': random.choice(['Chennai', 'Mumbai', 'Delhi', 'Hyderabad', 'Bangalore']),
            'account_balance': round(random.uniform(5000, 500000), 2),
            'is_foreign_transaction': random.choice([0, 1]),
            'failed_login_attempts': random.randint(0, 5),
            'account_tenure_years': random.randint(0, 20),
            'transaction_time': datetime.now()
        }
        sample_transactions.append(txn)
    
    print(f"âœ“ Generated {len(sample_transactions)} sample transactions\n")
    
    # Analyze each transaction
    print("-"*80)
    print("ðŸ” TRANSACTION ANALYSIS RESULTS")
    print("-"*80)
    
    fraud_count = 0
    block_count = 0
    review_count = 0
    
    for i, txn in enumerate(sample_transactions):
        result = detector.analyze_transaction(txn)
        
        # Create alert if needed
        alert = alert_system.create_alert(result, txn)
        
        # Display result
        status_icon = {
            'APPROVE': 'âœ…',
            'REVIEW': 'âš ï¸',
            'BLOCK': 'ðŸš«'
        }.get(result['classification'], 'â“')
        
        print(f"\n[Transaction {i+1}] {status_icon} {result['classification']}")
        print(f"   Customer: {result['customer_id']} | Amount: â‚¹{txn['transaction_amount']:,.2f}")
        print(f"   Risk Score: {result['risk_score']}%")
        print(f"   Action: {result['action']}")
        
        if result['triggered_rules']:
            print(f"   Rules Triggered: {', '.join(result['triggered_rules'][:3])}")
        
        if result['classification'] == 'BLOCK':
            block_count += 1
            fraud_count += 1
        elif result['classification'] == 'REVIEW':
            review_count += 1
    
    # Print summary
    print("\n" + "="*80)
    print("ðŸ“ˆ FRAUD DETECTION SUMMARY")
    print("="*80)
    print(f"Total Transactions Analyzed: {len(sample_transactions)}")
    print(f"âœ… Approved (Safe): {len(sample_transactions) - fraud_count}")
    print(f"âš ï¸  Review Required: {review_count}")
    print(f"ðŸš« Blocked (Fraud): {block_count}")
    print(f"ðŸ“Š Fraud Rate: {(fraud_count/len(sample_transactions))*100:.1f}%")
    
    # Show customer profiles
    print("\n" + "="*80)
    print("ðŸ‘¤ SAMPLE CUSTOMER BEHAVIORAL PROFILES")
    print("="*80)
    
    sample_customer = list(detector.behavior_analyzer.customer_profiles.keys())[:3]
    for cid in sample_customer:
        profile = detector.behavior_analyzer.get_profile(cid)
        print(f"\nCustomer: {cid}")
        print(f"   Transactions: {profile['transaction_count']}")
        print(f"   Avg Amount: â‚¹{profile['avg_amount']:,.2f}")
        print(f"   Reputation Score: {profile['reputation_score']:.1f}")
        print(f"   Fraud Count: {profile['fraud_count']}")
        print(f"   Legitimate Count: {profile['legit_count']}")
    
    # Show blacklist stats
    print("\n" + "="*80)
    print("ðŸš« BLACKLIST STATISTICS")
    print("="*80)
    blacklist_stats = detector.reputation_manager.get_blacklist_stats()
    for entity_type, count in blacklist_stats.items():
        print(f"   {entity_type}: {count}")
    
    # Generate report
    print("\n" + "="*80)
    print("ðŸ“„ GENERATING FRAUD REPORT")
    print("="*80)
    report = report_gen.generate_daily_report()
    print(f"âœ“ Daily report generated for {report['report_date']}")
    
    print("\n" + "="*80)
    print("âœ… DEMONSTRATION COMPLETE")
    print("="*80)
    print("\nðŸš€ To start the API server, call: api = FraudDetectionAPI(detector); api.run()")
    
    return detector, alert_system, report_gen


# Run the demo
if __name__ == "__main__":
    detector, alert_system, report_gen = run_fraud_detection_demo()

