import sys
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import os
from urllib.parse import quote
import pandas as pd
from sqlalchemy import create_engine, text
from email_alerts import _load_project_dotenv

_load_project_dotenv()

# Database configuration
DB_CONFIG = {
    'username': os.getenv('UPI_DB_USER', 'root'),
    'password': os.getenv('UPI_DB_PASSWORD', 'Password'), 
    'host': os.getenv('UPI_DB_HOST', 'localhost'),
    'port': int(os.getenv('UPI_DB_PORT', '3306')),
    'database': os.getenv('UPI_DB_NAME', 'upi_fraud_db')
}

# Create engine
engine = create_engine(f"mysql+pymysql://{DB_CONFIG['username']}:{quote(DB_CONFIG['password'], safe='')}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

print("="*80)
print("📊 UPI FRAUD DETECTION - TRANSACTION VIEWER")
print("="*80)

with engine.connect() as conn:
    # Total count
    total = pd.read_sql(text("SELECT COUNT(*) as total FROM upi_transactions"), conn).iloc[0, 0]
    print(f"\n📈 Total Transactions: {total:,}")

    # Classification summary
    print("\n📋 Classification Summary:")
    classification = pd.read_sql(text("""
        SELECT classification, COUNT(*) as count, 
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
        FROM upi_transactions 
        GROUP BY classification
    """), conn)
    print(classification.to_string(index=False))

    # Risk score distribution
    print("\n📊 Risk Score Distribution:")
    risk_dist = pd.read_sql(text("""
        SELECT 
            CASE 
                WHEN risk_score < 30 THEN 'Safe (0-30%)'
                WHEN risk_score < 70 THEN 'Review (30-70%)'
                ELSE 'High Risk (70-100%)'
            END as risk_category,
            COUNT(*) as count
        FROM upi_transactions
        GROUP BY risk_category
    """), conn)
    print(risk_dist.to_string(index=False))

    # Sample recent transactions
    print("\n📝 Sample Recent Transactions:")
    sample = pd.read_sql(text("""
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
    """), conn)
    print(sample.to_string(index=False))

    # Top high-risk transactions
    print("\n🚨 Top High-Risk Transactions (Risk > 50%):")
    high_risk = pd.read_sql(text("""
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
    """), conn)
    print(high_risk.to_string(index=False))

print("\n" + "="*80)
engine.dispose()
