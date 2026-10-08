"""Public invoice numbers are separate from internal database IDs."""
import secrets
from sqlalchemy import or_, select
from app.models.payment import Payment


MIN_ORDER_NUMBER = 100_000_000_000
ORDER_NUMBER_RANGE = 900_000_000_000


def generate_robokassa_invoice_id(database):
    for _ in range(20):
        number = str(MIN_ORDER_NUMBER + secrets.randbelow(ORDER_NUMBER_RANGE))
        occupied = database.scalar(select(Payment.id).where(
            Payment.provider == "robokassa",
            or_(Payment.provider_payment_id == f"robokassa:{number}", Payment.id == int(number)),
        ))
        if occupied is None:
            return number
    raise RuntimeError("Could not allocate a unique invoice number")


def public_order_number(payment):
    provider_id = getattr(payment, "provider_payment_id", None)
    if payment.provider == "robokassa" and provider_id and provider_id.startswith("robokassa:"):
        number = provider_id.removeprefix("robokassa:")
        if number.isdecimal():
            return number
    return str(payment.id)
