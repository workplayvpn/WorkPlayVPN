from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.dependencies import get_db
from app.models.payment import Payment
from app.services.payment_service import payment_service


router = APIRouter(
    prefix="/test/payments",
    tags=["test-payments"],
)


@router.post("/{payment_id}/succeed")
def succeed_test_payment(
    payment_id: int,
    database: Session = Depends(get_db),
):
    if settings.payment_mode != "test":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    payment = database.get(
        Payment,
        payment_id,
    )

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    if payment.provider != "test":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only test payments can be completed here",
        )

    payment = payment_service.mark_succeeded(
        database=database,
        payment_id=payment.id,
        provider_payment_id=payment.provider_payment_id,
    )

    return {
        "id": payment.id,
        "status": payment.status,
        "provider": payment.provider,
        "provider_payment_id": payment.provider_payment_id,
    }