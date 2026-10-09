"""Run checkout policy regressions without DB, secrets or external requests."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS
import unittest
from isolated_payment_read import load_checkout_policy


class CheckoutPolicyChecks(unittest.TestCase):
    def setUp(self):
        self.policy = load_checkout_policy()
        self.settings = self.policy['settings']
        self.settings.payment_mode = 'live'
        self.settings.robokassa_is_test = False
        self.payment = NS(status='pending', purpose='subscription', provider='robokassa',
            created_at=datetime.now(UTC), expires_at=datetime.now(UTC) + timedelta(hours=24),
            confirmation_url='https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=shop&Receipt=encoded-receipt')

    def available(self):
        return self.policy['payment_available_for_checkout'](self.payment)

    def test_test_invoice_cannot_be_resumed_in_live(self):
        self.payment.confirmation_url += '&IsTest=1'
        self.assertFalse(self.available())

    def test_live_invoice_cannot_be_resumed_in_test(self):
        self.settings.payment_mode = 'test'
        self.settings.robokassa_is_test = True
        self.assertFalse(self.available())
        self.payment.confirmation_url += '&IsTest=1'
        self.assertTrue(self.available())

    def test_merchant_and_duplicate_flags_are_checked(self):
        self.assertTrue(self.available())
        self.settings.robokassa_merchant_login = 'other'
        self.assertFalse(self.available())
        self.settings.robokassa_merchant_login = 'shop'
        self.payment.confirmation_url += '&IsTest=0&IsTest=1'
        self.assertFalse(self.available())

    def test_legacy_subscription_validity_is_capped_to_two_hours(self):
        self.assertEqual(self.policy['effective_payment_expiry'](self.payment),
                         self.payment.created_at + timedelta(hours=2))
        self.payment.created_at -= timedelta(hours=3)
        self.assertFalse(self.available())
        self.assertEqual(self.payment.status, 'pending')

    def test_existing_shorter_expiry_is_preserved(self):
        self.payment.expires_at = datetime.now(UTC) + timedelta(minutes=5)
        self.assertEqual(self.policy['effective_payment_expiry'](self.payment), self.payment.expires_at)
        self.payment.expires_at -= timedelta(minutes=6)
        self.assertFalse(self.available())

    def test_naive_timestamps_are_handled(self):
        self.payment.created_at = self.payment.created_at.replace(tzinfo=None)
        self.payment.expires_at = self.payment.expires_at.replace(tzinfo=None)
        self.assertTrue(self.available())

    def test_gift_lifetime_is_unchanged(self):
        self.payment.purpose = 'gift'
        self.assertEqual(self.policy['effective_payment_expiry'](self.payment), self.payment.expires_at)

    def test_legacy_invoice_without_receipt_is_not_reused(self):
        self.payment.confirmation_url = 'https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=shop'
        self.assertFalse(self.available())

    def test_terminal_invoice_is_unavailable(self):
        for status in ['succeeded', 'canceled', 'expired']:
            self.payment.status = status
            self.assertFalse(self.available())


if __name__ == '__main__':
    unittest.main(verbosity=2)
