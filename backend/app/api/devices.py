from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.internal_auth import require_internal_api_secret
from app.db.dependencies import get_db
from app.models.vpn_node import VpnNode
from app.schemas.vpn_device import VpnDeviceCreate, VpnDeviceRead
from app.services.vpn_device_service import vpn_device_service
from app.services.vpn_node_profile_service import (
    vpn_node_profile_service,
)
from app.services.vpn_profile_link_builder import (
    vpn_profile_link_builder,
)


router = APIRouter(
    prefix="/devices",
    tags=["devices"],
    dependencies=[
        Depends(require_internal_api_secret),
    ],
)


def build_device_vless_url(
    database: Session,
    device,
    node: VpnNode,
) -> str | None:
    profiles = (
        vpn_node_profile_service.get_active_profiles_for_nodes(
            database=database,
            node_ids={node.id},
        )
    )

    reality_profile = next(
        (
            profile
            for profile in profiles
            if profile.node_id == node.id
            and profile.protocol == "vless"
            and profile.network == "tcp"
            and profile.security == "reality"
        ),
        None,
    )

    if reality_profile is None:
        return None

    return vpn_profile_link_builder.build_vless_link(
        device=device,
        node=node,
        profile=reality_profile,
    )


@router.post(
    "",
    response_model=VpnDeviceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_device(
    payload: VpnDeviceCreate,
    database: Session = Depends(get_db),
):
    device = vpn_device_service.create_device(
        database=database,
        telegram_id=payload.telegram_id,
        node_code=payload.node_code,
        device_name=payload.device_name,
    )

    node = database.get(
        VpnNode,
        device.node_id,
    )

    if node is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="VPN node not found after device creation",
        )

    vless_url = build_device_vless_url(
        database=database,
        device=device,
        node=node,
    )

    return VpnDeviceRead(
        id=device.id,
        device_name=device.device_name,
        node_code=node.code,
        node_name=node.name,
        is_active=device.is_active,
        created_at=device.created_at,
        vless_url=vless_url,
    )


@router.get(
    "/users/{telegram_id}",
    response_model=list[VpnDeviceRead],
)
def get_devices(
    telegram_id: int,
    database: Session = Depends(get_db),
):
    devices = vpn_device_service.get_devices(
        database=database,
        telegram_id=telegram_id,
    )

    result: list[VpnDeviceRead] = []

    for device in devices:
        node = database.get(
            VpnNode,
            device.node_id,
        )

        if node is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="VPN node not found",
            )

        vless_url = build_device_vless_url(
            database=database,
            device=device,
            node=node,
        )

        result.append(
            VpnDeviceRead(
                id=device.id,
                device_name=device.device_name,
                node_code=node.code,
                node_name=node.name,
                is_active=device.is_active,
                created_at=device.created_at,
                vless_url=vless_url,
            )
        )

    return result


@router.delete(
    "/{device_id}",
    response_model=VpnDeviceRead,
)
def remove_device(
    device_id: int,
    telegram_id: int,
    database: Session = Depends(get_db),
):
    device = vpn_device_service.remove_device(
        database=database,
        telegram_id=telegram_id,
        device_id=device_id,
    )

    node = database.get(
        VpnNode,
        device.node_id,
    )

    if node is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="VPN node not found",
        )

    return VpnDeviceRead(
        id=device.id,
        device_name=device.device_name,
        node_code=node.code,
        node_name=node.name,
        is_active=device.is_active,
        created_at=device.created_at,
        vless_url=None,
    )