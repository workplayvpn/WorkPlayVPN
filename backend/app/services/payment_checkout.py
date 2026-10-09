"""Whether an existing invoice may still be offered for checkout."""
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from app.core.config import settings


SUBSCRIPTION_PAYMENT_TTL = timedelta(hours=2)


def effective_payment_expiry(payment):
    expires = payment.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if payment.purpose == "subscription" and payment.created_at is not None:
        created = payment.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        limit = created + SUBSCRIPTION_PAYMENT_TTL
        expires = min(expires, limit) if expires is not None else limit
    return expires


def payment_matches_environment(payment):
    if payment.provider != "robokassa" or not payment.confirmation_url:
        return True
    parsed = urlsplit(payment.confirmation_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    expected_test = settings.payment_mode == "test"
    return (
        parsed.scheme == "https"
        and parsed.hostname == "auth.robokassa.ru"
        and len(query.get("Receipt", [])) == 1
        and bool(query["Receipt"][0])
        and query.get("MerchantLogin") == [settings.robokassa_merchant_login]
        and bool(settings.robokassa_is_test) == expected_test
        and query.get("IsTest", [""]) in ([["1"]] if expected_test else [[""], ["0"]])
    )


def payment_available_for_checkout(payment):
    expires = effective_payment_expiry(payment)
    return (
        payment.status == "pending"
        and (expires is None or expires > datetime.now(UTC))
        and payment_matches_environment(payment)
    )
