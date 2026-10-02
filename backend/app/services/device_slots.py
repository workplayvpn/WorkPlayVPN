from fastapi import HTTPException
from sqlalchemy import select
from app.models.plan import Plan
from app.models.user import User
from app.services.entitlements import active_entitlements, shared_device_limit

SLOT_PACKAGES = {"device_slots_1": (1, 249), "device_slots_2": (2, 449), "device_slots_3": (3, 649)}


def slot_count(plan):
    package = SLOT_PACKAGES.get(plan.code)
    if package and plan.access_tier == "device_slots":
        return package[0]
    return 0


def device_slot_offers(database, telegram_id):
    user = database.scalar(select(User).where(User.telegram_id == telegram_id, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(404, "User not found")
    entitlements = active_entitlements(database, user.id)
    if not entitlements:
        raise HTTPException(409, "Active subscription required")
    limit = shared_device_limit(entitlements, user.extra_device_slots)
    plans = database.scalars(select(Plan).where(Plan.is_active.is_(True), Plan.access_tier == "device_slots")).all()
    return {"total_limit": limit, "offers": [
        {"code": plan.code, "slots": slot_count(plan), "price_amount": str(plan.price_amount),
         "currency": plan.currency, "new_limit": limit + slot_count(plan)}
        for plan in sorted(plans, key=lambda p: slot_count(p)) if slot_count(plan)
    ]}
