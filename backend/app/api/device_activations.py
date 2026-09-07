from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.internal_auth import require_internal_api_secret
from app.core.config import settings
from app.db.dependencies import get_db
from app.schemas.device_activation import (
    DeviceActivationComplete,
    DeviceActivationCompleteRead,
    DeviceActivationCreate,
    DeviceActivationRead,
)
from app.services.device_activation_service import (
    device_activation_service,
)
from app.services.vpn_node_profile_service import (
    vpn_node_profile_service,
)
from app.services.vpn_profile_link_builder import (
    vpn_profile_link_builder,
)


router = APIRouter(
    prefix="/device-activations",
    tags=["device-activations"],
)


def build_activation_url(
    raw_token: str,
) -> str:
    return (
        f"{settings.activation_base_url.rstrip('/')}/"
        f"{raw_token}"
    )


@router.post(
    "",
    response_model=DeviceActivationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_internal_api_secret),
    ],
)
def create_device_activation(
    payload: DeviceActivationCreate,
    database: Session = Depends(get_db),
):
    activation, raw_token = (
        device_activation_service.create_activation(
            database=database,
            telegram_id=payload.telegram_id,
            location_code=payload.location_code,
        )
    )

    activation_url = build_activation_url(raw_token)

    return DeviceActivationRead(
        activation_id=activation.id,
        expires_at=activation.expires_at,
        activation_url=activation_url,
    )


@router.post(
    "/{token}/complete",
    response_model=DeviceActivationCompleteRead,
)
def complete_device_activation(
    token: str,
    payload: DeviceActivationComplete,
    database: Session = Depends(get_db),
):
    device, node = (
        device_activation_service.complete_activation(
            database=database,
            raw_token=token,
            device_name=payload.device_name,
        )
    )

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

    vless_url = None

    if reality_profile is not None:
        vless_url = vpn_profile_link_builder.build_vless_link(
            device=device,
            node=node,
            profile=reality_profile,
        )

    return DeviceActivationCompleteRead(
        device_id=device.id,
        device_name=device.device_name,
        node_code=node.code,
        node_name=node.name,
        platform=payload.platform,
        vless_url=vless_url,
    )