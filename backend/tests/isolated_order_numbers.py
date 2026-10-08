"""Actual order/provider/webhook functions with DB doubles; no network or credentials."""
import ast
import asyncio
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as NS
from urllib.parse import urlencode, parse_qs, urlsplit
from unittest.mock import Mock, patch
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'app'


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Column:
    def __init__(self, name): self.name = name
    def __eq__(self, value): return (self.name, value)


class Payment:
    id, provider, provider_payment_id = map(Column, ['id', 'provider', 'provider_payment_id'])


class Query:
    def __init__(self, target): self.target, self.conditions = target, []
    def where(self, *conditions): self.conditions.extend(conditions); return self


def load(relative, namespace, names=None):
    tree = ast.parse((ROOT / relative).read_text())
    tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))
                 and (names is None or getattr(n, 'name', None) in names)]
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n.decorator_list = []
            n.returns = None
            for arg in n.args.args: arg.annotation = None
            n.args.defaults = []
    exec(compile(ast.fix_missing_locations(tree), relative, 'exec'), namespace)
    return namespace


def environment():
    settings = NS(payment_mode='live', robokassa_is_test=False, robokassa_merchant_login='shop',
                  robokassa_password_1='fixture-password-1', robokassa_password_2='fixture-password-2',
                  robokassa_hash_algorithm='md5')
    namespace = dict(settings=settings, hashlib=hashlib, hmac=hmac, secrets=secrets,
        datetime=datetime, timedelta=timedelta, timezone=timezone, Decimal=Decimal,
        InvalidOperation=__import__('decimal').InvalidOperation, urlencode=urlencode, parse_qs=parse_qs,
        select=Query, or_=lambda *x: x, Payment=Payment, HTTPException=HTTPException,
        Session=object, PaymentProvider=object, ProviderPaymentResult=lambda **kw: NS(**kw),
        status=NS(HTTP_503_SERVICE_UNAVAILABLE=503, HTTP_400_BAD_REQUEST=400,
                  HTTP_500_INTERNAL_SERVER_ERROR=500, HTTP_401_UNAUTHORIZED=401,
                  HTTP_404_NOT_FOUND=404, HTTP_409_CONFLICT=409))
    load('services/payment_order_number.py', namespace)
    load('services/payment_providers/robokassa.py', namespace)
    namespace['payment_service'] = NS(mark_succeeded=Mock(side_effect=lambda **kw: NS(**kw)))
    load('services/robokassa_webhook.py', namespace)
    return namespace


class OrderNumberChecks(unittest.TestCase):
    def setUp(self): self.env = environment()

    def test_twelve_digit_random_numbers(self):
        db = Mock(); db.scalar.return_value = None
        numbers = [self.env['generate_robokassa_invoice_id'](db) for _ in range(500)]
        self.assertTrue(all(len(n) == 12 and n.isdecimal() for n in numbers))
        self.assertEqual(len(set(numbers)), 500)

    def test_collision_is_retried(self):
        db = Mock(); db.scalar.side_effect = [46, None]
        with patch.object(secrets, 'randbelow', side_effect=[123, 456]):
            number = self.env['generate_robokassa_invoice_id'](db)
        self.assertEqual(number, '100000000456')
        self.assertEqual(db.scalar.call_count, 2)

    def test_collision_limit(self):
        db = Mock(); db.scalar.return_value = 46
        with self.assertRaises(RuntimeError): self.env['generate_robokassa_invoice_id'](db)
        self.assertEqual(db.scalar.call_count, 20)

    def test_public_number_and_legacy_fallback(self):
        p = NS(id=46, provider='robokassa', provider_payment_id='robokassa:422415962178')
        self.assertEqual(self.env['public_order_number'](p), '422415962178')
        p.provider_payment_id = 'robokassa:46'
        self.assertEqual(self.env['public_order_number'](p), '46')
        p.provider_payment_id = None
        self.assertEqual(self.env['public_order_number'](p), '46')

    def invoice(self, number='422415962178'):
        return self.env['RobokassaProvider']().create_payment(amount=Decimal('199'), currency='RUB',
            description='Basic', idempotency_key='fixture-request',
            metadata={'payment_id': '46', 'invoice_id': number})

    def test_provider_signs_public_number_and_stores_mapping(self):
        invoice = self.invoice()
        q = parse_qs(urlsplit(invoice.confirmation_url).query)
        self.assertEqual(q['InvId'], ['422415962178'])
        self.assertEqual(q['SignatureValue'], [hashlib.md5(b'shop:199.00:422415962178:fixture-password-1').hexdigest()])
        self.assertEqual(invoice.provider_payment_id, 'robokassa:422415962178')
        self.assertNotIn('IsTest', q)

    def test_test_mode_preserved(self):
        self.env['settings'].payment_mode = 'test'
        self.env['settings'].robokassa_is_test = True
        q = parse_qs(urlsplit(self.invoice().confirmation_url).query)
        self.assertEqual(q['IsTest'], ['1'])

    def payload(self, number='422415962178', amount='199.00'):
        return dict(InvId=number, OutSum=amount, SignatureValue=hashlib.md5(
            f'{amount}:{number}:fixture-password-2'.encode()).hexdigest())

    def db(self, number='422415962178'):
        payment = NS(id=46, provider='robokassa', amount=Decimal('199'), currency='RUB',
                     provider_payment_id=f'robokassa:{number}')
        db = Mock(); db.scalar.return_value = payment; db.get.return_value = None
        return db

    def test_random_invoice_routes_to_internal_payment(self):
        service = self.env['RobokassaWebhookService']()
        payload = self.payload()
        service.verify_signature(payload)
        result = service.handle_result(database=self.db(), payload=payload)
        self.assertEqual(result.payment_id, 46)
        self.assertEqual(result.provider_payment_id, 'robokassa:422415962178')

    def test_legacy_invoice_still_routes(self):
        db = self.db('46'); db.get.return_value = db.scalar.return_value; db.scalar.return_value = None
        result = self.env['RobokassaWebhookService']().handle_result(database=db, payload=self.payload('46'))
        self.assertEqual(result.payment_id, 46)

    def test_wrong_amount_does_not_activate(self):
        service = self.env['RobokassaWebhookService']()
        payload = self.payload(amount='1.00')
        service.verify_signature(payload)
        with self.assertRaises(HTTPException) as error:
            service.handle_result(database=self.db(), payload=payload)
        self.assertEqual(error.exception.status_code, 409)
        self.env['payment_service'].mark_succeeded.assert_not_called()

    def test_wrong_signature_does_not_activate(self):
        payload = self.payload(); payload['InvId'] = '422415962179'
        with self.assertRaises(HTTPException): self.env['RobokassaWebhookService']().verify_signature(payload)
        self.env['payment_service'].mark_succeeded.assert_not_called()

    def test_acknowledgement_uses_public_number(self):
        self.env['robokassa_webhook_service'] = self.env['RobokassaWebhookService']()
        self.env['PlainTextResponse'] = lambda **kw: NS(**kw)
        load('api/payment_webhooks.py', self.env, {'robokassa_webhook'})
        payload = self.payload()
        class Request:
            async def body(self): return urlencode(payload).encode()
        response = asyncio.run(self.env['robokassa_webhook'](Request(), self.db()))
        self.assertEqual(response.content, 'OK422415962178')


if __name__ == '__main__': unittest.main(verbosity=2)
