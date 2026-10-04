from app.services.rollout_access import rollout_allowed
"""Opt-in experimental JSON subscription. Existing /sub links are untouched."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.dependencies import get_db
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.entitlements import active_entitlements
from app.services.happ_subscription_info import (
    subscription_expiry_info,
    subscription_presentation,
    hidden_settings_metadata,
)
from app.services.happ_smart_routing import build_happ_smart_routing_link
from app.services.happ_device_metadata import record_happ_device_metadata
from app.services.happ_account_device import resolve_happ_account_device
from app.services.happ_device_limit_response import device_limit_response, is_device_limit_error
from app.services.happ_auto_route import (
    build_auto_route_config,
    build_routed_auto_config,
)
from app.services.subscription_builder import subscription_builder
from app.services.subscription_token_service import subscription_token_service
from app.services.vpn_node_profile_service import vpn_node_profile_service


router = APIRouter(prefix="/sub/auto", tags=["subscription-feed"])


def auto_route_allowed(user_id: int) -> bool:
    """Public routing requires an explicit *; entitlement checks stay in place."""
    return rollout_allowed(settings.happ_auto_route_user_ids, user_id)


@router.get("/{token}")
def get_auto_route(
    token: str,
    database: Annotated[Session, Depends(get_db)],
    request: Request = None,
) -> JSONResponse:
    return _build_response(token, database, routed=False, request=request)


@router.get("/routed/{token}")
def get_routed_auto_route(
    token: str,
    database: Annotated[Session, Depends(get_db)],
    request: Request = None,
) -> JSONResponse:
    return _build_response(token, database, routed=True, request=request)


def get_routed_mobile_subscription(
    token: str, database: Session, request: Request | None = None,
) -> JSONResponse:
    """Serve the existing Mobile URL as one routed profile for canary users."""
    return _build_response(token, database, routed=True, branded=True, request=request)


@router.get("/routed/device/{device_id}/{token}")
def get_routed_auto_route_for_device(
    device_id: int,
    token: str,
    request: Request,
    database: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    return _build_response(token, database, routed=True, device_id=device_id,
                           request=request)


def _build_response(
    token: str, database: Session, *, routed: bool, device_id: int | None = None,
    branded: bool = False, request: Request | None = None,
) -> JSONResponse:
    user, tier = subscription_token_service.resolve_token_scope(database, token)
    if tier != "mobile" or not auto_route_allowed(user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    mobile_entitlement = active_entitlements(database, user.id).get("mobile")
    if mobile_entitlement is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    registered_device = None
    if settings.happ_account_device_registration_enabled:
        try:
            registered_device = resolve_happ_account_device(
                database, user.id, tier, request.headers if request is not None else {},
                device_id=device_id,
            )
        except HTTPException as error:
            if not is_device_limit_error(error):
                raise
            database.rollback()
            return device_limit_response(tier)

    query = select(VpnDevice).where(
        VpnDevice.user_id == user.id,
        VpnDevice.is_active.is_(True),
    )
    if device_id is not None:
        query = query.where(VpnDevice.id == device_id)
    devices = database.scalars(query.order_by(VpnDevice.id.asc())).all()
    if not devices:
        raise HTTPException(status_code=(status.HTTP_404_NOT_FOUND if device_id is not None
                                         else status.HTTP_503_SERVICE_UNAVAILABLE))
    device = registered_device or devices[0]
    if registered_device is not None:
        devices = [registered_device]
    if not device.mobile_xray_uuid or not device.mobile_xray_email:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    nodes = database.scalars(
        select(VpnNode).where(
            VpnNode.id == device.node_id,
            VpnNode.is_active.is_(True),
        )
    ).all()
    profiles = vpn_node_profile_service.get_active_profiles_for_nodes(
        database=database, node_ids={device.node_id},
    )
    links = subscription_builder.build(
        client="happ", device=device, nodes=nodes,
        profiles=profiles, include_happ_mobile=True,
    )
    if len(links) != 2:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    try:
        builder = build_routed_auto_config if routed else build_auto_route_config
        config = builder(*links)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auto route profile is unavailable",
        ) from exc

    profile_title = (
        "Work&PlayVPN Mobile" if branded or device_id is not None
        else "Work&PlayVPN Auto RU" if routed
        else "Work&PlayVPN Mobile Auto (pilot)"
    )
    headers = {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
        "profile-title": profile_title,
        "profile-update-interval": "3",
    }
    if branded or device_id is not None:
        headers.update(subscription_presentation(
            access_tier="mobile", routed_mobile=True,
        ))
    provider_metadata = hidden_settings_metadata(
        provider_id=settings.happ_provider_id,
        user_id=user.id,
        allowed_ids=settings.happ_hidden_settings_user_ids,
    )
    if provider_metadata:
        headers.update(provider_metadata)
        config[0]["meta"] = {"serverDescription": "Work&PlayVPN Mobile"}
    expiry_info = subscription_expiry_info(mobile_entitlement[0].expires_at)
    if expiry_info is not None:
        headers["subscription-userinfo"] = expiry_info
    if rollout_allowed(settings.happ_smart_routing_user_ids, user.id):
        headers["routing"] = build_happ_smart_routing_link()

    if request is not None:
        record_happ_device_metadata(
            database, devices, request.headers,
            selected_device=device if device_id is not None else None,
        )

    return JSONResponse(
        content=config,
        headers=headers,
    )
