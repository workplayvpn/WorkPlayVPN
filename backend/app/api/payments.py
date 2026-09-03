from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.dependencies import get_db
from app.schemas.payment import (
    PaymentCancel,
    PaymentCreate,
    PaymentRead,
)
from app.services.payment_service import payment_service


router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)


@router.post(
    "",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    payload: PaymentCreate,
    database: Session = Depends(get_db),
):
    provider = (
        payload.provider
        or settings.payment_default_provider
    )

    return payment_service.create_payment(
        database=database,
        telegram_id=payload.telegram_id,
        plan_code=payload.plan_code,
        provider=provider,
        idempotency_key=payload.idempotency_key,
    )

@router.post(
    "/{payment_id}/cancel",
    response_model=PaymentRead,
)
def cancel_payment(
    payment_id: int,
    payload: PaymentCancel,
    database: Session = Depends(get_db),
):
    return payment_service.mark_canceled(
        database=database,
        payment_id=payment_id,
        telegram_id=payload.telegram_id,
    )
