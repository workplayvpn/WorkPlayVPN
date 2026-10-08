"""Do not reuse gift invoices signed for an old Robokassa shop/configuration."""
import hmac
from urllib.parse import parse_qs, urlsplit

from app.core.config import settings
from app.services.payment_order_number import public_order_number
from app.services.payment_providers.robokassa import calculate_robokassa_signature


def gift_checkout_is_current(payment) -> bool:
    if payment.provider != "robokassa":
        return True
    parsed = urlsplit(payment.confirmation_url or "")
    params = parse_qs(parsed.query, keep_blank_values=True)
    if parsed.scheme != "https" or parsed.hostname != "auth.robokassa.ru":
        return False
    required = ("MerchantLogin", "OutSum", "InvId", "SignatureValue")
    if any(len(params.get(key, [])) != 1 for key in required):
        return False
    value = {key: values[0] for key, values in params.items()}
    if (value["MerchantLogin"] != settings.robokassa_merchant_login
            or value["InvId"] != public_order_number(payment)
            or value["OutSum"] != format(payment.amount, ".2f")
            or (value.get("IsTest") == "1") != settings.robokassa_is_test
            or not settings.robokassa_password_1):
        return False
    # The provider currently signs only these four fields (no Receipt/Shp_*).
    expected = calculate_robokassa_signature(
        parts=[value["MerchantLogin"], value["OutSum"], value["InvId"], settings.robokassa_password_1],
        algorithm=settings.robokassa_hash_algorithm,
    )
    return hmac.compare_digest(expected.lower(), value["SignatureValue"].lower())
