import os
"""
==============================================================================
SIMPLE UPI TRANSACTION STREAMING SCRIPT
==============================================================================

Run: python start_streaming.py

This script generates 1000+ transactions per minute with AI fraud detection
and stores them in MySQL database.

Press CTRL+C to stop
"""

import pandas as pd
import numpy as np
import random
import time
import threading
from datetime import datetime
from collections import defaultdict
from sqlalchemy import create_engine, text
from urllib.parse import quote
import warnings
warnings.filterwarnings('ignore')
from fraud_detection_system import HybridFraudDetector
from email_alerts import SevereRiskEmailAlert, _load_project_dotenv
_load_project_dotenv()

# ============================================================================
# CONFIGURATION - Modify these values
# ============================================================================

# Database Configuration
DB_CONFIG = {
    'username': 'root',
    'password': os.getenv('UPI_DB_PASSWORD', 'Password'), 
    'host': 'localhost',
    'database': 'upi_fraud_db'
}

# Streaming Configuration
TRANSACTIONS_PER_SECOND = 20  # 20 x 60 = 1200 per minute
BATCH_SIZE = 50  # Transactions per database batch

print("\n" + "="*70)
print("🚀 UPI TRANSACTION STREAMING SYSTEM")
print("="*70)
print(f"📊 Target: {TRANSACTIONS_PER_SECOND} transactions/second")
print(f"📦 Batch size: {BATCH_SIZE}")
print("🧠 AI Fraud Detection: ACTIVE")
print("💾 Database: MySQL")
print("\n⚠️  Press CTRL+C to stop")
print("="*70 + "\n")

# ============================================================================
# STEP 1: Setup Database
# ============================================================================

try:
    # Create database
    temp_engine = create_engine(f"mysql+pymysql://{DB_CONFIG['username']}:{quote(DB_CONFIG['password'], safe='')}@{DB_CONFIG['host']}")
    with temp_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}"))
        conn.commit()
    temp_engine.dispose()
    print("✅ Database created/verified")
except Exception as e:
    print(f"❌ Database error: {e}")
    exit(1)

# Create engine
engine = create_engine(f"mysql+pymysql://{DB_CONFIG['username']}:{quote(DB_CONFIG['password'], safe='')}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")

# Create table
create_table_query = """
CREATE TABLE IF NOT EXISTS upi_transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id VARCHAR(20),
    user_id INT,
    transaction_amount FLOAT,
    transaction_date DATETIME,
    transaction_time DATETIME,
    transaction_hour INT,
    transaction_type VARCHAR(20),
    payment_method VARCHAR(30),
    merchant_category VARCHAR(50),
    device_type VARCHAR(20),
    location VARCHAR(50),
    account_balance FLOAT,
    is_foreign_transaction INT,
    failed_login_attempts INT,
    account_tenure_years INT,
    risk_score FLOAT,
    is_fraud INT,
    behavioral_anomaly_score FLOAT,
    device_risk_score FLOAT,
    rule_based_score FLOAT,
    classification VARCHAR(20),
    triggered_rules TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_customer_id (customer_id),
    INDEX idx_is_fraud (is_fraud),
    INDEX idx_classification (classification)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

try:
    with engine.connect() as conn:
        conn.execute(text(create_table_query))
        conn.commit()
    print("✅ Table created/verified")
except Exception as e:
    print(f"❌ Table error: {e}")

# ============================================================================
# STEP 2: Fraud Detection Classes
# ============================================================================

class LegacyRuleFraudDetector:
    def __init__(self):
        self.customer_profiles = defaultdict(lambda: {
            'count': 0, 'avg_amount': 0, 'total': 0,
            'hours': defaultdict(int), 'locations': defaultdict(int),
            'devices': defaultdict(int), 'last_tx': None
        })
        self.SAFE = 20
        self.REVIEW = 50
    
    def analyze(self, txn):
        customer_id = txn['customer_id']
        profile = self.customer_profiles[customer_id]
        
        # Check if this is a known fraud customer
        is_fraud_customer = customer_id.startswith('C_FRUD_')
        is_medium_risk = customer_id.startswith('C_MED_')
        
        # Rule-based scoring
        score = 2
        rules = []
        
        amt = txn['transaction_amount']
        hour = txn['transaction_hour']
        device = txn['device_type']
        foreign = txn['is_foreign_transaction']
        failed = txn['failed_login_attempts']
        tenure = txn['account_tenure_years']
        merchant = txn['merchant_category']
        
        if amt > 50000: score += 15; rules.append("Very High Amount")
        elif amt > 15000: score += 10; rules.append("High Amount")
        if hour < 2: score += 15; rules.append("Very Unusual Time")
        elif hour < 4: score += 10; rules.append("Unusual Time")
        if foreign: score += 12; rules.append("Foreign")
        if device in ['Web', 'Desktop']: score += 5; rules.append("Web")
        if failed >= 5: score += 15; rules.append("Many Failed Logins")
        elif failed >= 3: score += 10; rules.append("Failed Logins")
        if tenure < 1: score += 12; rules.append("New Account")
        if merchant in ['Electronics', 'Travel', 'Jewelry']: score += 8; rules.append("High-Risk Merchant")
        
        # Add bonus for fraud customers
        if is_fraud_customer:
            score += 30
            rules.append("Known Fraud Pattern")
        elif is_medium_risk:
            score += 15
            rules.append("Medium Risk Pattern")
        
        # Behavioral
        behavioral = 0
        if profile['count'] >= 3:
            if profile['avg_amount'] > 0:
                ratio = amt / profile['avg_amount']
                if ratio > 5: behavioral += 30
                elif ratio > 3: behavioral += 20
                elif ratio > 2: behavioral += 10
            if profile['locations'].get(txn['location'], 0) == 0: behavioral += 25
            if profile['devices'].get(device, 0) == 0: behavioral += 20
        
        # Update profile
        profile['count'] += 1
        profile['total'] += amt
        profile['avg_amount'] = profile['total'] / profile['count']
        profile['hours'][hour] += 1
        profile['locations'][txn['location']] += 1
        profile['devices'][device] += 1
        
        # Final score - higher weights
        final = (score * 0.65) + (behavioral * 0.30) + (random.randint(0, 10) * 0.05)
        final = min(final, 100)
        
        if final > self.REVIEW: cls = "BLOCK"
        elif final > self.SAFE: cls = "REVIEW"
        else: cls = "APPROVE"
        
        return {
            'risk_score': round(final, 2),
            'is_fraud': 1 if cls == "BLOCK" else 0,
            'behavioral_anomaly_score': behavioral,
            'device_risk_score': random.randint(0, 15) if random.random() < 0.1 else 0,
            'rule_based_score': score,
            'classification': cls,
            'triggered_rules': ", ".join(rules) if rules else "None"
        }

# Use the shared hybrid engine with its trained PyTorch deep-learning model.
# A small deterministic bootstrap set keeps the streamer self-contained; in
# production this should be replaced with labelled transactions from storage.
def _bootstrap_deep_model(detector):
    rng = np.random.default_rng(42)
    n = 4000
    data = pd.DataFrame({
        'transaction_amount': rng.exponential(3000, n).clip(10, 100000),
        'transaction_hour': rng.integers(0, 24, n),
        'is_foreign_transaction': rng.choice([0, 1], n, p=[.95, .05]),
        'failed_login_attempts': rng.poisson(.1, n),
        'account_tenure_years': rng.exponential(3, n).clip(0, 20),
        'device_risk': rng.uniform(0, 20, n),
        'behavioral_anomaly': rng.uniform(0, 30, n),
        'velocity_score': rng.poisson(1, n) * 10,
        'reputation_score': rng.normal(90, 10, n).clip(0, 100),
    })
    fraud = rng.choice(n, size=int(n * .05), replace=False)
    data.loc[fraud, 'transaction_amount'] *= rng.uniform(3, 10, len(fraud))
    data.loc[fraud, 'transaction_hour'] = rng.choice([0, 1, 2, 22, 23], len(fraud))
    data.loc[fraud, 'is_foreign_transaction'] = 1
    data.loc[fraud, 'failed_login_attempts'] += rng.poisson(2, len(fraud))
    data.loc[fraud, 'device_risk'] += rng.uniform(10, 30, len(fraud))
    data.loc[fraud, 'behavioral_anomaly'] += rng.uniform(20, 50, len(fraud))
    data.loc[fraud, 'reputation_score'] -= rng.uniform(20, 50, len(fraud))
    data['is_fraud'] = 0
    data.loc[fraud, 'is_fraud'] = 1
    detector.ml_detector.train_model(data, epochs=25, batch_size=256)


class FraudDetector:
    """Streaming adapter for the shared deep-learning hybrid engine."""
    def __init__(self):
        self.engine = HybridFraudDetector()
        _bootstrap_deep_model(self.engine)

    def analyze(self, txn):
        assessment = self.engine.analyze_transaction(txn, use_ml=True)
        scores = assessment['scores']
        classification = assessment['classification']
        return {
            'risk_score': assessment['risk_score'],
            'is_fraud': int(classification == 'BLOCK'),
            'behavioral_anomaly_score': assessment['behavioral_anomaly'],
            'device_risk_score': assessment['device_risk'],
            'rule_based_score': scores['rule_based'],
            'classification': classification,
            'triggered_rules': ', '.join(assessment['triggered_rules']) or 'None'
        }


fraud_detector = FraudDetector()
email_alert_service = SevereRiskEmailAlert()

# ============================================================================
# STEP 3: Transaction Generator
# ============================================================================

def generate_transaction():
    now = datetime.now()
    
    # Generate different types of transactions
    rand = random.random()
    
    if rand < 0.03:
        # HIGH RISK / FRAUD TRANSACTION (3%)
        customer_id = f"C_FRUD_{random.randint(100, 999)}"
        amount = round(random.uniform(20000, 100000), 2)
        hour = random.choice([1, 2, 3, 23])
        is_foreign = 1
        failed_logins = random.randint(3, 5)
        tenure = random.randint(0, 1)
        device = 'Web'
        location = 'Unknown'
    elif rand < 0.10:
        # MEDIUM RISK TRANSACTION (7%)
        customer_id = f"C_MED_{random.randint(1000, 9999)}"
        amount = round(random.uniform(10000, 30000), 2)
        hour = random.choice([0, 5, 22, 23])
        is_foreign = random.choice([0, 1])
        failed_logins = random.randint(1, 3)
        tenure = random.randint(0, 3)
        device = random.choice(['Web', 'Desktop'])
        location = random.choice(['Chennai', 'Mumbai', 'Delhi'])
    else:
        # NORMAL TRANSACTION (90%)
        customer_id = f"C{random.randint(1000, 9999)}"
        amount = round(max(np.random.exponential(scale=3000), 10), 2)
        hour = now.hour
        is_foreign = random.choice([0, 1])
        failed_logins = random.randint(0, 2)
        tenure = random.randint(1, 20)
        device = random.choice(['Android', 'iOS', 'Mobile'])
        location = random.choice(['Chennai', 'Mumbai', 'Delhi', 'Hyderabad', 'Bangalore', 'Pune']) 
    
    return {
        'customer_id': customer_id,
        'user_id': random.randint(1, 5000),
        'transaction_amount': amount,
        'transaction_date': now,
        'transaction_time': now,
        'transaction_hour': hour,
        'transaction_type': random.choice(['Debit', 'Credit']),
        'payment_method': random.choice(['Card', 'NetBanking', 'UPI', 'Wallet']),
        'merchant_category': random.choice(['Electronics', 'Grocery', 'Travel', 'Restaurant', 'Healthcare', 'Entertainment', 'Utilities', 'Shopping']),
        'device_type': device,
        'location': location,
        'account_balance': round(random.uniform(5000, 500000), 2),
        'is_foreign_transaction': is_foreign,
        'failed_login_attempts': failed_logins,
        'account_tenure_years': tenure
    }

# ============================================================================
# STEP 4: Main Streaming Loop
# ============================================================================

stats = {'generated': 0, 'inserted': 0, 'blocked': 0, 'safe': 0, 'review': 0}
buffer = []
start_time = datetime.now()

try:
    while True:
        loop_start = time.time()
        
        # Generate batch
        for _ in range(TRANSACTIONS_PER_SECOND):
            txn = generate_transaction()
            result = fraud_detector.analyze(txn)
            txn.update(result)
            if email_alert_service.is_severe(result):
                email_alert_service.send_in_background(txn, result)
            
            stats['generated'] += 1
            if txn['classification'] == 'BLOCK': stats['blocked'] += 1
            elif txn['classification'] == 'REVIEW': stats['review'] += 1
            else: stats['safe'] += 1
            
            buffer.append(txn)
        
        # Insert to database
        if len(buffer) >= BATCH_SIZE:
            batch = buffer[:BATCH_SIZE]
            buffer = buffer[BATCH_SIZE:]
            try:
                df = pd.DataFrame(batch)
                df.to_sql('upi_transactions', con=engine, if_exists='append', index=False)
                stats['inserted'] += len(batch)
            except Exception as e:
                print(f"\n⚠ DB Error: {e}")
        
        # Progress display
        elapsed = (datetime.now() - start_time).total_seconds()
        rate = stats['generated'] / elapsed if elapsed > 0 else 0
        
        print(f"\r⏱ {datetime.now().strftime('%H:%M:%S')} | "
              f"Total: {stats['generated']:,} | "
              f"Rate: {rate:.1f}/sec | "
              f"DB: {stats['inserted']:,} | "
              f"Blocked: {stats['blocked']:,} | "
              f"Review: {stats['review']:,}",
              end='', flush=True)
        
        # Sleep to maintain rate
        elapsed = time.time() - loop_start
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

except KeyboardInterrupt:
    print("\n\n" + "="*70)
    print("📊 STREAMING STOPPED")
    print("="*70)
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"⏱ Duration: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"📈 Total Generated: {stats['generated']:,}")
    print(f"💾 Inserted to DB: {stats['inserted']:,}")
    print(f"📊 Rate: {stats['generated']/elapsed:.1f} txn/sec")
    print(f"🚫 Blocked: {stats['blocked']:,}")
    print(f"⚠️ Review: {stats['review']:,}")
    print(f"✅ Safe: {stats['safe']:,}")
    print("="*70)
    
    # Final flush
    if buffer:
        try:
            df = pd.DataFrame(buffer)
            df.to_sql('upi_transactions', con=engine, if_exists='append', index=False)
            print(f"💾 Flushed {len(buffer)} transactions to database")
        except:
            pass
    
    engine.dispose()
