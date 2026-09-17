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
        .where(Plan.is_active.is_(True))
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
