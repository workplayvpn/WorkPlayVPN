"""Dependency-free handler checks. No DB, credentials, network or payment provider.

Runs the real two handlers with tiny query/model doubles, NOT a PostgreSQL
integration test. Full authenticated integration coverage is in test_mini_app_payments.py.
"""
import ast
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as NS
import unittest


class Column:
    def __init__(self, name): self.name = name
    def __eq__(self, other): return (self.name, other)
    def is_(self, other): return (self.name, other)


def model(name, fields):
    return type(name, (), {field: Column(f"{name}.{field}") for field in fields})


Payment = model("Payment", ["id", "user_id", "purpose"])
User = model("User", ["id", "telegram_id", "is_active"])
Plan = model("Plan", ["id"])
Subscription = model("Subscription", ["id", "plan_id"])


class Query:
    def __init__(self, target): self.target, self.conditions = target, []
    def join(self, *_): return self
    def where(self, *conditions): self.conditions.extend(conditions); return self


class Database:
    def __init__(self, payment, active=True): self.payment, self.active = payment, active
    def scalar(self, query):
        if query.target is Plan:
            return NS(code="standard_30d", name="Basic", duration_days=30, access_tier="basic")
        assert query.target is Payment
        values = {"Payment.id": self.payment.id, "Payment.purpose": self.payment.purpose,
                  "User.telegram_id": 100, "User.is_active": self.active}
        if all(values[key] == value for key, value in query.conditions): return self.payment
        return None


class HTTPException(Exception):
    def __init__(self, status_code, detail): self.status_code, self.detail = status_code, detail


def load_checkout_policy():
    source = Path(__file__).resolve().parents[1] / "app/services/payment_checkout.py"
    tree = ast.parse(source.read_text())
    tree.body = [node for node in tree.body if not (isinstance(node, ast.ImportFrom) and node.module == "app.core.config")]
    namespace = {"settings": NS(payment_mode="test", robokassa_is_test=True, robokassa_merchant_login="shop")}
    exec(compile(tree, str(source), "exec"), namespace)
    return namespace


def load_handlers():
    source = Path(__file__).resolve().parents[1] / "app/api/mini_app.py"
    tree = ast.parse(source.read_text())
    names = {"build_payment_read", "get_payment"}
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    for node in selected:
        node.decorator_list = []
        node.returns = None
        for arg in node.args.args: arg.annotation = None
    namespace = {"Session": Database, "Payment": Payment, "User": User, "Plan": Plan,
                 "Subscription": Subscription, "select": Query, "UTC": UTC, "datetime": datetime,
                 "MiniAppPaymentRead": NS, "HTTPException": HTTPException,
                 "public_order_number": lambda p: str(p.id),
                 **load_checkout_policy(),
                 "payment_redirect_service": NS(build_public_confirmation_url=lambda p: "https://pay.example/42")}
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), str(source), "exec"), namespace)
    return namespace


class PaymentReadChecks(unittest.TestCase):
    def setUp(self):
        self.handlers = load_handlers()
        self.payment = NS(id=42, subscription_id=20, provider="test", confirmation_url="https://pay.example/42", purpose="subscription", status="pending",
                          amount=Decimal("199.00"), currency="RUB", created_at=datetime.now(UTC),
                          expires_at=datetime.now(UTC) + timedelta(hours=1), paid_at=None)
        self.database = Database(self.payment)
    def read(self, telegram_id=100, order_id=42):
        self.response = NS(headers={})
        return self.handlers["get_payment"](order_id, self.response, NS(user=NS(id=telegram_id)), self.database)
    def test_pending_metadata_and_private_cache(self):
        result = self.read()
        self.assertEqual(result.status, "pending")
        self.assertEqual(result.duration_days, 30)
        self.assertEqual(result.access_tier, "basic")
        self.assertEqual(result.amount, Decimal("199.00"))
        self.assertEqual(self.response.headers["Cache-Control"], "no-store")
    def test_foreign_missing_inactive_gift_are_hidden(self):
        for kwargs in ({"telegram_id": 101}, {"order_id": 43}):
            with self.assertRaises(HTTPException) as error: self.read(**kwargs)
            self.assertEqual(error.exception.status_code, 404)
        self.database.active = False
        with self.assertRaises(HTTPException): self.read()
        self.database.active = True
        self.payment.purpose = "gift"
        with self.assertRaises(HTTPException): self.read()
    def test_expired_is_read_only_and_unpayable(self):
        for expires in (datetime.now(UTC) - timedelta(seconds=1), datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)):
            self.payment.expires_at = expires
            result = self.read()
            self.assertEqual(result.status, "expired")
            self.assertIsNone(result.confirmation_url)
            self.assertEqual(self.payment.status, "pending")
    def test_terminal_status_never_has_payment_link(self):
        for status in ("succeeded", "canceled", "failed"):
            self.payment.status = status
            self.assertEqual(self.read().status, status)
            self.assertIsNone(self.read().confirmation_url)


if __name__ == "__main__": unittest.main(verbosity=2)
