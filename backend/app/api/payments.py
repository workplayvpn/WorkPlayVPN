from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.internal_auth import require_internal_api_secret
from app.core.config import settings
from app.db.dependencies import get_db
from app.models.payment import Payment
from app.schemas.payment import (
    PaymentCancel,
    PaymentCreate,
    PaymentRead,
)
from app.services.payment_redirect_service import (
    payment_redirect_service,
)
from app.services.payment_service import payment_service
from app.services.device_slots import device_slot_offers


router = APIRouter(
    prefix="/payments",
    tags=["payments"],
    dependencies=[
        Depends(require_internal_api_secret),
    ],
)


def build_payment_response(
    payment: Payment,
) -> PaymentRead:
    return PaymentRead(
        id=payment.id,
        subscription_id=payment.subscription_id,
        provider=payment.provider,
        provider_payment_id=payment.provider_payment_id,
        status=payment.status,
        amount=payment.amount,
        currency=payment.currency,
        confirmation_url=(
            payment_redirect_service
            .build_public_confirmation_url(payment)
        ),
        created_at=payment.created_at,
        expires_at=payment.expires_at,
        paid_at=payment.paid_at,
    )


@router.post(
    "",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    payload: PaymentCreate,
    database: Session = Depends(get_db),
) -> PaymentRead:
    provider = (
        payload.provider
        or settings.payment_default_provider
    )

    payment = payment_service.create_payment(
        database=database,
        telegram_id=payload.telegram_id,
        plan_code=payload.plan_code,
        provider=provider,
        idempotency_key=payload.idempotency_key,
    )

    return build_payment_response(payment)


@router.post(
    "/{payment_id}/cancel",
    response_model=PaymentRead,
)
def cancel_payment(
    payment_id: int,
    payload: PaymentCancel,
    database: Session = Depends(get_db),
) -> PaymentRead:
    payment = payment_service.mark_canceled(
        database=database,
        payment_id=payment_id,
        telegram_id=payload.telegram_id,
    )

    return build_payment_response(payment)

@router.get("/device-slots/{telegram_id}/offers")
def get_device_slot_offers(telegram_id: int, database: Session = Depends(get_db)):
    return device_slot_offers(database, telegram_id)
