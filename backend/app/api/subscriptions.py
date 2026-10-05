from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.internal_auth import require_internal_api_secret
from app.db.dependencies import get_db
from app.models.plan import Plan
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionRead,
    SubscriptionStatusRead,
    SubscriptionTierRead,
)
from app.services.subscription_service import subscription_service
from app.services.entitlements import active_entitlements, shared_device_limit


router = APIRouter(
    prefix="/subscriptions",
    tags=["subscriptions"],
    dependencies=[
        Depends(require_internal_api_secret),
    ],
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

    if plan.code != "trial_1d":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paid plans require payment",
        )

    return subscription_service.create_trial(
        database=database,
        user_id=user.id,
    )


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

    entitlements = active_entitlements(database, user.id)
    entry = entitlements.get("basic") or entitlements.get("mobile")
    subscription = entry[0] if entry else database.scalar(
        select(Subscription)
        .where(Subscription.user_id == user.id, Subscription.status == "pending",
            ~select(Payment.id).where(Payment.subscription_id == Subscription.id, Payment.purpose == "gift").exists())
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
        shared_device_limit(entitlements, user.extra_device_slots)
        if entitlements else plan.device_limit + user.extra_device_slots
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
        active_subscriptions=[
            SubscriptionTierRead(
                access_tier=tier, plan_code=tier_plan.code,
                plan_name=tier_plan.name, starts_at=item.starts_at,
                expires_at=item.expires_at,
            )
            for tier, (item, tier_plan) in entitlements.items()
        ],
    )
