from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.device_activations import build_activation_url
from app.api.telegram_webapp_auth import (
    require_telegram_webapp_auth,
)
from app.core.config import settings
from app.db.dependencies import get_db
from app.models.location import Location
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.schemas.mini_app import (
    MiniAppPaymentCreate,
    MiniAppPaymentRead,
    MiniAppActivationCreate,
    MiniAppActivationRead,
    MiniAppDeviceRead,
    MiniAppCatalogRead,
    MiniAppLocationRead,
    MiniAppPlanRead,
    MiniAppDeviceSummaryRead,
    MiniAppMeRead,
    MiniAppSubscriptionRead,
    MiniAppUserRead,
)
from app.services.device_activation_service import device_activation_service
from app.services.payment_service import payment_service
from app.services.subscription_service import subscription_service
from app.services.vpn_device_service import vpn_device_service
from app.services.payment_redirect_service import (
    payment_redirect_service,
)
from app.services.telegram_webapp_auth import (
    TelegramWebAppAuthResult,
)


router = APIRouter(
    prefix="/mini-app",
    tags=["mini-app"],
)


def get_visible_subscription(
    *,
    database: Session,
    user: User,
) -> Subscription | None:
    subscription = database.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status == "active",
        )
        .order_by(Subscription.created_at.desc())
    )

    if subscription is not None:
        subscription = subscription_service.expire_if_needed(
            database=database,
            subscription=subscription,
        )

        if subscription.status == "expired":
            subscription = None

    if subscription is None:
        subscription = database.scalar(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.status == "pending",
            )
            .order_by(Subscription.created_at.desc())
        )

    return subscription


@router.get(
    "/me",
    response_model=MiniAppMeRead,
)
def get_me(
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppMeRead:
    telegram_user = auth.user

    upsert_user = (
        insert(User)
        .values(
            telegram_id=telegram_user.id,
            first_name=telegram_user.first_name,
            username=telegram_user.username,
        )
        .on_conflict_do_update(
            index_elements=[User.telegram_id],
            set_={
                "first_name": telegram_user.first_name,
                "username": telegram_user.username,
            },
        )
    )

    database.execute(upsert_user)
    database.commit()

    user = database.scalar(
        select(User).where(
            User.telegram_id == telegram_user.id
        )
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mini App user synchronization failed",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    subscription = get_visible_subscription(
        database=database,
        user=user,
    )

    subscription_read: MiniAppSubscriptionRead | None = None
    total_device_limit = 0

    if subscription is not None:
        plan = database.get(
            Plan,
            subscription.plan_id,
        )

        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Subscription plan not found",
            )

        subscription_read = MiniAppSubscriptionRead(
            status=subscription.status,
            plan_code=plan.code,
            plan_name=plan.name,
            starts_at=subscription.starts_at,
            expires_at=subscription.expires_at,
        )

        if subscription.status == "active":
            total_device_limit = (
                plan.device_limit
                + user.extra_device_slots
            )

    active_device_count = database.scalar(
        select(func.count(VpnDevice.id)).where(
            VpnDevice.user_id == user.id,
            VpnDevice.is_active.is_(True),
        )
    )

    trial_was_used = database.scalar(
        select(Subscription.id)
        .join(
            Plan,
            Subscription.plan_id == Plan.id,
        )
        .where(
            Subscription.user_id == user.id,
            Plan.code == "trial_1d",
        )
        .limit(1)
    )

    return MiniAppMeRead(
        user=MiniAppUserRead(
            telegram_id=user.telegram_id,
            first_name=user.first_name
            or telegram_user.first_name,
            username=user.username,
        ),
        subscription=subscription_read,
        devices=MiniAppDeviceSummaryRead(
            active_count=active_device_count or 0,
            total_limit=total_device_limit,
        ),
        trial_available=(
            trial_was_used is None
            and (
                subscription is None
                or subscription.status != "active"
            )
        ),
    )


@router.get(
    "/catalog",
    response_model=MiniAppCatalogRead,
)
def get_catalog(
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppCatalogRead:
    plans = database.scalars(
        select(Plan)
        .where(
            Plan.is_active.is_(True),
            Plan.code.like("standard_%"),
        )
        .order_by(Plan.duration_days)
    ).all()

    locations = database.scalars(
        select(Location)
        .where(Location.is_active.is_(True))
        .order_by(Location.name)
    ).all()

    available_location_ids = set(
        database.scalars(
            select(VpnNode.location_id).where(
                VpnNode.is_active.is_(True)
            )
        ).all()
    )

    return MiniAppCatalogRead(
        plans=[
            MiniAppPlanRead(
                code=plan.code,
                name=plan.name,
                duration_days=plan.duration_days,
                price_amount=plan.price_amount,
                currency=plan.currency,
                device_limit=plan.device_limit,
            )
            for plan in plans
        ],
        locations=[
            MiniAppLocationRead(
                code=location.code,
                name=location.name,
                available=(
                    location.id in available_location_ids
                ),
            )
            for location in locations
        ],
    )


@router.post(
    "/trial",
    response_model=MiniAppSubscriptionRead,
    status_code=status.HTTP_201_CREATED,
)
def start_trial(
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppSubscriptionRead:
    user = database.scalar(
        select(User).where(
            User.telegram_id == auth.user.id
        )
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mini App user not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    subscription = subscription_service.create_trial(
        database=database,
        user_id=user.id,
    )

    plan = database.get(
        Plan,
        subscription.plan_id,
    )

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Trial plan not found",
        )

    return MiniAppSubscriptionRead(
        status=subscription.status,
        plan_code=plan.code,
        plan_name=plan.name,
        starts_at=subscription.starts_at,
        expires_at=subscription.expires_at,
    )


def build_mini_app_device(
    *,
    database: Session,
    device: VpnDevice,
) -> MiniAppDeviceRead:
    node = database.get(
        VpnNode,
        device.node_id,
    )

    if node is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="VPN node not found",
        )

    return MiniAppDeviceRead(
        id=device.id,
        device_name=device.device_name,
        node_code=node.code,
        node_name=node.name,
        is_active=device.is_active,
        created_at=device.created_at,
    )


@router.get(
    "/devices",
    response_model=list[MiniAppDeviceRead],
)
def get_devices(
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> list[MiniAppDeviceRead]:
    devices = vpn_device_service.get_devices(
        database=database,
        telegram_id=auth.user.id,
    )

    return [
        build_mini_app_device(
            database=database,
            device=device,
        )
        for device in devices
    ]





@router.post(
    "/device-activations",
    response_model=MiniAppActivationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_device_activation(
    payload: MiniAppActivationCreate,
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppActivationRead:
    activation, raw_token = (
        device_activation_service.create_activation(
            database=database,
            telegram_id=auth.user.id,
            location_code=payload.location_code.upper(),
        )
    )

    return MiniAppActivationRead(
        activation_id=activation.id,
        expires_at=activation.expires_at,
        activation_url=build_activation_url(raw_token),
    )


@router.delete(
    "/devices/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_device(
    device_id: int,
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> Response:
    vpn_device_service.remove_device(
        database=database,
        telegram_id=auth.user.id,
        device_id=device_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )


@router.post(
    "/payments",
    response_model=MiniAppPaymentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    payload: MiniAppPaymentCreate,
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppPaymentRead:
    payment = payment_service.create_payment(
        database=database,
        telegram_id=auth.user.id,
        plan_code=payload.plan_code,
        provider=settings.payment_default_provider,
        idempotency_key=payload.idempotency_key,
    )

    return MiniAppPaymentRead(
        id=payment.id,
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


@router.get(
    "/payments/current",
    response_model=MiniAppPaymentRead | None,
)
def get_current_payment(
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppPaymentRead | None:
    user = database.scalar(
        select(User).where(
            User.telegram_id == auth.user.id,
            User.is_active.is_(True),
        )
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    payment = database.scalar(
        select(Payment)
        .where(
            Payment.user_id == user.id,
            Payment.status == "pending",
            or_(
                Payment.expires_at.is_(None),
                Payment.expires_at > datetime.now(UTC),
            ),
        )
        .order_by(Payment.created_at.desc())
    )

    if payment is None:
        return None

    return MiniAppPaymentRead(
        id=payment.id,
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
