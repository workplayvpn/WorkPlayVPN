from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.subscription import Subscription


def active_entitlements(
    database: Session,
    user_id: int,
    *,
    now: datetime | None = None,
    exclude_subscription_id: int | None = None,
) -> dict[str, tuple[Subscription, Plan]]:
    """Return the live subscription for each access tier.

    Expired rows can remain ACTIVE until the expiry worker runs; they never
    grant access during that interval.
    """
    now = now or datetime.now(UTC)
    query = (
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            or_(Subscription.expires_at.is_(None), Subscription.expires_at > now),
        )
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
    )
    if exclude_subscription_id is not None:
        query = query.where(Subscription.id != exclude_subscription_id)
    rows = database.execute(query).all()
    result: dict[str, tuple[Subscription, Plan]] = {}
    for subscription, plan in rows:
        result.setdefault(plan.access_tier, (subscription, plan))
    return result


def shared_device_limit(
    entitlements: dict[str, tuple[Subscription, Plan]],
    extra_slots: int,
) -> int:
    # One set of physical devices serves both products; slots are not added.
    return max((plan.device_limit for _, plan in entitlements.values()), default=0) + (
        extra_slots if entitlements else 0
    )
