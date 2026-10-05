from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.gift_checkout import gift_checkout_is_current
from app.services.payment_providers.robokassa import RobokassaProvider


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    # These tests use only plain invoice objects and a DB-free return route.
    yield


@pytest.fixture
def invoice(monkeypatch):
    for key, value in {"robokassa_merchant_login":"new_shop", "robokassa_password_1":"new_test_password",
                       "robokassa_is_test":True, "payment_mode":"test", "robokassa_hash_algorithm":"md5"}.items():
        monkeypatch.setattr(settings, key, value)
    result = RobokassaProvider().create_payment(amount=Decimal("199"), currency="RUB", description="Gift",
                                              idempotency_key="checkout-test", metadata={"payment_id":"25"})
    return SimpleNamespace(id=25, amount=Decimal("199"), provider="robokassa", confirmation_url=result.confirmation_url)


def test_new_shop_invoice_is_usable(invoice):
    assert gift_checkout_is_current(invoice)


@pytest.mark.parametrize("setting,value", [("robokassa_merchant_login","another_shop"),
    ("robokassa_password_1","rotated_password"), ("robokassa_hash_algorithm","sha256"), ("robokassa_is_test",False)])
def test_old_shop_or_credentials_are_not_reused(invoice, monkeypatch, setting, value):
    monkeypatch.setattr(settings, setting, value)
    assert not gift_checkout_is_current(invoice)


def test_wrong_amount_or_invoice_is_rejected(invoice):
    invoice.amount=Decimal("99")
    assert not gift_checkout_is_current(invoice)
    invoice.amount=Decimal("199"); invoice.id=26
    assert not gift_checkout_is_current(invoice)


def test_untrusted_url_and_duplicate_fields_are_rejected(invoice):
    original=invoice.confirmation_url
    invoice.confirmation_url=original.replace("auth.robokassa.ru", "untrusted.example")
    assert not gift_checkout_is_current(invoice)
    invoice.confirmation_url=original+"&MerchantLogin=new_shop"
    assert not gift_checkout_is_current(invoice)


def test_non_robokassa_checkout_unchanged():
    assert gift_checkout_is_current(SimpleNamespace(provider="test"))


def test_browser_return_only_redirects_to_bot():
    with TestClient(app) as client:
        result=client.get("/pay/return?InvId=25&OutSum=199.00",follow_redirects=False)
    assert result.status_code == 302
    assert result.headers["location"] == "https://t.me/workplayvpn_bot?start=payment_return"
    assert result.headers["cache-control"] == "no-store"
