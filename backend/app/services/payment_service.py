import secrets
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.services.subscription_service import (
    subscription_service,
)


class PaymentService:

    def create_payment(
        self,
        database: Session,
        telegram_id: int,
        plan_code: str,
        provider: str,
        idempotency_key: str | None = None,
    ) -> Payment:
        user = database.scalar(
            select(User).where(
                User.telegram_id == telegram_id,
                User.is_active.is_(True),
            )
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        plan = database.scalar(
            select(Plan).where(
                Plan.code == plan_code,
                Plan.is_active.is_(True),
            )
        )

        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found",
            )

        if plan.code == "trial_1d":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trial plan does not require payment",
            )

        if idempotency_key is None:
            idempotency_key = secrets.token_urlsafe(32)

        existing_payment = database.scalar(
            select(Payment).where(
                Payment.idempotency_key == idempotency_key,
            )
        )

        if existing_payment is not None:
            return existing_payment

        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status="pending",
        )

        payment = Payment(
            user_id=user.id,
            subscription_id=0,
            provider=provider,
            provider_payment_id=None,
            idempotency_key=idempotency_key,
            status="pending",
            amount=plan.price_amount,
            currency=plan.currency,
            confirmation_url=None,
        )

        try:
            database.add(subscription)
            database.flush()

            payment.subscription_id = subscription.id

            database.add(payment)
            database.commit()
            database.refresh(payment)

        except IntegrityError:
            database.rollback()

            existing_payment = database.scalar(
                select(Payment).where(
                    Payment.idempotency_key == idempotency_key,
                )
            )

            if existing_payment is not None:
                return existing_payment

            raise

        return payment

    def mark_succeeded(
        self,
        database: Session,
        payment_id: int,
        provider_payment_id: str | None = None,
    ) -> Payment:
        payment = database.scalar(
            select(Payment)
            .where(
                Payment.id == payment_id,
            )
            .with_for_update()
        )

        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )

        if payment.status == "succeeded":
            return payment

        if payment.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment cannot be completed",
            )

        subscription = database.get(
            Subscription,
            payment.subscription_id,
        )

        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Subscription not found",
            )

        payment.status = "succeeded"
        payment.paid_at = datetime.now(UTC)

        if provider_payment_id is not None:
            payment.provider_payment_id = (
                provider_payment_id
            )

        try:
            database.flush()

            subscription_service.activate_subscription(
                database=database,
                subscription=subscription,
            )

            database.refresh(payment)

        except IntegrityError as exc:
            database.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Provider payment already processed",
            ) from exc

        except Exception:
            database.rollback()
            raise

        return payment

    def mark_canceled(
        self,
        database: Session,
        payment_id: int,
    ) -> Payment:
        payment = database.scalar(
            select(Payment)
            .where(
                Payment.id == payment_id,
            )
            .with_for_update()
        )

        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )

        if payment.status == "canceled":
            return payment

        if payment.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment cannot be canceled",
            )

        payment.status = "canceled"

        database.commit()
        database.refresh(payment)

        return payment


payment_service = PaymentService()