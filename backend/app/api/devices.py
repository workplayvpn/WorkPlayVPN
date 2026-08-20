from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.vpn_node import VpnNode
from app.schemas.vpn_device import VpnDeviceCreate, VpnDeviceRead
from app.services.vpn_device_service import vpn_device_service
from app.services.xray_node import xray_node_service


router = APIRouter(
    prefix="/devices",
    tags=["devices"],
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

    vless_url = xray_node_service.build_vless_url(
        user_uuid=device.xray_uuid,
        node_name=node.name,
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

        vless_url = xray_node_service.build_vless_url(
            user_uuid=device.xray_uuid,
            node_name=node.name,
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