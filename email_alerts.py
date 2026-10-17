"""Configurable, non-blocking email alerts for severe fraud-risk events."""

import os
import smtplib
import ssl
import threading
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path


def _load_project_dotenv():
    """Load simple KEY=VALUE settings from this project's optional .env file."""
    env_file = Path(__file__).with_name('.env')
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        # Allow reloading updated values
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


class SevereRiskEmailAlert:
    """Sends administrator email for a severe-risk transaction.

    Credentials deliberately come only from environment variables, never source
    control. A transaction is severe when its final risk score is at least
    ``UPI_EMAIL_SEVERE_RISK_THRESHOLD`` (70 by default) or it is classified as
    BLOCK.
    """

    def __init__(self):
        self.reload_config()

    def reload_config(self):
        _load_project_dotenv()
        self.host = os.getenv('UPI_SMTP_HOST', '')
        self.port = int(os.getenv('UPI_SMTP_PORT', '587'))
        self.username = os.getenv('UPI_SMTP_USERNAME', '')
        self.password = os.getenv('UPI_SMTP_PASSWORD', '')
        self.sender = os.getenv('UPI_SMTP_FROM', self.username)
        self.recipient = os.getenv('UPI_ALERT_RECIPIENT', '2312024@nec.edu.in')
        self.threshold = float(os.getenv('UPI_EMAIL_SEVERE_RISK_THRESHOLD', '70'))

    @property
    def is_configured(self):
        self.reload_config()
        return bool(self.host and self.username and self.password and self.recipient)

    def is_severe(self, result):
        self.reload_config()
        return (
            result.get('classification') == 'BLOCK'
            or float(result.get('risk_score') or 0) >= self.threshold
        )

    def _build_html_email(self, customer_id, amount, risk_score, classification, rules_list, time_str):
        rules_html = "".join(f"<li style='margin-bottom: 6px;'>⚠️ {rule}</li>" for rule in rules_list)
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
                .card {{ background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid #ef4444; border-radius: 12px; padding: 24px; max-width: 600px; margin: 0 auto; box-shadow: 0 10px 25px rgba(239, 68, 68, 0.2); }}
                .badge {{ display: inline-block; background-color: #ef4444; color: #ffffff; font-weight: bold; padding: 6px 14px; border-radius: 20px; font-size: 14px; text-transform: uppercase; }}
                .score-box {{ background: rgba(239, 68, 68, 0.1); border-left: 4px solid #ef4444; padding: 12px 16px; margin: 18px 0; border-radius: 4px; }}
                .data-table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                .data-table td {{ padding: 8px 0; border-bottom: 1px solid #334155; color: #cbd5e1; }}
                .data-table td.label {{ color: #94a3b8; font-weight: 600; width: 40%; }}
                .btn {{ display: inline-block; background: #3b82f6; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h2 style="color: #ef4444; margin: 0;">🚨 High-Risk UPI Fraud Alert</h2>
                    <span class="badge">{classification}</span>
                </div>
                <p style="color: #cbd5e1; font-size: 15px;">A critical high-risk transaction has been flagged by the AI Fraud Detection Engine.</p>
                
                <div class="score-box">
                    <div style="font-size: 24px; font-weight: bold; color: #f87171;">Risk Score: {risk_score:.2f}%</div>
                    <div style="font-size: 13px; color: #94a3b8;">Threshold: {self.threshold}%</div>
                </div>

                <table class="data-table">
                    <tr><td class="label">Customer ID:</td><td><strong>{customer_id}</strong></td></tr>
                    <tr><td class="label">Transaction Amount:</td><td><strong>INR {amount:,.2f}</strong></td></tr>
                    <tr><td class="label">Detection Timestamp:</td><td>{time_str}</td></tr>
                    <tr><td class="label">Action Status:</td><td style="color: #ef4444; font-weight: bold;">{classification}</td></tr>
                </table>

                <h4 style="color: #f1f5f9; margin: 16px 0 8px 0;">Triggered Risk Factors:</h4>
                <ul style="color: #fca5a5; padding-left: 20px; margin: 0;">
                    {rules_html}
                </ul>

                <div style="text-align: center;">
                    <a href="http://localhost:5000" class="btn">Open Fraud Operations Dashboard</a>
                </div>
            </div>
        </body>
        </html>
        """

    def send(self, transaction, result):
        """Deliver one email. Returns a delivery status; does not raise."""
        self.reload_config()
        if not self.is_severe(result):
            return {'sent': False, 'reason': 'not_severe'}
        if not self.is_configured:
            return {'sent': False, 'reason': 'email_not_configured (Set UPI_SMTP_USERNAME & UPI_SMTP_PASSWORD in .env)'}

        customer_id = transaction.get('customer_id', result.get('customer_id', 'unknown'))
        amount = float(transaction.get('transaction_amount', result.get('transaction_amount', 0)) or 0)
        risk_score = float(result.get('risk_score') or 0)
        rules = result.get('triggered_rules') or ['No rule details available']
        rules_list = rules if isinstance(rules, list) else [str(rules)]
        rules_text = ', '.join(rules_list)
        time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')

        message = EmailMessage()
        message['Subject'] = f'🚨 [UPI FRAUD ALERT] {result.get("classification", "SEVERE")} | Score: {risk_score:.1f}% | INR {amount:,.2f}'
        message['From'] = self.sender or self.username
        message['To'] = self.recipient
        
        # Plain text fallback
        message.set_content(
            f'🚨 HIGH-RISK UPI FRAUD ALERT\n\n'
            f'Status: {result.get("classification", "SEVERE")}\n'
            f'Risk Score: {risk_score:.2f}%\n'
            f'Time: {time_str}\n'
            f'Customer ID: {customer_id}\n'
            f'Amount: INR {amount:,.2f}\n'
            f'Triggered Rules: {rules_text}\n\n'
            f'Access the dashboard: http://localhost:5000\n'
        )

        # HTML rich version
        html_content = self._build_html_email(customer_id, amount, risk_score, result.get("classification", "SEVERE"), rules_list, time_str)
        message.add_alternative(html_content, subtype='html')

        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
                smtp.ehlo()
                if os.getenv('UPI_SMTP_STARTTLS', 'true').lower() != 'false':
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(message)
            return {'sent': True, 'recipient': self.recipient}
        except (OSError, smtplib.SMTPException) as error:
            return {'sent': False, 'reason': str(error)}

    def send_in_background(self, transaction, result, callback=None):
        """Keep fraud processing responsive while SMTP delivery occurs."""
        def deliver():
            outcome = self.send(transaction, result)
            if callback:
                callback(outcome)

        threading.Thread(target=deliver, daemon=True, name='severe-risk-email').start()
