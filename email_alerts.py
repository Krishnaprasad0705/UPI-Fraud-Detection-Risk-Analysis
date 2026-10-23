import sys
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
"""Configurable, non-blocking, idempotent email alerts for severe fraud-risk events."""

import os
import ssl
import smtplib
import threading
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path


def _load_project_dotenv():
    """Load simple KEY=VALUE settings from this project's optional .env file."""
    env_file = Path(__file__).resolve().with_name('.env')
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


class SevereRiskEmailAlert:
    """Sends administrator email for a severe-risk transaction.

    Credentials come strictly from environment variables, never source control.
    A transaction triggers an alert when:
    - Its classification is BLOCK, HIGH, or CRITICAL, OR
    - Its final risk score is >= UPI_EMAIL_SEVERE_RISK_THRESHOLD (70 by default).
    """

    def __init__(self):
        self._sent_alert_keys = set()
        self._lock = threading.Lock()
        self._load_sent_history()
        self.reload_config()

    def _get_history_file(self):
        return Path(__file__).resolve().with_name('.alerts_dispatched.log')

    def _load_sent_history(self):
        try:
            h_file = self._get_history_file()
            if h_file.exists():
                for line in h_file.read_text(encoding='utf-8').splitlines():
                    parts = line.strip().split('\t')
                    if parts and parts[0]:
                        self._sent_alert_keys.add(parts[0])
        except Exception:
            pass

    def _record_sent_key(self, key):
        with self._lock:
            self._sent_alert_keys.add(key)
            try:
                h_file = self._get_history_file()
                with open(h_file, 'a', encoding='utf-8') as f:
                    f.write(f"{key}\t{datetime.now().isoformat()}\n")
            except Exception:
                pass

    def reload_config(self):
        _load_project_dotenv()
        # Support both standard naming and UPI-prefixed naming
        self.host = os.getenv('SMTP_HOST') or os.getenv('UPI_SMTP_HOST', '')
        raw_port = os.getenv('SMTP_PORT') or os.getenv('UPI_SMTP_PORT', '587')
        try:
            self.port = int(raw_port)
        except ValueError:
            self.port = 587
        self.username = os.getenv('SMTP_USERNAME') or os.getenv('UPI_SMTP_USERNAME', '')
        self.password = os.getenv('SMTP_PASSWORD') or os.getenv('UPI_SMTP_PASSWORD', '')
        self.sender = os.getenv('SMTP_FROM') or os.getenv('UPI_SMTP_FROM') or self.username
        self.recipient = os.getenv('ALERT_EMAIL_TO') or os.getenv('UPI_ALERT_RECIPIENT', '2312024@nec.edu.in')
        
        raw_threshold = os.getenv('UPI_EMAIL_SEVERE_RISK_THRESHOLD', '70')
        try:
            self.threshold = float(raw_threshold)
        except ValueError:
            self.threshold = 70.0
        
        self.starttls = os.getenv('UPI_SMTP_STARTTLS', 'true').lower() != 'false'

    @property
    def is_configured(self):
        self.reload_config()
        return bool(self.host and self.username and self.password and self.recipient)

    def is_severe(self, result):
        """Determine if a transaction result requires an urgent alert."""
        if not result or not isinstance(result, dict):
            return False
        self.reload_config()
        cls = str(result.get('classification', '')).upper()
        try:
            score = float(result.get('risk_score') or 0)
        except (ValueError, TypeError):
            score = 0.0
        return cls in ['BLOCK', 'HIGH', 'CRITICAL'] or score >= self.threshold

    def _get_dedup_key(self, transaction, result):
        """Construct a unique idempotency key for deduplication."""
        txn_id = transaction.get('transaction_id') or result.get('transaction_id')
        if txn_id:
            return f"id:{txn_id}"
        cust = transaction.get('customer_id') or result.get('customer_id') or 'anon'
        amt = round(float(transaction.get('transaction_amount', result.get('transaction_amount', 0)) or 0), 2)
        hour = transaction.get('transaction_hour', datetime.now().hour)
        return f"fp:{cust}:{amt}:{hour}"

    def _build_html_email(self, txn_id_str, customer_id, amount, risk_score, severity, decision, rules_list, time_str):
        rules_html = "".join(f"<li style='margin-bottom: 6px;'>⚠️ {rule}</li>" for rule in rules_list)
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #0b0f1a; color: #f8fafc; margin: 0; padding: 20px; }}
                .card {{ background: linear-gradient(135deg, #111827, #0b0f1a); border: 1px solid #ef4444; border-radius: 12px; padding: 24px; max-width: 620px; margin: 0 auto; box-shadow: 0 10px 30px rgba(239, 68, 68, 0.25); }}
                .header-row {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(239, 68, 68, 0.3); padding-bottom: 12px; margin-bottom: 16px; }}
                .badge {{ display: inline-block; background-color: #ef4444; color: #ffffff; font-weight: bold; padding: 6px 14px; border-radius: 20px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }}
                .score-box {{ background: rgba(239, 68, 68, 0.12); border-left: 4px solid #ef4444; padding: 12px 16px; margin: 18px 0; border-radius: 4px; }}
                .data-table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 14px; }}
                .data-table td {{ padding: 8px 4px; border-bottom: 1px solid #1f2937; color: #cbd5e1; }}
                .data-table td.label {{ color: #94a3b8; font-weight: 600; width: 42%; }}
                .notice-box {{ background: rgba(249, 115, 22, 0.1); border-left: 3px solid #f97316; padding: 10px 14px; border-radius: 4px; margin: 16px 0; color: #fdba74; font-size: 13px; }}
                .btn {{ display: inline-block; background: #00e5ff; color: #0b0f1a; text-decoration: none; padding: 10px 22px; border-radius: 6px; font-weight: bold; margin-top: 15px; text-transform: uppercase; font-size: 13px; letter-spacing: 0.5px; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="header-row">
                    <h2 style="color: #ef4444; margin: 0; font-size: 20px;">🚨 [{severity} RISK ALERT] UPI Transaction</h2>
                    <span class="badge">{decision}</span>
                </div>
                <p style="color: #cbd5e1; font-size: 14px; line-height: 1.5; margin-top: 0;">
                    A high-risk UPI transaction was intercepted by the AI-Driven Fraud Detection Engine.
                </p>
                
                <div class="score-box">
                    <div style="font-size: 22px; font-weight: bold; color: #f87171;">Risk Score: {risk_score:.2f}%</div>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">Severity: {severity} (Threshold: &ge; {self.threshold}%)</div>
                </div>

                <table class="data-table">
                    <tr><td class="label">Transaction ID:</td><td><strong>#{txn_id_str}</strong></td></tr>
                    <tr><td class="label">Customer ID:</td><td><strong>{customer_id}</strong></td></tr>
                    <tr><td class="label">Transaction Amount:</td><td><strong>INR {amount:,.2f}</strong></td></tr>
                    <tr><td class="label">Detection Timestamp:</td><td>{time_str}</td></tr>
                    <tr><td class="label">Engine Decision:</td><td style="color: #ef4444; font-weight: bold;">{decision}</td></tr>
                </table>

                <h4 style="color: #f1f5f9; margin: 16px 0 8px 0; font-size: 14px;">Triggered Attack Vectors / Rules:</h4>
                <ul style="color: #fca5a5; padding-left: 20px; margin: 0; font-size: 13px;">
                    {rules_html}
                </ul>

                <div class="notice-box">
                    <strong>⚠️ Security Recommendation:</strong> Perform immediate verification before clearing funds or unblocking account credentials.
                </div>

                <div style="text-align: center; margin-top: 20px;">
                    <a href="http://localhost:5000" class="btn">Open SOC Operations Console</a>
                </div>
            </div>
        </body>
        </html>
        """

    def send(self, transaction, result):
        """Deliver one email alert with idempotency and robust error handling."""
        self.reload_config()
        if not self.is_severe(result):
            return {'sent': False, 'reason': 'not_severe'}

        # Deduplication check
        dedup_key = self._get_dedup_key(transaction, result)
        with self._lock:
            if dedup_key in self._sent_alert_keys:
                return {'sent': False, 'reason': 'duplicate_suppressed', 'key': dedup_key}

        if not self.is_configured:
            return {
                'sent': False,
                'reason': 'email_not_configured',
                'details': 'Set SMTP_USERNAME & SMTP_PASSWORD in .env'
            }

        customer_id = transaction.get('customer_id', result.get('customer_id', 'unknown'))
        amount = float(transaction.get('transaction_amount', result.get('transaction_amount', 0)) or 0)
        risk_score = float(result.get('risk_score') or 0)
        decision = str(result.get('classification', 'BLOCK')).upper()
        severity = 'CRITICAL' if risk_score >= 85 or decision == 'BLOCK' else 'HIGH'
        txn_id = transaction.get('transaction_id') or result.get('transaction_id') or 'PENDING_DB_INSERT'
        
        rules = result.get('triggered_rules') or ['High-risk anomaly pattern detected']
        rules_list = rules if isinstance(rules, list) else [str(rules)]
        rules_text = ', '.join(rules_list)
        time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')

        message = EmailMessage()
        message['Subject'] = f'🚨 [{severity} FRAUD ALERT] UPI Transaction #{txn_id} | Score: {risk_score:.1f}% | INR {amount:,.2f}'
        message['From'] = self.sender or self.username
        message['To'] = self.recipient
        
        # Plain text content
        message.set_content(
            f'🚨 [{severity} FRAUD ALERT] UPI Transaction #{txn_id}\n\n'
            f'Severity: {severity}\n'
            f'Engine Decision: {decision}\n'
            f'Risk Score: {risk_score:.2f}%\n'
            f'Timestamp: {time_str}\n'
            f'Customer ID: {customer_id}\n'
            f'Amount: INR {amount:,.2f}\n'
            f'Triggered Vectors: {rules_text}\n\n'
            f'Security Recommendation: Immediate transaction review recommended before releasing funds.\n'
            f'Fraud Console: http://localhost:5000\n'
        )

        # HTML rich content
        html_content = self._build_html_email(str(txn_id), customer_id, amount, risk_score, severity, decision, rules_list, time_str)
        message.add_alternative(html_content, subtype='html')

        try:
            with smtplib.SMTP(self.host, self.port, timeout=12) as smtp:
                smtp.ehlo()
                if self.starttls:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(message)
            
            # Record successful dispatch for deduplication
            self._record_sent_key(dedup_key)
            return {'sent': True, 'recipient': self.recipient, 'key': dedup_key, 'severity': severity}
        except (OSError, smtplib.SMTPException) as error:
            # Log failure cleanly without leaking credentials
            return {'sent': False, 'reason': f'smtp_delivery_error: {type(error).__name__}'}

    def send_in_background(self, transaction, result, callback=None):
        """Keep fraud processing responsive while SMTP delivery occurs in a thread."""
        def deliver():
            outcome = self.send(transaction, result)
            if callback:
                try:
                    callback(outcome)
                except Exception:
                    pass

        threading.Thread(target=deliver, daemon=True, name='severe-risk-email').start()

    def send_test_email(self, custom_recipient=None):
        """Send a clearly labeled test notification without creating a fake fraud event."""
        self.reload_config()
        if not self.is_configured:
            return {
                'sent': False,
                'reason': 'email_not_configured',
                'details': f'Missing credentials. host={bool(self.host)}, user={bool(self.username)}, pwd={bool(self.password)}'
            }
        
        target = custom_recipient or self.recipient
        time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        
        message = EmailMessage()
        message['Subject'] = '✅ [TEST] UPI Fraud Detection - Email Alert Verification'
        message['From'] = self.sender or self.username
        message['To'] = target
        
        body_text = (
            f"UPI Fraud Detection System - Connectivity Test\n\n"
            f"Status: Operational\n"
            f"Timestamp: {time_str}\n"
            f"Configured Recipient: {target}\n"
            f"SMTP Host: {self.host}:{self.port}\n\n"
            f"This is an automated test notification to verify that SMTP email delivery is configured correctly.\n"
            f"No actual fraud event was generated.\n"
        )
        message.set_content(body_text)

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family:'Segoe UI',sans-serif; background:#0b0f1a; color:#f8fafc; padding:20px;">
            <div style="background:#111827; border:1px solid #00e5ff; border-radius:10px; padding:24px; max-width:550px; margin:0 auto;">
                <h2 style="color:#00e5ff; margin:0 0 12px 0;">🛡️ UPI Fraud Shield - Email System Verified</h2>
                <p style="color:#cbd5e1; font-size:14px;">This test confirms that your SMTP credentials and network dispatch channel are working properly.</p>
                <div style="background:rgba(0,229,255,0.08); border-left:3px solid #00e5ff; padding:10px 14px; margin:15px 0; font-size:13px;">
                    <div><strong>Recipient:</strong> {target}</div>
                    <div><strong>Host:</strong> {self.host}:{self.port}</div>
                    <div><strong>Time:</strong> {time_str}</div>
                </div>
                <p style="font-size:12px; color:#94a3b8;">High-risk (risk score &ge; {self.threshold}% or BLOCK) transactions will be dispatched here in real-time.</p>
            </div>
        </body>
        </html>
        """
        message.add_alternative(html_body, subtype='html')

        try:
            with smtplib.SMTP(self.host, self.port, timeout=12) as smtp:
                smtp.ehlo()
                if self.starttls:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(message)
            return {'sent': True, 'recipient': target, 'message': 'Test email sent successfully'}
        except Exception as error:
            return {'sent': False, 'reason': f'{type(error).__name__}: {str(error)}'}


if __name__ == '__main__':
    import sys
    print("=" * 60)
    print("UPI Fraud Detection - Email Alert Configuration Test")
    print("=" * 60)
    alert_mgr = SevereRiskEmailAlert()
    print(f"Recipient:  {alert_mgr.recipient}")
    print(f"SMTP Host:  {alert_mgr.host}:{alert_mgr.port}")
    print(f"SMTP User:  {alert_mgr.username or '(not set)'}")
    print(f"Configured: {alert_mgr.is_configured}")
    print(f"Threshold:  Score >= {alert_mgr.threshold}% or BLOCK")
    print("-" * 60)
    if '--test' in sys.argv or '-t' in sys.argv:
        print("Sending test email to configured recipient...")
        res = alert_mgr.send_test_email()
        print("Result:", res)
    else:
        print("To send a test email, run: python email_alerts.py --test")
    print("=" * 60)
