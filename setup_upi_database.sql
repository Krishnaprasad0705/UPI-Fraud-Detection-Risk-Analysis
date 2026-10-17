-- ============================================================================
-- UPI FRAUD DETECTION DATABASE SETUP
-- ============================================================================

-- Create Database
CREATE DATABASE IF NOT EXISTS upi_fraud_db;
USE upi_fraud_db;

-- ============================================================================
-- Create UPI Transactions Table
-- ============================================================================
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
    behavioral_anomaly_score FLOAT DEFAULT 0,
    device_risk_score FLOAT DEFAULT 0,
    rule_based_score FLOAT DEFAULT 0,
    classification VARCHAR(20) DEFAULT 'APPROVE',
    triggered_rules TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_transaction_time (transaction_time),
    INDEX idx_is_fraud (is_fraud),
    INDEX idx_risk_score (risk_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Verify Table Structure
-- ============================================================================
DESCRIBE upi_transactions;

-- ============================================================================
-- View Existing Transactions (if any)
-- ============================================================================
SELECT * FROM upi_transactions LIMIT 10;

-- ============================================================================
-- Statistical Queries (for analysis)
-- ============================================================================

-- Total fraud count
SELECT COUNT(*) as total_frauds FROM upi_transactions WHERE is_fraud = 1;

-- Fraud rate percentage
SELECT 
    COUNT(CASE WHEN is_fraud = 1 THEN 1 END) as fraud_count,
    COUNT(*) as total_transactions,
    ROUND((COUNT(CASE WHEN is_fraud = 1 THEN 1 END) / COUNT(*)) * 100, 2) as fraud_rate_percent
FROM upi_transactions;

-- Frauds by device type
SELECT device_type, COUNT(*) as fraud_count
FROM upi_transactions 
WHERE is_fraud = 1
GROUP BY device_type
ORDER BY fraud_count DESC;

-- Frauds by location
SELECT location, COUNT(*) as fraud_count
FROM upi_transactions 
WHERE is_fraud = 1
GROUP BY location
ORDER BY fraud_count DESC;

-- Average risk score by transaction type
SELECT 
    transaction_type,
    AVG(risk_score) as avg_risk_score,
    MAX(risk_score) as max_risk_score,
    COUNT(*) as transaction_count
FROM upi_transactions
GROUP BY transaction_type;

-- High-risk transactions (risk_score > 70)
SELECT 
    transaction_id,
    customer_id,
    transaction_amount,
    transaction_time,
    device_type,
    location,
    risk_score,
    is_fraud
FROM upi_transactions
WHERE risk_score > 70
ORDER BY transaction_time DESC
LIMIT 20;

-- Foreign transactions fraud analysis
SELECT 
    is_foreign_transaction,
    COUNT(*) as transaction_count,
    COUNT(CASE WHEN is_fraud = 1 THEN 1 END) as fraud_count,
    ROUND((COUNT(CASE WHEN is_fraud = 1 THEN 1 END) / COUNT(*)) * 100, 2) as fraud_rate_percent
FROM upi_transactions
GROUP BY is_foreign_transaction;

-- Hourly fraud distribution
SELECT 
    transaction_hour,
    COUNT(*) as transaction_count,
    COUNT(CASE WHEN is_fraud = 1 THEN 1 END) as fraud_count,
    ROUND((COUNT(CASE WHEN is_fraud = 1 THEN 1 END) / COUNT(*)) * 100, 2) as fraud_rate_percent
FROM upi_transactions
GROUP BY transaction_hour
ORDER BY transaction_hour;

