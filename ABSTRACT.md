# AI-Driven UPI Fraud Detection System (Technical Abstract)

The system implements real-time fraud detection for UPI transactions at 20 txns/sec using a hybrid engine in `fraud_detection_system.py`: rule-based (10 weighted rules, e.g., amount>50k +4%), behavioral profiling, device analysis, reputation scoring, and Random Forest ML (9 features: amount, hour, foreign_tx, etc.). Risk scores (0-100%) classify as APPROVE/REVIEW/BLOCK.

Transactions stream via `start_streaming.py` to MySQL (`upi_fraud_db.upi_transactions`, indexed on customer_id/time/score). Flask API (`fraud_detection_api_new.py`) serves endpoints (/api/stats, /api/alerts, CSV exports). Dashboard (templates/dashboard.html, Chart.js) shows live pie/trend/hourly/location charts + alerts.

Performance: <200ms latency. Deploy: run_dashboard.bat.

**Word count: 92**
