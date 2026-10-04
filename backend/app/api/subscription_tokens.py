from sqlalchemy import select
from app.models.vpn_device import VpnDevice
from app.api.happ_auto_route import auto_route_allowed
from fastapi import APIRouter, Depends, Response, status
from base64 import b64encode
from datetime import UTC, datetime
from app.api.mini_app import get_mini_app_key
from app.services.branded_qr import qr_png
from app.services.telegram_webapp_auth import TelegramWebAppAuthResult, TelegramWebAppUser
from sqlalchemy.orm import Session

from app.api.internal_auth import require_internal_api_secret
from app.core.config import settings
from app.services.entitlements import active_entitlements
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


@router.get("/happ/{tier}")
def get_bot_happ_key(tier: str, telegram_id: int, response: Response,
                     database: Session = Depends(get_db)):
    """Internal bot calls only: Telegram sender ID, never a client-supplied URL."""
    auth = TelegramWebAppAuthResult(
        user=TelegramWebAppUser(id=telegram_id, first_name=""), auth_date=datetime.now(UTC))
    data = get_mini_app_key(tier=tier, response=response, auth=auth,
                            database=database)
    if "Vary" in response.headers:
        del response.headers["Vary"]
    return {"url": data["url"], "qr_png_base64": b64encode(qr_png(data["url"])).decode("ascii")}


def build_token_response(
    *,
    token,
    raw_token: str,
    database: Session | None = None,
) -> SubscriptionTokenRead:
    entitlements = active_entitlements(database, token.user_id) if database is not None else {}
    mobile_token = (
        subscription_token_service.scoped_token(token, "mobile")
        if "mobile" in entitlements else None
    )
    # Keep the historical fields usable for a Mobile-only customer.
    if "basic" not in entitlements and mobile_token:
        raw_token = mobile_token
    subscription_url = (
        f"{settings.subscription_base_url.rstrip('/')}/"
        f"{raw_token}"
    )

    connect_url = (
        f"{settings.connect_base_url.rstrip('/')}/"
        f"{raw_token}"
    )

    basic_devices = {}
    mobile_devices = {}
    if database is not None:
        devices = database.scalars(select(VpnDevice).where(
            VpnDevice.user_id == token.user_id, VpnDevice.is_active.is_(True))
            .order_by(VpnDevice.id)).all()
        base = settings.connect_base_url.rstrip("/")
        for device in devices:
            if "basic" in entitlements:
                basic_devices[str(device.id)] = f"{base}/device/{device.id}/{raw_token}"
            if mobile_token:
                if auto_route_allowed(token.user_id) and device.mobile_xray_uuid and device.mobile_xray_email:
                    mobile_devices[str(device.id)] = f"{base}/auto/routed/device/{device.id}/{mobile_token}"
                else:
                    mobile_devices[str(device.id)] = f"{base}/{mobile_token}"

    return SubscriptionTokenRead(
        basic_device_connect_urls=basic_devices,
        mobile_device_connect_urls=mobile_devices,
        access_key=raw_token,
        subscription_url=subscription_url,
        connect_url=connect_url,
        created_at=token.created_at,
        rotated_at=token.rotated_at,
        mobile_access_key=mobile_token,
        mobile_subscription_url=(
            f"{settings.subscription_base_url.rstrip('/')}/{mobile_token}"
            if mobile_token else None
        ),
        mobile_connect_url=(
            f"{settings.connect_base_url.rstrip('/')}/{mobile_token}"
            if mobile_token else None
        ),
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
        database=database,
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
        database=database,
    )
