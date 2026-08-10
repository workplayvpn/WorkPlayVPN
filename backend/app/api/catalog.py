from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.location import Location
from app.models.plan import Plan
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
    return database.scalars(
        select(Location)
        .where(Location.is_active.is_(True))
        .order_by(Location.name)
    ).all()