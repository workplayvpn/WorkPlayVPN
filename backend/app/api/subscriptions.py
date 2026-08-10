from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionRead,
    SubscriptionStatusRead,
)


router = APIRouter(
    prefix="/subscriptions",
    tags=["subscriptions"],
)


@router.post(
    "",
    response_model=SubscriptionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription(
    payload: SubscriptionCreate,
    database: Session = Depends(get_db),
):
    user = database.scalar(
        select(User).where(
            User.telegram_id == payload.telegram_id
        )
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    plan = database.scalar(
        select(Plan).where(
            Plan.code == payload.plan_code,
            Plan.is_active.is_(True),
        )
    )

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    now = datetime.now(UTC)

    if plan.code == "trial_3d":
        previous_trial = database.scalar(
            select(Subscription)
            .join(
                Plan,
                Subscription.plan_id == Plan.id,
            )
            .where(
                Subscription.user_id == user.id,
                Plan.code == "trial_3d",
            )
        )

        if previous_trial is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Trial already used",
            )

        active_subscription = database.scalar(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status == "active",
            )
        )

        if active_subscription is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already has active subscription",
            )

        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status="active",
            starts_at=now,
            expires_at=now + timedelta(
                days=plan.duration_days
            ),
        )
    else:
        pending_subscription = database.scalar(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.plan_id == plan.id,
                Subscription.status == "pending",
            )
        )

        if pending_subscription is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment already pending",
            )

        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status="pending",
        )

    database.add(subscription)
    database.commit()
    database.refresh(subscription)

    return subscription

@router.get(
    "/users/{telegram_id}/current",
    response_model=SubscriptionStatusRead,
)
def get_current_subscription(
    telegram_id: int,
    database: Session = Depends(get_db),
):
    user = database.scalar(
        select(User).where(
            User.telegram_id == telegram_id
        )
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    subscription = database.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status == "active",
        )
        .order_by(Subscription.created_at.desc())
    )

    now = datetime.now(UTC)

    if (
        subscription is not None
        and subscription.expires_at is not None
        and subscription.expires_at <= now
    ):
        subscription.status = "expired"
        database.commit()
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

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    plan = database.get(
        Plan,
        subscription.plan_id,
    )

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Subscription plan not found",
        )

    total_device_limit = (
        plan.device_limit + user.extra_device_slots
    )

    return SubscriptionStatusRead(
        status=subscription.status,
        plan_code=plan.code,
        plan_name=plan.name,
        starts_at=subscription.starts_at,
        expires_at=subscription.expires_at,
        included_devices=plan.device_limit,
        extra_device_slots=user.extra_device_slots,
        total_device_limit=total_device_limit,
    )