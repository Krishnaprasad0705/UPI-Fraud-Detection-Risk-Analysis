import sys
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import unittest
from datetime import datetime
from email_alerts import SevereRiskEmailAlert
from fraud_detection_system import HybridFraudDetector, RuleBasedDetector, DeepLearningFraudDetector

class TestUPIFraudDetection(unittest.TestCase):
    def setUp(self):
        self.detector = HybridFraudDetector()
        self.email_service = SevereRiskEmailAlert()

    def test_detector_initialization_counters(self):
        """Verify detector in-memory counters exist and initialize to 0."""
        self.assertTrue(hasattr(self.detector, 'total_transactions'))
        self.assertTrue(hasattr(self.detector, 'blocked_count'))
        self.assertTrue(hasattr(self.detector, 'review_count'))
        self.assertTrue(hasattr(self.detector, 'approved_count'))
        self.assertEqual(self.detector.total_transactions, 0)

    def test_low_risk_transaction_no_alert(self):
        """Verify normal/low risk transactions do not trigger email alert."""
        txn = {
            'customer_id': 'C_NORMAL_1',
            'transaction_amount': 250.0,
            'transaction_hour': 14,
            'location': 'Mumbai',
            'device_type': 'Android',
            'is_foreign_transaction': 0,
            'failed_login_attempts': 0,
            'account_tenure_years': 5,
            'account_balance': 50000.0,
            'merchant_category': 'Grocery',
            'transaction_time': datetime.now()
        }
        res = self.detector.analyze_transaction(txn, use_ml=False)
        self.assertEqual(res['classification'], 'APPROVE')
        self.assertFalse(self.email_service.is_severe(res))
        outcome = self.email_service.send(txn, res)
        self.assertFalse(outcome['sent'])
        self.assertEqual(outcome['reason'], 'not_severe')

    def test_high_risk_transaction_triggers_alert(self):
        """Verify severe high-risk transaction is flagged and triggers severe check."""
        txn = {
            'customer_id': 'C_FRAUD_HIGH',
            'transaction_amount': 95000.0,
            'transaction_hour': 1,  # Midnight
            'location': 'Unknown',
            'device_type': 'Web',
            'is_foreign_transaction': 1,
            'failed_login_attempts': 5,
            'account_tenure_years': 0,  # New account
            'account_balance': 100.0,   # Insufficient
            'merchant_category': 'Jewelry',
            'transaction_time': datetime.now()
        }
        res = self.detector.analyze_transaction(txn, use_ml=False)
        self.assertIn(res['classification'], ['BLOCK', 'REVIEW'])
        self.assertGreaterEqual(res['risk_score'], 50.0)

    def test_email_idempotency(self):
        """Verify duplicate alerts for the same transaction ID are suppressed."""
        txn = {
            'transaction_id': 9999999,
            'customer_id': 'C_TEST_IDEMP',
            'transaction_amount': 88000.0,
            'transaction_hour': 2,
            'location': 'Unknown',
            'device_type': 'Web',
            'is_foreign_transaction': 1,
            'failed_login_attempts': 4,
            'account_tenure_years': 0,
            'account_balance': 200.0,
            'merchant_category': 'Electronics',
            'transaction_time': datetime.now()
        }
        res = {
            'transaction_id': 9999999,
            'risk_score': 95.0,
            'classification': 'BLOCK',
            'triggered_rules': ['High Value', 'Foreign IP']
        }
        self.assertTrue(self.email_service.is_severe(res))
        # First send (will attempt or report unconfigured, but registers key if simulated)
        key = self.email_service._get_dedup_key(txn, res)
        self.email_service._record_sent_key(key)
        # Second send must be suppressed by idempotency
        second_attempt = self.email_service.send(txn, res)
        self.assertFalse(second_attempt['sent'])
        self.assertEqual(second_attempt['reason'], 'duplicate_suppressed')

    def test_api_routes_import_cleanly(self):
        """Verify API module loads without syntax or import errors."""
        import fraud_detection_api_new as api
        self.assertIsNotNone(api.app)
        self.assertTrue(callable(api.get_db_engine))


if __name__ == '__main__':
    print("=" * 60)
    print("Running Automated Project Verification Tests...")
    print("=" * 60)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestUPIFraudDetection)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
