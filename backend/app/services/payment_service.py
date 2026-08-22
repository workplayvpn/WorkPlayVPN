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
from app.services.payment_providers import payment_provider_registry
from app.services.subscription_service import subscription_service


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

        provider_service = payment_provider_registry.get(
            provider
        )

        # -------------------------------------------------
        # 1. Обычная идемпотентность конкретного запроса.
        # -------------------------------------------------

        existing_payment = database.scalar(
            select(Payment).where(
                Payment.idempotency_key == idempotency_key,
            )
        )

        if existing_payment is not None:
            existing_subscription = database.get(
                Subscription,
                existing_payment.subscription_id,
            )

            if existing_subscription is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Payment subscription not found",
                )

            if (
                existing_payment.user_id != user.id
                or existing_payment.provider != provider
                or existing_subscription.plan_id != plan.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Idempotency key already used "
                        "for another payment"
                    ),
                )

            if existing_payment.provider_payment_id is not None:
                return existing_payment

            payment = existing_payment

        else:
            # -------------------------------------------------
            # 2. Блокируем пользователя.
            #
            # Благодаря этому два запроса с РАЗНЫМИ
            # idempotency_key не смогут одновременно
            # создать два pending Payment.
            # -------------------------------------------------

            locked_user = database.scalar(
                select(User)
                .where(
                    User.id == user.id,
                )
                .with_for_update()
            )

            if locked_user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            # Пока запрос ждал блокировку User,
            # другой запрос мог уже создать Payment.
            existing_payment = database.scalar(
                select(Payment)
                .where(
                    Payment.idempotency_key == idempotency_key,
                )
            )

            if existing_payment is not None:
                existing_subscription = database.get(
                    Subscription,
                    existing_payment.subscription_id,
                )

                if existing_subscription is None:
                    raise HTTPException(
                        status_code=(
                            status.HTTP_500_INTERNAL_SERVER_ERROR
                        ),
                        detail="Payment subscription not found",
                    )

                if (
                    existing_payment.user_id != locked_user.id
                    or existing_payment.provider != provider
                    or existing_subscription.plan_id != plan.id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Idempotency key already used "
                            "for another payment"
                        ),
                    )

                payment = existing_payment

            else:
                # -------------------------------------------------
                # 3. Один пользователь не должен иметь пачку
                # неоплаченных счетов.
                # -------------------------------------------------

                pending_payment = database.scalar(
                    select(Payment)
                    .where(
                        Payment.user_id == locked_user.id,
                        Payment.status == "pending",
                    )
                    .order_by(
                        Payment.created_at.desc()
                    )
                )

                if pending_payment is not None:
                    pending_subscription = database.get(
                        Subscription,
                        pending_payment.subscription_id,
                    )

                    if pending_subscription is None:
                        raise HTTPException(
                            status_code=(
                                status.HTTP_500_INTERNAL_SERVER_ERROR
                            ),
                            detail="Payment subscription not found",
                        )

                    # Тот же тариф + тот же provider:
                    # возвращаем существующий счёт.
                    if (
                        pending_subscription.plan_id == plan.id
                        and pending_payment.provider == provider
                    ):
                        payment = pending_payment

                    else:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Payment already pending",
                        )

                else:
                    subscription = Subscription(
                        user_id=locked_user.id,
                        plan_id=plan.id,
                        status="pending",
                    )

                    payment = Payment(
                        user_id=locked_user.id,
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

                        payment.subscription_id = (
                            subscription.id
                        )

                        database.add(payment)
                        database.commit()
                        database.refresh(payment)

                    except IntegrityError:
                        database.rollback()

                        payment = database.scalar(
                            select(Payment).where(
                                Payment.idempotency_key
                                == idempotency_key,
                            )
                        )

                        if payment is None:
                            raise

        # -------------------------------------------------
        # 4. Provider payment уже создан.
        # Просто возвращаем существующую ссылку.
        # -------------------------------------------------

        if payment.provider_payment_id is not None:
            return payment

        # -------------------------------------------------
        # 5. Блокируем конкретный Payment перед обращением
        # к внешнему провайдеру.
        # -------------------------------------------------

        payment = database.scalar(
            select(Payment)
            .where(
                Payment.id == payment.id,
            )
            .with_for_update()
        )

        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment not found after creation",
            )

        # Пока запрос ждал блокировку Payment,
        # другой процесс мог уже создать счёт у провайдера.
        if payment.provider_payment_id is not None:
            return payment

        try:
            provider_result = provider_service.create_payment(
                amount=payment.amount,
                currency=payment.currency,
                description=f"Work&PlayVPN {plan.name}",
                idempotency_key=payment.idempotency_key,
                metadata={
                    "payment_id": str(payment.id),
                    "subscription_id": str(
                        payment.subscription_id
                    ),
                    "user_id": str(user.id),
                },
            )

            payment.provider_payment_id = (
                provider_result.provider_payment_id
            )

            payment.confirmation_url = (
                provider_result.confirmation_url
            )

            database.commit()
            database.refresh(payment)

        except HTTPException:
            database.rollback()
            raise

        except Exception as exc:
            database.rollback()

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Payment provider unavailable",
            ) from exc

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
            payment.provider_payment_id = provider_payment_id

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