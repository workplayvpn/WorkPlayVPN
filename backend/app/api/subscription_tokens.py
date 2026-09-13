from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.internal_auth import require_internal_api_secret
from app.core.config import settings
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
    dependencies=[
        Depends(require_internal_api_secret),
    ],
)


def build_token_response(
    *,
    token,
    raw_token: str,
) -> SubscriptionTokenRead:
    subscription_url = (
        f"{settings.subscription_base_url.rstrip('/')}/"
        f"{raw_token}"
    )

    connect_url = (
        f"{settings.connect_base_url.rstrip('/')}/"
        f"{raw_token}"
    )

    return SubscriptionTokenRead(
        access_key=raw_token,
        subscription_url=subscription_url,
        connect_url=connect_url,
        created_at=token.created_at,
        rotated_at=token.rotated_at,
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

    return build_token_response(
        token=token,
        raw_token=raw_token,
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

    return build_token_response(
        token=token,
        raw_token=raw_token,
    )