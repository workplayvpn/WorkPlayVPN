import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.payment_fulfillment import PaymentFulfillment
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.services.payment_providers import payment_provider_registry
from app.services.mobile_rollout import mobile_pilot_allowed
from app.services.device_slots import slot_count
from app.services.entitlements import active_entitlements
from app.services.subscription_service import subscription_service
from app.services.referrals import credit_payment
from app.services.informer import enqueue_purchase

logger = logging.getLogger(__name__)


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

        if plan.access_tier == "mobile" and not mobile_pilot_allowed(user.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found",
            )

        if slot_count(plan) and not active_entitlements(database, user.id):
            raise HTTPException(status_code=409, detail="Active subscription required")

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
                # 3. Каждый новый запрос с новым idempotency_key
                # создаёт отдельный pending-платёж.
                # -------------------------------------------------

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
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
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
                    "expires_at": (
                        payment.expires_at.isoformat()
                        if payment.expires_at
                        else ""
                    ),
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
            .execution_options(populate_existing=True)
        )

        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )

        # Повторный webhook.
        #
        # Помимо обычной идемпотентности платежа,
        # восстанавливаем fulfillment, если платёж
        # был успешно обработан раньше, но задача
        # доставки по какой-либо причине отсутствует.
        if payment.status == "succeeded":
            fulfillment = database.scalar(
                select(PaymentFulfillment).where(
                    PaymentFulfillment.payment_id == payment.id,
                )
            )

            if fulfillment is None:
                existing_subscription = database.get(Subscription, payment.subscription_id)
                existing_plan = database.get(Plan, existing_subscription.plan_id) if existing_subscription else None
                is_slots = bool(existing_plan and slot_count(existing_plan))
                fulfillment = PaymentFulfillment(
                    payment_id=payment.id,
                    user_id=payment.user_id,
                    status="delivered" if is_slots else "pending",
                    delivered_at=datetime.now(UTC) if is_slots else None,
                )

                try:
                    database.add(fulfillment)
                    database.commit()
                except IntegrityError:
                    database.rollback()

            self._cancel_other_pending_payments(
                database=database,
                succeeded_payment=payment,
            )

            database.refresh(payment)
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

        plan = database.get(Plan, subscription.plan_id)
        slots = slot_count(plan) if plan is not None else 0
        if slots:
            user = database.scalar(select(User).where(User.id == payment.user_id).with_for_update().execution_options(populate_existing=True))
            if user is None:
                raise HTTPException(status_code=404, detail="User not found")
            user.extra_device_slots += slots
            payment.status = "succeeded"
            payment.paid_at = datetime.now(UTC)
            if provider_payment_id is not None:
                payment.provider_payment_id = provider_payment_id
            subscription.status = "completed"
            database.add(PaymentFulfillment(payment_id=payment.id, user_id=user.id,
                status="delivered", delivered_at=datetime.now(UTC)))
            enqueue_purchase(database, payment, user=user, subscription=subscription, plan=plan)
            database.commit()
            database.refresh(payment)
            self._cancel_other_pending_payments(database=database, succeeded_payment=payment)
            return payment

        payment.status = "succeeded"
        payment.paid_at = datetime.now(UTC)

        if provider_payment_id is not None:
            payment.provider_payment_id = provider_payment_id

        # Создаём durable-задачу ДО активации подписки.
        #
        # activate_subscription() выполняет commit,
        # поэтому Payment, Subscription и Fulfillment
        # будут зафиксированы вместе.
        fulfillment = PaymentFulfillment(
            payment_id=payment.id,
            user_id=payment.user_id,
            status="pending",
        )

        try:
            database.add(fulfillment)
            database.flush()
            credit_payment(database, payment, plan)

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

        self._cancel_other_pending_payments(
            database=database,
            succeeded_payment=payment,
        )

        database.refresh(payment)

        return payment

    def _cancel_other_pending_payments(
        self,
        database: Session,
        *,
        succeeded_payment: Payment,
    ) -> None:
        pending_payment_ids = list(
            database.scalars(
                select(Payment.id).where(
                    Payment.user_id
                    == succeeded_payment.user_id,
                    Payment.id
                    != succeeded_payment.id,
                    Payment.status == "pending",
                )
            ).all()
        )

        for pending_payment_id in pending_payment_ids:
            try:
                pending_payment = database.scalar(
                    select(Payment)
                    .where(
                        Payment.id
                        == pending_payment_id,
                    )
                    .with_for_update()
                )

                if pending_payment is None:
                    continue

                if pending_payment.status != "pending":
                    continue

                subscription = database.get(
                    Subscription,
                    pending_payment.subscription_id,
                )

                provider_service = (
                    payment_provider_registry.get(
                        pending_payment.provider
                    )
                )

                if (
                    pending_payment.provider_payment_id
                    is not None
                ):
                    provider_service.cancel_payment(
                        provider_payment_id=(
                            pending_payment.provider_payment_id
                        ),
                    )

                pending_payment.status = "canceled"

                if (
                    subscription is not None
                    and subscription.status == "pending"
                ):
                    subscription.status = "canceled"

                database.commit()

            except Exception:
                database.rollback()

                logger.exception(
                    "Failed to cancel pending payment %s "
                    "after payment %s succeeded",
                    pending_payment_id,
                    succeeded_payment.id,
                )

    def mark_canceled(
        self,
        database: Session,
        payment_id: int,
        telegram_id: int,
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

        user = database.scalar(
            select(User).where(
                User.telegram_id == telegram_id,
            )
        )

        if user is None or payment.user_id != user.id:
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

        subscription = database.get(
            Subscription,
            payment.subscription_id,
        )

        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment subscription not found",
            )

        provider_service = payment_provider_registry.get(
            payment.provider
        )

        if payment.provider_payment_id is not None:
            provider_service.cancel_payment(
                provider_payment_id=payment.provider_payment_id,
            )

        payment.status = "canceled"

        if subscription.status == "pending":
            subscription.status = "canceled"

        try:
            database.commit()
            database.refresh(payment)

        except Exception:
            database.rollback()
            raise

        return payment


payment_service = PaymentService()
