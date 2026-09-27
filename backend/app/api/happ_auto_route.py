"""Opt-in experimental JSON subscription. Existing /sub links are untouched."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.dependencies import get_db
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.entitlements import active_entitlements
from app.services.happ_auto_route import (
    build_auto_route_config,
    build_routed_auto_config,
)
from app.services.subscription_builder import subscription_builder
from app.services.subscription_token_service import subscription_token_service
from app.services.vpn_node_profile_service import vpn_node_profile_service


router = APIRouter(prefix="/sub/auto", tags=["subscription-feed"])


def auto_route_allowed(user_id: int) -> bool:
    """No wildcard: this experimental path must be explicitly enabled."""
    return str(user_id) in {
        item.strip() for item in settings.happ_auto_route_user_ids.split(",")
        if item.strip().isdigit()
    }


@router.get("/{token}")
def get_auto_route(
    token: str,
    database: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    return _build_response(token, database, routed=False)


@router.get("/routed/{token}")
def get_routed_auto_route(
    token: str,
    database: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    return _build_response(token, database, routed=True)


@router.get("/routed/device/{device_id}/{token}")
def get_routed_auto_route_for_device(
    device_id: int,
    token: str,
    database: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    return _build_response(token, database, routed=True, device_id=device_id)


def _build_response(
    token: str, database: Session, *, routed: bool, device_id: int | None = None,
) -> JSONResponse:
    user, tier = subscription_token_service.resolve_token_scope(database, token)
    if tier != "mobile" or not auto_route_allowed(user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if "mobile" not in active_entitlements(database, user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

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
    device = devices[0]
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
        if device_id is not None:
            config[0]["remarks"] = f"Work&PlayVPN Auto RU · WP-{device_id:06d}"
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auto route profile is unavailable",
        ) from exc

    profile_title = (
        f"Work&PlayVPN Auto RU - WP-{device_id:06d}" if device_id is not None
        else "Work&PlayVPN Auto RU" if routed
        else "Work&PlayVPN Mobile Auto (pilot)"
    )
    return JSONResponse(
        content=config,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "profile-title": profile_title,
            "profile-update-interval": "3",
        },
    )
