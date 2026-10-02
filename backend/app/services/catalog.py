from sqlalchemy import select
from app.models.plan import Plan
from app.models.user import User
from app.models.subscription import Subscription
from app.services.entitlements import active_entitlements
from app.services.mobile_rollout import mobile_pilot_allowed


def available_plans(database, telegram_id, *, include_trial=False):
    user_id = database.scalar(select(User.id).where(User.telegram_id == telegram_id))
    condition = Plan.code.like("standard_%") | Plan.code.like("mobile_%")
    if include_trial and user_id is not None:
        used = database.scalar(select(Subscription.id).join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.user_id == user_id, Plan.code == "trial_1d").limit(1))
        include_trial = used is None and not active_entitlements(database, user_id)
    if include_trial:
        condition = condition | (Plan.code == "trial_1d")
    plans = database.scalars(select(Plan).where(Plan.is_active.is_(True), condition)
        .order_by(Plan.access_tier, Plan.duration_days)).all()
    return [plan for plan in plans if plan.access_tier != "mobile" or
            (user_id is not None and mobile_pilot_allowed(user_id))]
