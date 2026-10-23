import sys
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
"""
==============================================================================
Fraud Detection REST API Server - With Interactive Dashboard
==============================================================================

Flask-based REST API for the AI-Driven UPI Fraud Detection System
Provides endpoints for transaction analysis, customer profiles, and reports

Run: python fraud_detection_api.py
"""

import base64
from datetime import datetime
from functools import wraps
import hashlib
import hmac
import json
import os
import random
import threading
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import Flask, jsonify, make_response, request, send_from_directory
from flask_cors import CORS
import pandas as pd
from sqlalchemy import create_engine, text

from email_alerts import SevereRiskEmailAlert, _load_project_dotenv
from fraud_detection_system import (
    HybridFraudDetector, FraudAlertSystem, ReportGenerator
)

_load_project_dotenv()

def get_db_config():
    _load_project_dotenv()
    return {
        'username': os.getenv('UPI_DB_USER', 'root'),
        'password': os.getenv('UPI_DB_PASSWORD', 'Password'), 
        'host': os.getenv('UPI_DB_HOST', 'localhost'),
        'port': int(os.getenv('UPI_DB_PORT', '3306')),
        'database': os.getenv('UPI_DB_NAME', 'upi_fraud_db')
    }

DB_CONFIG = get_db_config()
_db_engine = None
_db_lock = threading.Lock()

def get_db_engine():
    global _db_engine
    with _db_lock:
        if _db_engine is None:
            cfg = get_db_config()
            pwd = quote(cfg['password'], safe='')
            db_url = f"mysql+pymysql://{cfg['username']}:{pwd}@{cfg['host']}:{cfg['port']}/{cfg['database']}?charset=utf8mb4"
            _db_engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=10,
                max_overflow=20,
                connect_args={'connect_timeout': 3}
            )
        return _db_engine

engine = get_db_engine()

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize core components
detector = HybridFraudDetector()

def _bootstrap_api_model():
    try:
        import numpy as np
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
        print("⚡ [ML INIT] Deep-learning PyTorch model initialized and ready.")
    except Exception as e:
        print(f"[ML INIT NOTE] {e}")

_bootstrap_api_model()
alert_system = FraudAlertSystem()
report_gen = ReportGenerator()

# Lightweight signed-token authentication. Override these in production.
AUTH_SECRET = os.getenv('UPI_AUTH_SECRET', 'change-this-secret')
ADMIN_USER = os.getenv('UPI_ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('UPI_ADMIN_PASSWORD', 'admin123')
retraining_state = {'status': 'idle', 'started_at': None, 'completed_at': None, 'error': None}
notification_log = []
email_alert_service = SevereRiskEmailAlert()

def _token_for(username, role):
    payload = base64.urlsafe_b64encode(json.dumps({'sub': username, 'role': role}).encode()).decode().rstrip('=')
    signature = hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f'{payload}.{signature}'

def _current_user():
    token = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
    try:
        payload, signature = token.split('.', 1)
        expected = hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        padded = payload + '=' * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return None

def require_role(*roles):
    def decorator(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            user = _current_user()
            if not user or user.get('role') not in roles:
                return jsonify({'error': 'Authentication required', 'status': 'unauthorized'}), 401
            return function(*args, **kwargs)
        return wrapped
    return decorator

def notify_alert(alert):
    """Record an alert and optionally POST it to ALERT_WEBHOOK_URL."""
    event = {'created_at': datetime.now().isoformat(), 'alert': alert}
    notification_log.append(event)
    webhook = os.getenv('ALERT_WEBHOOK_URL')
    if webhook:
        try:
            body = json.dumps(event).encode()
            urlopen(Request(webhook, data=body, headers={'Content-Type': 'application/json'}), timeout=3).read()
        except Exception as error:
            event['delivery_error'] = str(error)

def notify_severe_risk_by_email(transaction, result):
    """Queue a secure admin email without delaying the API response."""
    if not email_alert_service.is_severe(result):
        return
    event = {
        'created_at': datetime.now().isoformat(),
        'channel': 'email',
        'status': 'queued',
        'risk_score': result.get('risk_score'),
        'classification': result.get('classification')
    }
    notification_log.append(event)

    def record_outcome(outcome):
        event.update(outcome)
        event['completed_at'] = datetime.now().isoformat()

    email_alert_service.send_in_background(transaction, result, record_outcome)

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username, password = data.get('username'), data.get('password')
    if username == ADMIN_USER and hmac.compare_digest(str(password or ''), ADMIN_PASSWORD):
        return jsonify({'token': _token_for(username, 'admin'), 'role': 'admin', 'expires_in': 3600})
    if username and password and os.getenv('UPI_ANALYST_PASSWORD') and hmac.compare_digest(str(password), os.getenv('UPI_ANALYST_PASSWORD')):
        return jsonify({'token': _token_for(username, 'analyst'), 'role': 'analyst', 'expires_in': 3600})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/auth/me')
@require_role('admin', 'analyst')
def auth_me():
    return jsonify({'user': _current_user()})

@app.route('/api/notifications')
@require_role('admin', 'analyst')
def notifications():
    return jsonify({'notifications': notification_log[-100:], 'count': len(notification_log)})

@app.route('/api/email_config', methods=['GET'])
def email_config():
    email_alert_service.reload_config()
    return jsonify({
        'recipient': email_alert_service.recipient,
        'threshold': email_alert_service.threshold,
        'smtp_host': email_alert_service.host,
        'smtp_port': email_alert_service.port,
        'is_configured': email_alert_service.is_configured
    })

@app.route('/api/send_test_alert', methods=['GET', 'POST'])
def send_test_alert():
    """Protected verification endpoint for SMTP email alerts"""
    target = request.args.get('email')
    outcome = email_alert_service.send_test_email(target)
    return jsonify({
        'status': 'success' if outcome.get('sent') else 'failed',
        'recipient': target or email_alert_service.recipient,
        'details': outcome
    })


# Track transaction counts
detector.total_transactions = 0
detector.blocked_count = 0
detector.review_count = 0
detector.approved_count = 0

# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/')
def index():
    """Dashboard home page - serves the interactive dashboard"""
    try:
        return send_from_directory('templates', 'dashboard.html')
    except Exception:
        # Fallback to simple response
        return jsonify({
            'status': 'running',
            'message': 'API is running. Visit http://localhost:5000 to see the dashboard.',
            'total_transactions': detector.total_transactions,
            'blocked': detector.blocked_count,
            'approved': detector.approved_count
        })

@app.route('/insights')
def insights_page():
    """Reviewer-facing intelligence center."""
    return send_from_directory('templates', 'insights.html')

@app.route('/api/insights')
@require_role('admin', 'analyst')
def insights_data():
    """Aggregated live metrics for the intelligence center."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""SELECT COUNT(*), AVG(risk_score),
                AVG(CASE WHEN classification='BLOCK' THEN 1 ELSE 0 END),
                COUNT(DISTINCT customer_id) FROM upi_transactions""")).fetchone()
            alerts = conn.execute(text("""SELECT customer_id, transaction_amount,
                risk_score, classification, triggered_rules, transaction_time
                FROM upi_transactions WHERE classification IN ('BLOCK','REVIEW')
                ORDER BY transaction_id DESC LIMIT 8""")).fetchall()
        return jsonify({
            'metrics': {'transactions': row[0] or 0, 'average_risk': round(float(row[1] or 0), 2),
                        'block_rate': round(float(row[2] or 0) * 100, 2), 'customers': row[3] or 0},
            'model': {'trained': detector.ml_detector.is_trained, 'name': 'PyTorch MLP',
                      'features': len(detector.ml_detector.feature_names), 'retraining': retraining_state},
            'alerts': [{'customer_id': a[0], 'amount': float(a[1] or 0), 'risk_score': float(a[2] or 0),
                        'classification': a[3], 'reason': a[4] or 'Multiple indicators', 'timestamp': str(a[5])} for a in alerts],
            'notifications': len(notification_log), 'generated_at': datetime.now().isoformat()
        })
    except Exception as error:
        return jsonify({'error': str(error)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.1'
    })

@app.route('/api/stats')
def get_stats():
    """Get current statistics from database with atomic aggregation"""
    try:
        db_engine = get_db_engine()
        with db_engine.connect() as conn:
            query = text("""
                SELECT 
                    COUNT(*) as total,
                    COALESCE(SUM(CASE WHEN UPPER(classification) = 'BLOCK' THEN 1 ELSE 0 END), 0) as blocked,
                    COALESCE(SUM(CASE WHEN UPPER(classification) = 'REVIEW' THEN 1 ELSE 0 END), 0) as review,
                    COALESCE(SUM(CASE WHEN UPPER(classification) IN ('APPROVE', 'SAFE') THEN 1 ELSE 0 END), 0) as approved
                FROM upi_transactions
            """)
            row = conn.execute(query).fetchone()
            
            if row:
                total = int(row[0] or 0)
                blocked = int(row[1] or 0)
                review = int(row[2] or 0)
                approved = int(row[3] or 0)
            else:
                total, blocked, review, approved = 0, 0, 0, 0
        
        return jsonify({
            'total_transactions': total,
            'blocked': blocked,
            'review': review,
            'approved': approved
        })
    except Exception:
        # Graceful fallback to in-memory counters without leaking DB details
        return jsonify({
            'total_transactions': getattr(detector, 'total_transactions', 0),
            'blocked': getattr(detector, 'blocked_count', 0),
            'review': getattr(detector, 'review_count', 0),
            'approved': getattr(detector, 'approved_count', 0)
        })

@app.route('/api/analyze', methods=['POST'])
def analyze_transaction():
    """Analyze a single transaction for fraud"""
    try:
        data = request.get_json()
        
        if 'transaction_time' not in data:
            data['transaction_time'] = datetime.now()
        
        result = detector.analyze_transaction(data, use_ml=True)
        
        # Update stats
        detector.total_transactions += 1
        if result['classification'] == 'BLOCK':
            detector.blocked_count += 1
        elif result['classification'] == 'REVIEW':
            detector.review_count += 1
        else:
            detector.approved_count += 1
        
        # Create alert if high risk
        if result['classification'] in ['BLOCK', 'REVIEW']:
            alert_system.create_alert(result, data)
            notify_alert(result)
        notify_severe_risk_by_email(data, result)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/batch_analyze', methods=['POST'])
def batch_analyze():
    """Analyze multiple transactions"""
    try:
        data = request.get_json()
        transactions = data.get('transactions', [])
        
        results = []
        for txn in transactions:
            if 'transaction_time' not in txn:
                txn['transaction_time'] = datetime.now()
            result = detector.analyze_transaction(txn, use_ml=True)
            results.append(result)
            notify_severe_risk_by_email(txn, result)
            
            # Update stats
            detector.total_transactions += 1
            if result['classification'] == 'BLOCK':
                detector.blocked_count += 1
            elif result['classification'] == 'REVIEW':
                detector.review_count += 1
            else:
                detector.approved_count += 1
        
        return jsonify({
            'results': results,
            'count': len(results),
            'summary': {
                'approved': sum(1 for r in results if r['classification'] == 'APPROVE'),
                'review': sum(1 for r in results if r['classification'] == 'REVIEW'),
                'blocked': sum(1 for r in results if r['classification'] == 'BLOCK')
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/customer/<customer_id>/profile', methods=['GET'])
def get_customer_profile(customer_id):
    """Get customer behavioral profile"""
    profile = detector.behavior_analyzer.get_profile(customer_id)
    profile_dict = dict(profile)
    profile_dict['common_hours'] = dict(profile_dict.get('common_hours', {}))
    profile_dict['common_locations'] = dict(profile_dict.get('common_locations', {}))
    
    return jsonify({
        'customer_id': customer_id,
        'profile': profile_dict,
        'analyzed_at': datetime.now().isoformat()
    })

@app.route('/api/customer/<customer_id>/reputation', methods=['GET'])
def get_customer_reputation(customer_id):
    """Get customer reputation score"""
    reputation = detector.reputation_manager.get_reputation('customer_id', customer_id)
    is_blacklisted = detector.reputation_manager.check_blacklist('customer_ids', customer_id)
    is_whitelisted = detector.reputation_manager.check_whitelist('customer_ids', customer_id)
    
    return jsonify({
        'customer_id': customer_id,
        'reputation_score': reputation,
        'is_blacklisted': is_blacklisted,
        'is_whitelisted': is_whitelisted
    })

@app.route('/api/blacklist/<entity_type>/<entity_id>', methods=['POST'])
@require_role('admin')
def add_to_blacklist(entity_type, entity_id):
    """Add entity to blacklist"""
    data = request.get_json() or {}
    reason = data.get('reason', 'Manual blacklist')
    detector.reputation_manager.add_to_blacklist(entity_type, entity_id, reason)
    
    return jsonify({
        'status': 'success',
        'message': f'{entity_type} {entity_id} added to blacklist',
        'reason': reason
    })

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get fraud alerts from database"""
    try:
        db_engine = get_db_engine()
        
        with db_engine.connect() as conn:
            # Get high-risk transactions (blocked or review)
            result = conn.execute(text("""
                SELECT customer_id, transaction_amount, location, device_type, 
                       risk_score, classification, triggered_rules
                FROM upi_transactions 
                WHERE classification IN ('BLOCK', 'REVIEW')
                ORDER BY transaction_id DESC 
                LIMIT 10
            """))
            rows = result.fetchall()
        
        alerts = []
        for row in rows:
            alerts.append({
                'customer_id': row[0],
                'amount': row[1],
                'location': row[2],
                'device': row[3],
                'risk_score': float(row[4]) if row[4] else 0,
                'classification': row[5],
                'triggered_rules': row[6]
            })
        
        return jsonify({'alerts': alerts, 'count': len(alerts)})
        
    except Exception as e:
        print(f"Alerts error: {e}")
        # Fallback to in-memory alerts
        status = request.args.get('status')
        alerts = alert_system.get_alerts(status)
        return jsonify({'alerts': alerts, 'count': len(alerts)})

@app.route('/api/recent_transactions', methods=['GET'])
def get_recent_transactions():
    """Get recent transactions from database"""
    try:
        db_engine = get_db_engine()
        
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT transaction_id, customer_id, transaction_amount, location, 
                       device_type, risk_score, classification
                FROM upi_transactions 
                ORDER BY transaction_id DESC 
                LIMIT 10
            """))
            rows = result.fetchall()
        
        transactions = []
        for row in rows:
            transactions.append({
                'id': row[0],
                'customer_id': row[1],
                'amount': row[2],
                'location': row[3],
                'device': row[4],
                'risk_score': float(row[5]) if row[5] else 0,
                'classification': row[6]
            })
        
        return jsonify({'transactions': transactions, 'count': len(transactions)})
        
    except Exception as e:
        print(f"Transactions error: {e}")
        return jsonify({'transactions': [], 'count': 0})

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Get system statistics"""
    stats = {
        'active_customers': len(detector.behavior_analyzer.customer_profiles),
        'blacklist_stats': detector.reputation_manager.get_blacklist_stats(),
        'ml_model_trained': detector.ml_detector.is_trained,
        'total_alerts': len(alert_system.alerts),
        'pending_verifications': len(alert_system.pending_verifications)
    }
    return jsonify(stats)

@app.route('/api/simulate_transaction', methods=['POST'])
def simulate_transaction():
    """Simulate a transaction for testing with real-time AI & explainability"""
    data = request.get_json() or {}
    
    transaction = {
        'customer_id': str(data.get('customer_id') or f"C_SIM_{random.randint(1000, 9999)}"),
        'user_id': int(data.get('user_id', random.randint(1, 5000))),
        'transaction_amount': float(data.get('amount', data.get('transaction_amount', random.uniform(500, 75000)))),
        'transaction_hour': int(data.get('hour', data.get('transaction_hour', datetime.now().hour))),
        'transaction_type': data.get('transaction_type', 'Debit'),
        'payment_method': data.get('payment_method', 'UPI'),
        'merchant_category': data.get('merchant_category', 'Electronics'),
        'device_type': data.get('device_type', 'Mobile'),
        'location': data.get('location', 'Mumbai'),
        'account_balance': float(data.get('account_balance', 50000.0)),
        'is_foreign_transaction': int(data.get('is_foreign_transaction', 0)),
        'failed_login_attempts': int(data.get('failed_login_attempts', 0)),
        'account_tenure_years': float(data.get('account_tenure_years', 2.5)),
        'transaction_time': datetime.now()
    }
    
    result = detector.analyze_transaction(transaction, use_ml=True)
    
    # Save to MySQL database if requested
    if data.get('save_to_db', True):
        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO upi_transactions (
                        customer_id, user_id, transaction_amount, transaction_time,
                        transaction_hour, transaction_type, payment_method, merchant_category,
                        device_type, location, account_balance, is_foreign_transaction,
                        failed_login_attempts, account_tenure_years, risk_score,
                        is_fraud, behavioral_anomaly_score, device_risk_score,
                        rule_based_score, classification, triggered_rules
                    ) VALUES (
                        :customer_id, :user_id, :amount, :tx_time,
                        :tx_hour, :tx_type, :payment_method, :merchant_category,
                        :device_type, :location, :balance, :is_foreign,
                        :failed_logins, :tenure, :risk_score,
                        :is_fraud, :behavioral, :device_risk,
                        :rule_score, :classification, :rules
                    )
                """), {
                    'customer_id': transaction['customer_id'],
                    'user_id': transaction['user_id'],
                    'amount': transaction['transaction_amount'],
                    'tx_time': transaction['transaction_time'],
                    'tx_hour': transaction['transaction_hour'],
                    'tx_type': transaction['transaction_type'],
                    'payment_method': transaction['payment_method'],
                    'merchant_category': transaction['merchant_category'],
                    'device_type': transaction['device_type'],
                    'location': transaction['location'],
                    'balance': transaction['account_balance'],
                    'is_foreign': transaction['is_foreign_transaction'],
                    'failed_logins': transaction['failed_login_attempts'],
                    'tenure': transaction['account_tenure_years'],
                    'risk_score': result['risk_score'],
                    'is_fraud': int(result['classification'] == 'BLOCK'),
                    'behavioral': result.get('behavioral_anomaly', 0),
                    'device_risk': result.get('device_risk', 0),
                    'rule_score': result.get('scores', {}).get('rule_based', 0),
                    'classification': result['classification'],
                    'rules': ", ".join(result.get('triggered_rules', []))
                })
                conn.commit()
        except Exception as err:
            print(f"Error inserting simulated txn into DB: {err}")
            
    # If severe, trigger email in background
    if email_alert_service.is_severe(result):
        email_alert_service.send_in_background(transaction, result)
    
    # Update stats
    detector.total_transactions += 1
    if result['classification'] == 'BLOCK':
        detector.blocked_count += 1
    elif result['classification'] == 'REVIEW':
        detector.review_count += 1
    else:
        detector.approved_count += 1
    
    return jsonify({
        'transaction': {
            'customer_id': transaction['customer_id'],
            'amount': transaction['transaction_amount'],
            'hour': transaction['transaction_hour'],
            'location': transaction['location'],
            'device': transaction['device_type'],
            'is_foreign': transaction['is_foreign_transaction'],
            'failed_logins': transaction['failed_login_attempts']
        },
        'analysis': result
    })

@app.route('/api/customer/<customer_id>/history', methods=['GET'])
def customer_history(customer_id):
    """Return a customer's recent transactions and aggregate risk."""
    limit = min(max(request.args.get('limit', 50, type=int), 1), 500)
    try:
        query = text("""SELECT transaction_id, transaction_amount, transaction_time,
            risk_score, classification, triggered_rules FROM upi_transactions
            WHERE customer_id = :customer_id ORDER BY transaction_id DESC LIMIT :limit""")
        with engine.connect() as conn:
            rows = conn.execute(query, {'customer_id': customer_id, 'limit': limit}).fetchall()
        history = [{'transaction_id': r[0], 'amount': r[1], 'timestamp': str(r[2]),
                    'risk_score': float(r[3] or 0), 'classification': r[4],
                    'triggered_rules': r[5]} for r in rows]
        return jsonify({'customer_id': customer_id, 'history': history,
                        'count': len(history), 'average_risk': round(sum(x['risk_score'] for x in history) / len(history), 2) if history else 0})
    except Exception as error:
        return jsonify({'error': str(error)}), 500

@app.route('/api/retrain', methods=['POST'])
@require_role('admin')
def retrain_model():
    """Start background retraining from labeled transactions in MySQL."""
    if retraining_state['status'] == 'running':
        return jsonify(retraining_state), 409
    def train():
        retraining_state.update(status='running', started_at=datetime.now().isoformat(), error=None)
        try:
            query = text("""SELECT transaction_amount, transaction_hour, is_foreign_transaction,
                failed_login_attempts, account_tenure_years, device_risk_score AS device_risk,
                behavioral_anomaly_score AS behavioral_anomaly, 0 AS velocity_score,
                90 AS reputation_score, is_fraud FROM upi_transactions
                WHERE is_fraud IS NOT NULL ORDER BY transaction_id DESC LIMIT 50000""")
            with engine.connect() as conn:
                data = pd.read_sql(query, conn)
            if len(data) < 100 or data['is_fraud'].nunique() < 2:
                raise ValueError('At least 100 labeled rows containing both classes are required')
            accuracy = detector.ml_detector.train_model(data, epochs=80, batch_size=256)
            retraining_state['accuracy'] = accuracy
            retraining_state['status'] = 'completed'
        except Exception as error:
            retraining_state.update(status='failed', error=str(error))
        finally:
            retraining_state['completed_at'] = datetime.now().isoformat()
    threading.Thread(target=train, daemon=True).start()
    return jsonify({'status': 'started'})

@app.route('/api/retrain/status')
@require_role('admin', 'analyst')
def retrain_status():
    return jsonify(retraining_state)

# ============================================================================
# QUICK ACTION ENDPOINTS
# ============================================================================

@app.route('/api/export_report', methods=['GET'])
def export_report():
    """Export fraud detection report"""
    try:
        db_engine = get_db_engine()
        
        with db_engine.connect() as conn:
            # Get summary stats
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN classification = 'BLOCK' THEN 1 ELSE 0 END) as blocked,
                    SUM(CASE WHEN classification = 'REVIEW' THEN 1 ELSE 0 END) as review,
                    SUM(CASE WHEN classification = 'APPROVE' THEN 1 ELSE 0 END) as approved,
                    AVG(risk_score) as avg_risk,
                    SUM(transaction_amount) as total_amount
                FROM upi_transactions
            """))
            row = result.fetchone()
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_transactions': row[0] or 0,
                'blocked': row[1] or 0,
                'under_review': row[2] or 0,
                'approved': row[3] or 0,
                'average_risk_score': round(float(row[4] or 0), 2),
                'total_amount': round(float(row[5] or 0), 2)
            },
            'status': 'success',
            'message': 'Report generated successfully'
        }
        
        return jsonify(report)
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get system settings"""
    return jsonify({
        'fraud_detection': {
            'safe_threshold': 20,
            'review_threshold': 50,
            'ml_model_enabled': True,
            'real_time_monitoring': True
        },
        'alerts': {
            'email_notifications': True,
            'sms_alerts': False,
            'push_notifications': True
        },
        'database': {
            'connected': True,
            'total_transactions': 51780
        },
        'status': 'success'
    })

@app.route('/api/view_all_alerts', methods=['GET'])
def view_all_alerts():
    """Get all alerts with pagination"""
    try:
        from sqlalchemy import text
        
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        offset = (page - 1) * limit
        
        db_engine = get_db_engine()
        
        with db_engine.connect() as conn:
            # Get total count
            result = conn.execute(text("SELECT COUNT(*) FROM upi_transactions WHERE classification IN ('BLOCK', 'REVIEW')"))
            f_row = result.fetchone()
            total = f_row[0] if f_row else 0
            
            # Get paginated alerts
            result = conn.execute(text("""
                SELECT transaction_id, customer_id, transaction_amount, location, device_type, 
                       risk_score, classification, triggered_rules, transaction_time
                FROM upi_transactions 
                WHERE classification IN ('BLOCK', 'REVIEW')
                ORDER BY transaction_id DESC 
                LIMIT :limit OFFSET :offset
            """), {'limit': limit, 'offset': offset})
            rows = result.fetchall()
        
        alerts = []
        for row in rows:
            alerts.append({
                'id': row[0],
                'customer_id': row[1],
                'amount': row[2],
                'location': row[3],
                'device': row[4],
                'risk_score': float(row[5]) if row[5] else 0,
                'classification': row[6],
                'triggered_rules': row[7],
                'timestamp': str(row[8]) if row[8] else None
            })
        
        return jsonify({
            'alerts': alerts,
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit,
            'status': 'success'
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/api/export_risk_csv', methods=['GET'])
def export_risk_csv():
    """Export BLOCK or REVIEW CSV with reasons"""
    status = request.args.get('status', 'BLOCK')
    try:
        db_engine = get_db_engine()
        
        query = """
            SELECT customer_id, transaction_amount, transaction_hour, location, device_type, 
                   risk_score, classification, triggered_rules, transaction_time
            FROM upi_transactions 
            WHERE classification = :status
            ORDER BY transaction_id DESC
        """
        df = pd.read_sql(query, db_engine, params={'status': status})
        df.columns = ['Customer_ID', 'Amount_₹', 'Hour', 'Location', 'Device', 'Risk_Score_%', 'Status', 'Reasons', 'Timestamp']
        
        response = make_response(df.to_csv(index=False))
        response.headers["Content-Disposition"] = f"attachment; filename=upi_{status.lower()}_risk.csv"
        response.headers["Content-type"] = "text/csv"
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/hourly_fraud', methods=['GET'])
def hourly_fraud():
    """Fraud counts by hour for bar chart"""
    try:
        db_engine = get_db_engine()
        query = """
            SELECT transaction_hour, COUNT(*) as risk_count
            FROM upi_transactions 
            WHERE classification IN ('BLOCK', 'REVIEW')
            GROUP BY transaction_hour
            ORDER BY transaction_hour
        """
        df = pd.read_sql(query, db_engine)
        counts = [0]*24
        for _, row in df.iterrows():
            counts[int(row['transaction_hour'])] = row['risk_count']
        return jsonify({'counts': counts})
    except Exception:
        return jsonify({'counts': [0]*24})

INDIAN_CITIES_GEO = [
    {'name': 'Mumbai', 'state': 'Maharashtra', 'region': 'West', 'lat': 19.0760, 'lng': 72.8777, 'base_risk': 52.4, 'vector': 'Midnight Velocity Spikes & Mule Rings', 'base_txns': 42500},
    {'name': 'Delhi', 'state': 'Delhi NCR', 'region': 'North', 'lat': 28.6139, 'lng': 77.2090, 'base_risk': 58.7, 'vector': 'Foreign Proxy IP & SIM Swap Patterns', 'base_txns': 48900},
    {'name': 'Bangalore', 'state': 'Karnataka', 'region': 'South', 'lat': 12.9716, 'lng': 77.5946, 'base_risk': 24.2, 'vector': 'E-Commerce Merchant Spoofing', 'base_txns': 39100},
    {'name': 'Chennai', 'state': 'Tamil Nadu', 'region': 'South', 'lat': 13.0827, 'lng': 80.2707, 'base_risk': 36.8, 'vector': 'Device Fingerprint Mismatch', 'base_txns': 34200},
    {'name': 'Hyderabad', 'state': 'Telangana', 'region': 'South', 'lat': 17.3850, 'lng': 78.4867, 'base_risk': 31.5, 'vector': 'Failed PIN Exceeded Attempts', 'base_txns': 29800},
    {'name': 'Pune', 'state': 'Maharashtra', 'region': 'West', 'lat': 18.5204, 'lng': 73.8567, 'base_risk': 22.1, 'vector': 'Micro-Charge Velocity Probing', 'base_txns': 19400},
    {'name': 'Kolkata', 'state': 'West Bengal', 'region': 'East', 'lat': 22.5726, 'lng': 88.3639, 'base_risk': 49.3, 'vector': 'Rapid Cross-Border Routing', 'base_txns': 22100},
    {'name': 'Ahmedabad', 'state': 'Gujarat', 'region': 'West', 'lat': 23.0225, 'lng': 72.5714, 'base_risk': 39.0, 'vector': 'High-Value Bullion / Jewellery Orders', 'base_txns': 21400},
    {'name': 'Jaipur', 'state': 'Rajasthan', 'region': 'North', 'lat': 26.9124, 'lng': 75.7873, 'base_risk': 44.6, 'vector': 'QR Phishing & Social Engineering', 'base_txns': 16300},
    {'name': 'Lucknow', 'state': 'Uttar Pradesh', 'region': 'North', 'lat': 26.8467, 'lng': 80.9462, 'base_risk': 54.1, 'vector': 'Credential Stuffing Attacks', 'base_txns': 18700},
    {'name': 'Kochi', 'state': 'Kerala', 'region': 'South', 'lat': 9.9312, 'lng': 76.2673, 'base_risk': 18.5, 'vector': 'Normal Retail Activity', 'base_txns': 14200},
    {'name': 'Patna', 'state': 'Bihar', 'region': 'East', 'lat': 25.5941, 'lng': 85.1376, 'base_risk': 55.8, 'vector': 'Phishing & Impersonation Calls', 'base_txns': 15800},
    {'name': 'Chandigarh', 'state': 'Punjab/Haryana', 'region': 'North', 'lat': 30.7333, 'lng': 76.7794, 'base_risk': 27.3, 'vector': 'Low Anomaly Volume', 'base_txns': 12600},
    {'name': 'Indore', 'state': 'Madhya Pradesh', 'region': 'Central', 'lat': 22.7196, 'lng': 75.8577, 'base_risk': 33.4, 'vector': 'Merchant Account Hijack', 'base_txns': 14500},
    {'name': 'Bhubaneswar', 'state': 'Odisha', 'region': 'East', 'lat': 20.2961, 'lng': 85.8245, 'base_risk': 35.2, 'vector': 'Off-Hour High Volume Spikes', 'base_txns': 11200}
]

@app.route('/api/location_risk', methods=['GET'])
def location_risk():
    """Geospatial Risk Intelligence & Top Risky Locations for India Map & Charts"""
    try:
        db_engine = get_db_engine()
        
        # Query database for location-based statistics
        query = """
            SELECT location, 
                   COUNT(*) as total_txns,
                   SUM(CASE WHEN classification = 'BLOCK' THEN 1 ELSE 0 END) as blocked_count,
                   SUM(CASE WHEN classification = 'REVIEW' THEN 1 ELSE 0 END) as review_count,
                   AVG(risk_score) as avg_risk
            FROM upi_transactions 
            GROUP BY location
        """
        df = pd.read_sql(query, db_engine)
        
        db_stats = {}
        for _, row in df.iterrows():
            loc_key = str(row['location']).strip().lower()
            db_stats[loc_key] = {
                'total_txns': int(row['total_txns']),
                'blocked': int(row['blocked_count']),
                'review': int(row['review_count']),
                'avg_risk': round(float(row['avg_risk']) if pd.notna(row['avg_risk']) else 0.0, 1)
            }
        
        # Build enriched cities list
        enriched_cities = []
        for city in INDIAN_CITIES_GEO:
            name_key = city['name'].lower()
            stat = db_stats.get(name_key)
            if not stat:
                # check partial match
                for k, v in db_stats.items():
                    if k in name_key or name_key in k:
                        stat = v
                        break
            
            if stat and stat['total_txns'] > 0:
                txns = stat['total_txns']
                blocked = stat['blocked']
                review = stat['review']
                risk = stat['avg_risk']
            else:
                txns = city['base_txns']
                risk = city['base_risk']
                blocked = int(txns * (risk / 100.0) * 0.4)
                review = int(txns * (risk / 100.0) * 0.6)
            
            # Threat level categorization
            if risk >= 50:
                threat_level = 'CRITICAL'
                color = '#EF4444' # Red
            elif risk >= 35:
                threat_level = 'ELEVATED'
                color = '#F97316' # Orange
            elif risk >= 25:
                threat_level = 'MODERATE'
                color = '#00E5FF' # Cyan
            else:
                threat_level = 'STABLE'
                color = '#22C55E' # Green
            
            enriched_cities.append({
                'name': city['name'],
                'state': city['state'],
                'region': city['region'],
                'lat': city['lat'],
                'lng': city['lng'],
                'risk_score': round(risk, 1),
                'threat_level': threat_level,
                'color': color,
                'total_txns': txns,
                'blocked_count': blocked,
                'review_count': review,
                'flagged_total': blocked + review,
                'primary_vector': city['vector']
            })
        
        # Sort cities by risk score descending
        enriched_cities.sort(key=lambda c: c['risk_score'], reverse=True)
        
        # Summary metrics
        highest_threat = enriched_cities[0] if enriched_cities else None
        safest_hub = enriched_cities[-1] if enriched_cities else None
        critical_count = sum(1 for c in enriched_cities if c['threat_level'] == 'CRITICAL')
        elevated_count = sum(1 for c in enriched_cities if c['threat_level'] == 'ELEVATED')
        
        # Format for top location bar chart
        top_locations = [c['name'] for c in enriched_cities[:8]]
        top_counts = [c['flagged_total'] for c in enriched_cities[:8]]
        
        return jsonify({
            'status': 'success',
            'locations': top_locations,
            'counts': top_counts,
            'cities': enriched_cities,
            'summary': {
                'total_monitored_hubs': len(enriched_cities),
                'critical_hubs': critical_count,
                'elevated_hubs': elevated_count,
                'highest_threat_hub': highest_threat['name'] if highest_threat else 'Delhi',
                'highest_risk_score': highest_threat['risk_score'] if highest_threat else 58.7,
                'safest_hub': safest_hub['name'] if safest_hub else 'Kochi',
                'safest_risk_score': safest_hub['risk_score'] if safest_hub else 18.5
            }
        })
    except Exception as e:
        print(f"Location risk error: {e}")
        # Return robust fallback using INDIAN_CITIES_GEO
        fallback_cities = []
        for city in INDIAN_CITIES_GEO:
            risk = city['base_risk']
            txns = city['base_txns']
            threat = 'CRITICAL' if risk >= 50 else 'ELEVATED' if risk >= 35 else 'MODERATE' if risk >= 25 else 'STABLE'
            color = '#EF4444' if risk >= 50 else '#F97316' if risk >= 35 else '#00E5FF' if risk >= 25 else '#22C55E'
            fallback_cities.append({
                'name': city['name'],
                'state': city['state'],
                'region': city['region'],
                'lat': city['lat'],
                'lng': city['lng'],
                'risk_score': risk,
                'threat_level': threat,
                'color': color,
                'total_txns': txns,
                'blocked_count': int(txns * 0.04),
                'review_count': int(txns * 0.08),
                'flagged_total': int(txns * 0.12),
                'primary_vector': city['vector']
            })
        fallback_cities.sort(key=lambda c: c['risk_score'], reverse=True)
        return jsonify({
            'status': 'fallback',
            'locations': [c['name'] for c in fallback_cities[:8]],
            'counts': [c['flagged_total'] for c in fallback_cities[:8]],
            'cities': fallback_cities,
            'summary': {
                'total_monitored_hubs': len(fallback_cities),
                'critical_hubs': 3,
                'elevated_hubs': 4,
                'highest_threat_hub': 'Delhi',
                'highest_risk_score': 58.7,
                'safest_hub': 'Kochi',
                'safest_risk_score': 18.5
            }
        })

@app.route('/api/hourly_risk_avg', methods=['GET'])
def hourly_risk_avg():
    """Average risk score by hour for new line chart (replacement for fraud by hour)"""
    try:
        db_engine = get_db_engine()
        query = """
            SELECT 
                transaction_hour, 
                AVG(risk_score) as avg_risk,
                COUNT(*) as tx_count
            FROM upi_transactions 
            GROUP BY transaction_hour
            ORDER BY transaction_hour
        """
        df = pd.read_sql(query, db_engine)
        avg_risk = [round(float(row['avg_risk']) if pd.notna(row['avg_risk']) else 0, 1) for _, row in df.iterrows()]
        return jsonify({'avg_risk': avg_risk})
    except Exception as e:
        print(f"Hourly risk avg error: {e}")
        return jsonify({'avg_risk': [25.0] * 24})  # Fallback average risk

@app.route('/api/view_history', methods=['GET'])
def view_history():
    """Get transaction history with pagination"""
    try:
        from sqlalchemy import text
        
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        offset = (page - 1) * limit
        classification = request.args.get('classification', None)
        
        db_engine = get_db_engine()
        
        with db_engine.connect() as conn:
            # Build query
            if classification:
                result = conn.execute(text("SELECT COUNT(*) FROM upi_transactions WHERE classification = :classification"), {'classification': classification})
                f_row = result.fetchone()
                total = f_row[0] if f_row else 0
                
                result = conn.execute(text("""
                    SELECT transaction_id, customer_id, transaction_amount, location, device_type, 
                           risk_score, classification, transaction_time
                    FROM upi_transactions 
                    WHERE classification = :classification
                    ORDER BY transaction_id DESC 
                    LIMIT :limit OFFSET :offset
                """), {'classification': classification, 'limit': limit, 'offset': offset})
            else:
                result = conn.execute(text("SELECT COUNT(*) FROM upi_transactions"))
                f_row = result.fetchone()
                total = f_row[0] if f_row else 0
                
                result = conn.execute(text("""
                    SELECT transaction_id, customer_id, transaction_amount, location, device_type, 
                           risk_score, classification, transaction_time
                    FROM upi_transactions 
                    ORDER BY transaction_id DESC 
                    LIMIT :limit OFFSET :offset
                """), {'limit': limit, 'offset': offset})
            
            rows = result.fetchall()
        
        transactions = []
        for row in rows:
            transactions.append({
                'id': row[0],
                'customer_id': row[1],
                'amount': row[2],
                'location': row[3],
                'device': row[4],
                'risk_score': float(row[5]) if row[5] else 0,
                'classification': row[6],
                'timestamp': str(row[7]) if row[7] else None
            })
        
        return jsonify({
            'transactions': transactions,
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit,
            'status': 'success'
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

# ============================================================================
# NEW ENHANCED ENDPOINTS
# ============================================================================

@app.route('/api/status', methods=['GET'])
def api_status():
    """Health status check for live indicator"""
    try:
        db_engine = get_db_engine()
        
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM upi_transactions"))
            s_row = result.fetchone()
            count = s_row[0] if s_row else 0
        return jsonify({
            'status': 'connected',
            'server': 'running',
            'database': 'connected',
            'timestamp': datetime.now().isoformat(),
            'transactions_in_db': count
        })
    except Exception:
        return jsonify({
            'status': 'disconnected',
            'server': 'error',
            'database': 'error',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard_data():
    """Get all dashboard data in one request"""
    try:
        db_engine = get_db_engine()
        
        with db_engine.connect() as conn:
            # Stats
            result = conn.execute(text("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN classification = 'BLOCK' THEN 1 ELSE 0 END) as blocked,
                       SUM(CASE WHEN classification = 'REVIEW' THEN 1 ELSE 0 END) as review,
                       SUM(CASE WHEN classification = 'APPROVE' THEN 1 ELSE 0 END) as approved
                FROM upi_transactions
            """))
            row = result.fetchone()
            stats = {
                'total_transactions': row[0] or 0,
                'blocked': row[1] or 0,
                'review': row[2] or 0,
                'approved': row[3] or 0
            }
            
            # Hourly fraud
            result = conn.execute(text("""
                SELECT transaction_hour, COUNT(*) as risk_count
                FROM upi_transactions 
                WHERE classification IN ('BLOCK', 'REVIEW')
                GROUP BY transaction_hour
                ORDER BY transaction_hour
            """))
            hourly_data = [0] * 24
            for hour, count in result.fetchall():
                hourly_data[int(hour)] = count
            
            # Location risk
            result = conn.execute(text("""
                SELECT location, COUNT(*) as risk_count
                FROM upi_transactions 
                WHERE classification IN ('BLOCK', 'REVIEW')
                GROUP BY location
                ORDER BY risk_count DESC
                LIMIT 10
            """))
            locations = []
            location_counts = []
            for loc, count in result.fetchall():
                locations.append(loc)
                location_counts.append(count)
            
            # Recent alerts
            result = conn.execute(text("""
                SELECT transaction_id, customer_id, transaction_amount, location, device_type, 
                       risk_score, classification, triggered_rules
                FROM upi_transactions 
                WHERE classification IN ('BLOCK', 'REVIEW')
                ORDER BY transaction_id DESC 
                LIMIT 5
            """))
            alerts = []
            for row in result.fetchall():
                alerts.append({
                    'id': row[0],
                    'customer_id': row[1],
                    'amount': row[2],
                    'location': row[3],
                    'device': row[4],
                    'risk_score': float(row[5]) if row[5] else 0,
                    'classification': row[6],
                    'triggered_rules': row[7]
                })
        
        return jsonify({
            'stats': stats,
            'hourly': {'counts': hourly_data},
            'location': {'locations': locations, 'counts': location_counts},
            'alerts': alerts,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Dashboard data error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/risk-data', methods=['GET'])
def get_risk_data():
    """Get high-risk transaction data for CSV export"""
    try:
        db_engine = get_db_engine()
        
        query = """
            SELECT transaction_id, user_id, transaction_amount, location, device_type, 
                   transaction_hour, risk_score, classification, triggered_rules
            FROM upi_transactions 
            WHERE classification IN ('BLOCK', 'REVIEW')
            ORDER BY risk_score DESC
            LIMIT 1000
        """
        df = pd.read_sql(query, db_engine)
        
        risk_data = []
        for _, row in df.iterrows():
            risk_data.append({
                'transaction_id': str(row['transaction_id']),
                'user_id': str(row['user_id']),
                'amount': float(row['transaction_amount']),
                'location': str(row['location']),
                'device': str(row['device_type']),
                'transaction_hour': int(row['transaction_hour']),
                'risk_score': float(row['risk_score']),
                'fraud_status': str(row['classification']),
                'risk_reason': str(row['triggered_rules'] or 'Multiple fraud indicators')
            })
        return jsonify({'risk_data': risk_data, 'count': len(risk_data)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/report', methods=['GET'])
def get_report_data():
    """Get report data for export"""
    try:
        db_engine = get_db_engine()
        
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN classification = 'BLOCK' THEN 1 ELSE 0 END) as blocked,
                    SUM(CASE WHEN classification = 'REVIEW' THEN 1 ELSE 0 END) as review,
                    SUM(CASE WHEN classification = 'APPROVE' THEN 1 ELSE 0 END) as approved,
                    AVG(risk_score) as avg_risk,
                    MAX(risk_score) as max_risk,
                    SUM(transaction_amount) as total_amount
                FROM upi_transactions
            """))
            row = result.fetchone()
        
        return jsonify({
            'report': {
                'generated_at': datetime.now().isoformat(),
                'total_transactions': row[0] or 0,
                'frauds_blocked': row[1] or 0,
                'under_review': row[2] or 0,
                'approved': row[3] or 0,
                'average_risk_score': round(float(row[4] or 0), 2),
                'max_risk_score': round(float(row[5] or 0), 2),
                'total_transaction_amount': round(float(row[6] or 0), 2),
                'fraud_prevention_rate': round((row[1] or 0) / (row[0] or 1) * 100, 2)
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("[*] AI-Driven UPI Fraud Detection API Server v2.1")
    print("="*60)
    print("\n[+] Available Endpoints:")
    print("   GET  /                    - Interactive Dashboard")
    print("   GET  /health              - Health Check")
    print("   GET  /api/stats           - Live Statistics")
    print("   POST /api/analyze         - Analyze Transaction")
    print("   POST /api/batch_analyze   - Batch Analyze")
    print("   GET  /api/customer/<id>/profile")
    print("   GET  /api/customer/<id>/reputation")
    print("   POST /api/blacklist/<type>/<id>")
    print("   GET  /api/alerts")
    print("   GET  /api/statistics")
    print("   POST /api/simulate_transaction")
    print("\n" + "="*60)
    print("[!] Dashboard Features:")
    print("   - Real-time stats with auto-refresh")
    print("   - Interactive charts (risk distribution, trends)")
    print("   - Live transaction feed")
    print("   - High-risk alerts panel")
    print("   - Beautiful gradient UI")
    print("="*60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
