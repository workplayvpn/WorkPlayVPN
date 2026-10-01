from app.api.internal_auth import require_internal_api_secret
from app.services.catalog import available_plans
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.location import Location
from app.models.plan import Plan
from app.models.vpn_node import VpnNode
from app.schemas.catalog import LocationRead, PlanRead


router = APIRouter(
    prefix="/catalog",
    tags=["catalog"],
)


@router.get(
    "/plans",
    response_model=list[PlanRead],
)
def get_plans(
    database: Session = Depends(get_db),
):
    return database.scalars(
        select(Plan)
        .where(Plan.is_active.is_(True), Plan.access_tier == "basic")
        .order_by(Plan.duration_days)
    ).all()


@router.get(
    "/locations",
    response_model=list[LocationRead],
)
def get_locations(
    database: Session = Depends(get_db),
):
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

    return [
        LocationRead(
            id=location.id,
            code=location.code,
            name=location.name,
            is_active=location.is_active,
            available=(location.id in available_location_ids),
        )
        for location in locations
    ]


@router.get("/users/{telegram_id}/plans", response_model=list[PlanRead],
            dependencies=[Depends(require_internal_api_secret)])
def get_user_plans(telegram_id: int, database: Session = Depends(get_db)):
    return available_plans(database, telegram_id, include_trial=True)
