from app.schemas.mini_app import MiniAppRegionRead, MiniAppRegionUpdate
from app.services.vpn_device_service import vpn_device_service
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.internal_auth import require_internal_api_secret
from app.db.dependencies import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead


router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[
        Depends(require_internal_api_secret),
    ],
)


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    database: Session = Depends(get_db),
):
    existing_user = database.scalar(
        select(User).where(User.telegram_id == payload.telegram_id)
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    user = User(**payload.model_dump())

    database.add(user)
    database.commit()
    database.refresh(user)

    return user


@router.get(
    "/{telegram_id}",
    response_model=UserRead,
)
def get_user(
    telegram_id: int,
    database: Session = Depends(get_db),
):
    user = database.scalar(
        select(User).where(User.telegram_id == telegram_id)
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user

@router.patch("/{telegram_id}/region", response_model=MiniAppRegionRead)
def change_user_region(telegram_id: int, payload: MiniAppRegionUpdate,
                       database: Session = Depends(get_db)):
    location = vpn_device_service.change_account_location(
        database=database, telegram_id=telegram_id,
        location_code=payload.location_code)
    return MiniAppRegionRead(code=location.code, name=location.name)
