from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.telegram_webapp_auth import (
    require_telegram_webapp_auth,
)
from app.db.dependencies import get_db
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.schemas.mini_app import (
    MiniAppDeviceSummaryRead,
    MiniAppMeRead,
    MiniAppSubscriptionRead,
    MiniAppUserRead,
)
from app.services.subscription_service import subscription_service
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
        trial_available=trial_was_used is None,
    )
