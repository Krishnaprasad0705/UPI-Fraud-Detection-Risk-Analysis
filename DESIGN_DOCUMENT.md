# AI-Driven UPI Fraud Detection System - Design Document

## Document Information

**Project Title:** AI-Driven UPI Fraud Detection System  
**Version:** 2.2  
**Date:** March 13, 2026  
**Authors:** [Student Names]  
**Institution:** [Institution Name]  

## Table of Contents

1. [Introduction](#introduction)
2. [System Architecture](#system-architecture)
3. [Database Design](#database-design)
4. [Algorithm Design](#algorithm-design)
5. [API Design](#api-design)
6. [User Interface Design](#user-interface-design)
7. [Security Design](#security-design)
8. [Performance Design](#performance-design)
9. [Testing Design](#testing-design)
10. [Deployment Design](#deployment-design)

---

## 1. Introduction {#introduction}

### 1.1 Purpose
This design document describes the architecture, components, and design decisions for the AI-Driven UPI Fraud Detection System. The system provides real-time fraud detection for UPI transactions using a hybrid approach combining rule-based detection, behavioral analysis, and machine learning.

### 1.2 Scope
The system includes:
- Real-time transaction processing at 20 transactions/second
- Multi-layered fraud detection engine
- MySQL database for transaction storage
- REST API for integration
- Interactive dashboard for monitoring
- CSV export functionality for reports

### 1.3 Assumptions and Constraints
- Target processing rate: 20 transactions/second
- Response time: <200ms per transaction
- Database: MySQL 8.0
- Programming Language: Python 3.8+
- Deployment: Local development environment

---

## 2. System Architecture {#system-architecture}

### 2.1 High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Transaction    │───▶│   Fraud         │───▶│   Database      │
│  Generator      │    │   Detection     │    │   Storage       │
│                 │    │   Engine        │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Dashboard     │
                       │   & API         │
                       │                 │
                       └─────────────────┘
```

### 2.2 Component Description

#### 2.2.1 Transaction Generator (`start_streaming.py`)
- **Purpose:** Generates realistic UPI transactions for testing
- **Rate:** 20 transactions/second
- **Data:** Customer ID, amount, time, location, device, etc.
- **Output:** Transaction objects for fraud analysis

#### 2.2.2 Fraud Detection Engine (`fraud_detection_system.py`)
- **Purpose:** Core fraud detection logic
- **Components:**
  - Rule-based detector
  - Behavioral analyzer
  - ML model predictor
  - Risk scorer
- **Input:** Transaction data
- **Output:** Risk score (0-100%), classification (APPROVE/REVIEW/BLOCK)

#### 2.2.3 Database Layer
- **Purpose:** Persistent storage of transactions and analysis results
- **Technology:** MySQL with SQLAlchemy ORM
- **Tables:** upi_transactions (main table)

#### 2.2.4 API Server (`fraud_detection_api_new.py`)
- **Purpose:** REST API for dashboard and external integration
- **Framework:** Flask
- **Endpoints:** /api/stats, /api/alerts, /api/export_risk_csv, etc.

#### 2.2.5 Dashboard (`templates/dashboard.html`)
- **Purpose:** Web interface for monitoring and reporting
- **Technology:** HTML, CSS, JavaScript, Chart.js
- **Features:** Live charts, statistics, alerts table, CSV export

### 2.3 Data Flow

1. **Transaction Generation:** Realistic UPI transaction data created
2. **Fraud Analysis:** Multi-layered detection applied
3. **Risk Scoring:** Probability calculated (0-100%)
4. **Classification:** Transaction categorized (APPROVE/REVIEW/BLOCK)
5. **Storage:** Transaction stored in database with analysis results
6. **Visualization:** Real-time dashboard updates with charts and alerts

---

## 3. Database Design {#database-design}

### 3.1 Database Schema

#### Table: `upi_transactions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| transaction_id | INT | PRIMARY KEY AUTO_INCREMENT | Unique transaction identifier |
| customer_id | VARCHAR(20) | NOT NULL | UPI customer ID |
| transaction_amount | FLOAT | NOT NULL | Transaction amount in ₹ |
| transaction_time | DATETIME | NOT NULL | Transaction timestamp |
| transaction_hour | INT | NOT NULL | Hour of day (0-23) |
| payment_method | VARCHAR(30) | NOT NULL | Payment method (UPI/Card/Wallet) |
| merchant_category | VARCHAR(50) | NOT NULL | Merchant type |
| device_type | VARCHAR(20) | NOT NULL | Device type (Android/iOS/Web) |
| location | VARCHAR(50) | NOT NULL | Transaction location (city) |
| is_foreign_transaction | INT | DEFAULT 0 | Foreign transaction flag |
| failed_login_attempts | INT | DEFAULT 0 | Failed login count |
| account_tenure_years | INT | DEFAULT 0 | Account age in years |
| risk_score | FLOAT | NOT NULL | Calculated risk score (0-100) |
| is_fraud | INT | NOT NULL | Fraud flag (1=fraud, 0=legit) |
| classification | VARCHAR(20) | NOT NULL | APPROVE/REVIEW/BLOCK |
| triggered_rules | TEXT | NULL | Rules that triggered high risk |

### 3.2 Database Configuration

- **Engine:** InnoDB
- **Charset:** utf8mb4
- **Connection:** SQLAlchemy with connection pooling
- **Credentials:** root/Akash@0706 (development)

### 3.3 Indexes

- Primary Key: transaction_id
- Index: customer_id (for customer profiling)
- Index: transaction_time (for time-based queries)
- Index: risk_score (for filtering high-risk transactions)
- Index: classification (for status-based queries)

---

## 4. Algorithm Design {#algorithm-design}

### 4.1 Fraud Detection Algorithm

#### 4.1.1 Rule-Based Detection

**Algorithm:** Weighted Anomaly Detection with Rule Stacking

**Rules Table:**

| Rule ID | Condition | Weight | Description |
|---------|-----------|--------|-------------|
| R1 | transaction_amount > 50000 | +8% | Very high amount |
| R2 | transaction_amount > 15000 | +4% | High amount |
| R3 | transaction_hour < 2 | +4% | Very unusual time |
| R4 | transaction_hour < 4 | +2% | Unusual time |
| R5 | is_foreign_transaction = 1 | +3% | Foreign transaction |
| R6 | device_type = 'Web' | +1% | Web device |
| R7 | failed_login_attempts >= 5 | +4% | Many failed logins |
| R8 | failed_login_attempts >= 3 | +2% | Failed logins |
| R9 | account_tenure_years < 1 | +5% | New account |
| R10 | merchant_category IN ('Electronics', 'Travel') | +2% | High-risk merchant |

**Base Probability:** 2%

**Formula:**
```
Final Rule Score = Base Probability + Sum of triggered rule weights
```

#### 4.1.2 Behavioral Analysis

**Features Analyzed:**
- Amount deviation from customer average
- Location consistency
- Device fingerprinting
- Time pattern analysis
- Transaction velocity

**Scoring Method:**
- Compare current transaction with customer's historical profile
- Flag anomalies (3x-5x normal amount, new locations, etc.)

#### 4.1.3 Machine Learning Model

**Algorithm:** PyTorch feed-forward deep neural network (MLP) with batch normalization, dropout, AdamW optimization, and class-weighted binary cross-entropy

**Features (9):**
1. transaction_amount (normalized)
2. transaction_hour
3. is_foreign_transaction
4. failed_login_attempts
5. account_tenure_years
6. device_risk
7. behavioral_anomaly
8. velocity_score
9. reputation_score

**Training Data:** Historical transactions with known fraud labels

#### 4.1.4 Hybrid Scoring Formula

```
Final Risk Score = (Rule-Based × 0.35) + (ML × 0.30) + (Behavioral × 0.20) + (Device × 0.10) + (Reputation × 0.05)
```

### 4.2 Classification Thresholds

| Risk Score Range | Classification | Action |
|------------------|----------------|--------|
| 0-30% | APPROVE | Allow transaction |
| 30-70% | REVIEW | Require additional verification (OTP/Biometric) |
| 70-100% | BLOCK | Block transaction immediately |

---

## 5. API Design {#api-design}

### 5.1 REST API Endpoints

#### Core Endpoints

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| GET | `/` | Dashboard homepage | HTML page |
| GET | `/api/stats` | Live transaction statistics | JSON: {total, safe, review, blocked} |
| GET | `/api/alerts` | Recent high-risk transactions | JSON array of alerts |
| GET | `/api/hourly_fraud` | Fraud count by hour | JSON: {hour: count} |
| GET | `/api/location_risk` | Risk count by location | JSON: {location: count} |
| GET | `/api/export_risk_csv?status=BLOCK` | Export CSV for blocked transactions | CSV file download |
| GET | `/api/export_risk_csv?status=REVIEW` | Export CSV for review transactions | CSV file download |

### 5.2 Response Formats

#### `/api/stats` Response:
```json
{
  "total_transactions": 1000,
  "safe_transactions": 560,
  "review_transactions": 190,
  "blocked_transactions": 250,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### `/api/alerts` Response:
```json
[
  {
    "transaction_id": 12345,
    "customer_id": "user123",
    "amount": 25000.00,
    "risk_score": 85.5,
    "location": "Mumbai",
    "reasons": "High Amount, Unusual Time",
    "timestamp": "2024-01-15T10:29:45Z"
  }
]
```

### 5.3 Error Handling

- **400 Bad Request:** Invalid parameters
- **404 Not Found:** Endpoint not found
- **500 Internal Server Error:** Database or processing errors

All errors return JSON: `{"error": "description", "code": 500}`

---

## 6. User Interface Design {#user-interface-design}

### 6.1 Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│ UPI Fraud Detection Dashboard                    [Refresh] │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ Live Stats  │ │ Risk Pie    │ │ Trend Line  │ │ Fraud/Hour │ │
│ │             │ │ Chart       │ │ Chart       │ │ Bar Chart  │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Fraud Alerts Table                                      │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ ID | Customer | Amount | Risk | Location | Reasons │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Export BLOCK CSV] [Export REVIEW CSV]                     │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Design Principles

- **Real-time Updates:** Auto-refresh every 5 seconds
- **Responsive Design:** Mobile-friendly layout
- **Neon Theme:** Modern, professional appearance
- **Interactive Charts:** Hover tooltips, clickable legends
- **Error Handling:** Graceful degradation with error messages

### 6.3 Chart Specifications

#### Risk Distribution Pie Chart
- **Library:** Chart.js
- **Data:** Safe (green), Review (yellow), Blocked (red)
- **Interactive:** Hover shows percentages

#### Trend Line Chart
- **Type:** Line chart
- **X-axis:** Time
- **Y-axis:** Transaction count
- **Real-time:** Updates with new data

#### Fraud by Hour Bar Chart
- **Type:** Bar chart
- **X-axis:** Hours (0-23)
- **Y-axis:** Fraud count
- **Color:** Red bars

#### Risk by Location Bar Chart
- **Type:** Horizontal bar chart
- **Y-axis:** City names
- **X-axis:** Risk transaction count

---

## 7. Security Design {#security-design}

### 7.1 Data Protection

- **Database Security:** Parameterized queries prevent SQL injection
- **API Security:** Input validation and sanitization
- **File Security:** Secure file paths for CSV exports

### 7.2 Privacy Considerations

- **Data Minimization:** Only necessary transaction data stored
- **Retention Policy:** Transactions retained for analysis period
- **Access Control:** Local development environment (no external access)

### 7.3 Fraud Prevention Measures

- **Real-time Detection:** Immediate risk assessment
- **Behavioral Profiling:** Customer pattern learning
- **Device Fingerprinting:** New device detection
- **Reputation System:** Blacklist/whitelist management

---

## 8. Performance Design {#performance-design}

### 8.1 Performance Requirements

- **Throughput:** 20 transactions/second
- **Response Time:** <200ms per transaction
- **Database Queries:** Optimized with indexes
- **Memory Usage:** Efficient data structures

### 8.2 Scalability Considerations

- **Database Connection Pooling:** SQLAlchemy connection pooling
- **Asynchronous Processing:** Background task handling
- **Caching:** Potential for Redis caching in production

### 8.3 Monitoring

- **Logging:** Transaction processing logs
- **Metrics:** Processing rate, error rates
- **Dashboard:** Real-time performance monitoring

---

## 9. Testing Design {#testing-design}

### 9.1 Testing Strategy

- **Unit Testing:** Individual functions and methods
- **Integration Testing:** API endpoints and database operations
- **Performance Testing:** Load testing at target throughput
- **User Acceptance Testing:** Dashboard functionality

### 9.2 Test Cases

#### Fraud Detection Tests
- High amount transactions (>₹50,000)
- Unusual time transactions (midnight-4AM)
- Foreign transactions
- Failed login scenarios
- New account transactions

#### API Tests
- Endpoint response times
- Data accuracy
- Error handling
- CSV export functionality

#### Dashboard Tests
- Chart rendering
- Real-time updates
- Export functionality
- Responsive design

---

## 10. Deployment Design {#deployment-design}

### 10.1 Development Environment

- **OS:** Windows 10/11
- **Python:** 3.8+
- **Database:** MySQL 8.0
- **Web Server:** Flask development server

### 10.2 Production Considerations

- **Web Server:** Gunicorn or uWSGI
- **Database:** MySQL with replication
- **Load Balancer:** Nginx
- **Monitoring:** Application performance monitoring
- **Backup:** Automated database backups

### 10.3 Installation Steps

1. Install Python 3.8+
2. Install MySQL 8.0
3. Create database and run setup script
4. Install Python dependencies
5. Configure environment variables
6. Run database migrations
7. Start the application

---

## Appendices

### Appendix A: Code Structure
```
project/
├── fraud_detection_api_new.py    # Main API server
├── fraud_detection_system.py     # Fraud detection engine
├── start_streaming.py           # Transaction generator
├── view_transactions.py         # Database viewer
├── setup_upi_database.sql       # Database setup
├── requirements.txt             # Python dependencies
├── templates/
│   └── dashboard.html           # Dashboard template
├── run_dashboard.bat            # Unified launcher
└── run_api.bat                  # API only launcher
```

### Appendix B: Risk Scoring Examples

**Example 1: Low Risk Transaction**
- Amount: ₹500
- Time: 2:00 PM
- Location: Known city
- Device: Regular mobile
- Risk Score: 15% → APPROVE

**Example 2: High Risk Transaction**
- Amount: ₹75,000
- Time: 3:00 AM
- Location: Foreign
- Device: New web browser
- Risk Score: 85% → BLOCK

### Appendix C: API Usage Examples

```bash
# Get statistics
curl http://localhost:5000/api/stats

# Export blocked transactions
curl http://localhost:5000/api/export_risk_csv?status=BLOCK -o blocked.csv
```

---

*End of Design Document*
