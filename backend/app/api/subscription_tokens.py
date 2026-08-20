from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.subscription_token import (
    SubscriptionTokenCreate,
    SubscriptionTokenRead,
)
from app.services.subscription_token_service import (
    subscription_token_service,
)


router = APIRouter(
    prefix="/subscription-tokens",
    tags=["subscription-tokens"],
)


@router.post(
    "",
    response_model=SubscriptionTokenRead,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription_token(
    payload: SubscriptionTokenCreate,
    database: Session = Depends(get_db),
):
    token, raw_token = (
        subscription_token_service.get_or_create_token(
            database=database,
            telegram_id=payload.telegram_id,
        )
    )

    subscription_url = (
        "https://sub.workplayvpn.local/"
        f"{raw_token}"
    )

    return SubscriptionTokenRead(
        subscription_url=subscription_url,
        created_at=token.created_at,
        rotated_at=token.rotated_at,
    )


@router.post(
    "/rotate",
    response_model=SubscriptionTokenRead,
)
def rotate_subscription_token(
    payload: SubscriptionTokenCreate,
    database: Session = Depends(get_db),
):
    token, raw_token = (
        subscription_token_service.rotate_token(
            database=database,
            telegram_id=payload.telegram_id,
        )
    )

    subscription_url = (
        "https://sub.workplayvpn.local/"
        f"{raw_token}"
    )

    return SubscriptionTokenRead(
        subscription_url=subscription_url,
        created_at=token.created_at,
        rotated_at=token.rotated_at,
    )