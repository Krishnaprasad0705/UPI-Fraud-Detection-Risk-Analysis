import os
from email_alerts import _load_project_dotenv
_load_project_dotenv()
"""
Script to view stored UPI transactions from the database
"""

import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import quote

# Database configuration
DB_CONFIG = {
    'username': 'root',
    'password': os.getenv('UPI_DB_PASSWORD', 'Password'), 
    'host': 'localhost',
    'database': 'upi_fraud_db'
}

# Create engine
engine = create_engine(f"mysql+pymysql://{DB_CONFIG['username']}:{quote(DB_CONFIG['password'], safe='')}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")

print("="*80)
print("📊 UPI FRAUD DETECTION - TRANSACTION VIEWER")
print("="*80)

# Total count
total = pd.read_sql("SELECT COUNT(*) as total FROM upi_transactions", engine).iloc[0, 0]
print(f"\n📈 Total Transactions: {total:,}")

# Classification summary
print("\n📋 Classification Summary:")
classification = pd.read_sql("""
    SELECT classification, COUNT(*) as count, 
           ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
    FROM upi_transactions 
    GROUP BY classification
""", engine)
print(classification.to_string(index=False))

# Risk score distribution
print("\n📊 Risk Score Distribution:")
risk_dist = pd.read_sql("""
    SELECT 
        CASE 
            WHEN risk_score < 30 THEN 'Safe (0-30%)'
            WHEN risk_score < 70 THEN 'Review (30-70%)'
            ELSE 'High Risk (70-100%)'
        END as risk_category,
        COUNT(*) as count
    FROM upi_transactions
    GROUP BY risk_category
""", engine)
print(risk_dist.to_string(index=False))

# Sample recent transactions
print("\n📝 Sample Recent Transactions:")
sample = pd.read_sql("""
    SELECT 
        transaction_id,
        customer_id,
        transaction_amount,
        location,
        device_type,
        risk_score,
        classification,
        triggered_rules
    FROM upi_transactions 
    ORDER BY transaction_id DESC 
    LIMIT 10
""", engine)
print(sample.to_string(index=False))

# Top high-risk transactions
print("\n🚨 Top High-Risk Transactions (Risk > 50%):")
high_risk = pd.read_sql("""
    SELECT 
        transaction_id,
        customer_id,
        transaction_amount,
        location,
        risk_score,
        classification,
        triggered_rules
    FROM upi_transactions 
    WHERE risk_score > 50
    ORDER BY risk_score DESC 
    LIMIT 10
""", engine)
print(high_risk.to_string(index=False))

print("\n" + "="*80)

engine.dispose()
