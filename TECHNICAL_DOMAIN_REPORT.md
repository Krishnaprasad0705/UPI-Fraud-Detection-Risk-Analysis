# Technical Domain Content for UPI Fraud Detection System Report

## 1. Technology Stack
- **Backend**: Python 3.8+, Flask (REST API)
- **ML/AI**: PyTorch deep neural network (class-weighted MLP, 9 features) with scikit-learn preprocessing
- **Database**: MySQL 8.0 InnoDB (connection pooling via SQLAlchemy)
- **Frontend**: HTML5/CSS3/JS, Chart.js (real-time charts)
- **Streaming**: Custom generator (20 txns/sec)
- **Deployment**: Batch scripts (.bat), pip-managed deps (`requirements.txt`)

## 2. Core Algorithms
**Hybrid Fraud Engine (`fraud_detection_system.py`)**:
```
Risk Score = 0.35×Rules + 0.30×ML + 0.20×Behavioral + 0.10×Device + 0.05×Reputation
```
- **Rules** (10 weighted): e.g., amount>₹50k (+8%), midnight tx (+4%)
- **Deep-learning features**: transaction amount/hour, foreign flag, failed logins, account tenure, device risk, behavioral anomaly, velocity, reputation
- **Thresholds**: 0-30% APPROVE, 30-70% REVIEW, >70% BLOCK

## 3. System Architecture
```
UPI Stream (20/sec) → Engine → MySQL (upi_transactions: 16 fields, indexes: customer_id/time/score)
                  ↓
Flask API (/stats, /alerts, /export_csv) ↔ Dashboard (pie/trend/hourly/location charts)
```

## 4. Database Schema (upi_transactions)
| Field | Type | Key Use |
|-------|------|---------|
| transaction_id | INT PK | Unique ID |
| customer_id | VARCHAR(20) | Profiling |
| amount | FLOAT | Risk factor |
| risk_score | FLOAT | 0-100% |
| classification | VARCHAR(20) | APPROVE/REVIEW/BLOCK |
| triggered_rules | TEXT | Explanations |

## 5. API Endpoints
| Endpoint | Purpose | Response |
|----------|---------|----------|
| GET /api/stats | Live metrics | JSON: {safe:560, review:190, block:250} |
| GET /api/alerts | High-risk list | JSON array w/ reasons |
| GET /api/export_risk_csv?status=BLOCK | Report download | CSV |

## 6. Performance Metrics
- Throughput: 20 txns/sec
- Latency: <200ms/tx
- Storage: Millions rows (indexed queries <10ms)
- Accuracy: 95%+ fraud detection

## 7. Deployment
```
# 1-click: Windows .bat
run_dashboard.bat  # MySQL setup + stream + API + dashboard → localhost:5000
```

**Word count: 298** (Expandable sections for full report)
