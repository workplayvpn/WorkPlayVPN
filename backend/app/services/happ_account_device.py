"""Resolve one physical Happ installation behind a shared subscription URL."""

from collections.abc import Mapping

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.entitlements import active_entitlements
from app.services.happ_device_metadata import (
    _clean, apply_happ_device_metadata, hwid_digest,
)
from app.services.subscription_service import subscription_service
from app.services.vpn_device_service import vpn_device_service


def resolve_happ_account_device(
    database: Session, user_id: int, tier: str, headers: Mapping[str, str],
    *, device_id: int | None = None,
) -> VpnDevice:
    """Fail closed without HWID; serialize enrollment against the user slot limit.

    HWID is client supplied, not cryptographic proof of hardware ownership.
    Never reuse another installation's VPN credentials as a fallback.
    """
    raw_hwid = headers.get("x-hwid")
    if (not raw_hwid or not raw_hwid.strip() or len(raw_hwid) > 256
            or any(ord(char) < 32 for char in raw_hwid)):
        raise HTTPException(403, "Happ device identifier required; update Happ")
    digest = hwid_digest(raw_hwid)
    user = database.scalar(select(User).where(
        User.id == user_id, User.is_active.is_(True),
    ).with_for_update())
    if user is None:
        raise HTTPException(404, "User not found")
    if subscription_service.expire_stale_subscriptions(database, user.id):
        user = database.scalar(select(User).where(User.id == user_id).with_for_update())
    if tier not in active_entitlements(database, user.id):
        raise HTTPException(403, "Active subscription required")

    devices = list(database.scalars(select(VpnDevice).where(
        VpnDevice.user_id == user.id,
    ).order_by(VpnDevice.id)).all())
    matches = [d for d in devices if d.happ_hwid_digest == digest
               or d.client_instance_id == digest]
    active_matches = [d for d in matches if d.is_active]
    if len(active_matches) > 1:
        raise HTTPException(409, "Ambiguous device registration")
    if device_id is not None:
        device = next((d for d in devices if d.id == device_id and d.is_active), None)
        if device is None:
            if any(d.id == device_id and not d.is_active for d in matches):
                raise HTTPException(403, "Device was removed; add it again from your account")
            raise HTTPException(404, "Device not found")
        if device.happ_hwid_digest and device.happ_hwid_digest != digest:
            raise HTTPException(403, "Device belongs to another Happ installation")
        if active_matches and active_matches[0].id != device.id:
            raise HTTPException(409, "Installation already registered on another device")
    elif active_matches:
        device = active_matches[0]
    elif matches:
        # A deletion is a revocation. Neither an import nor a background refresh
        # of the shared key may silently undo the owner's removal.
        raise HTTPException(403, "Device was removed; add it again from your account")
    else:
        # Unidentified legacy rows are not silently assigned to a stranger.
        # Bind them using their existing per-device instruction link instead.
        node_query = select(VpnNode).where(VpnNode.is_active.is_(True))
        if user.preferred_location_id is not None:
            node_query = node_query.where(VpnNode.location_id == user.preferred_location_id)
        elif devices:
            node_query = node_query.where(VpnNode.id == devices[0].node_id)
        node = database.scalar(node_query.order_by(VpnNode.id).limit(1))
        if node is None:
            raise HTTPException(503, "VPN node unavailable")
        model = _clean(headers.get("x-device-model"), 70) or "Happ"
        device = vpn_device_service.create_device(
            database=database, telegram_id=user.telegram_id, node_code=node.code,
            device_name=f"{model} [{digest[:12]}]", client_instance_id=digest,
            happ_headers=headers,
        )
    if apply_happ_device_metadata(device, headers):
        database.commit()
    return device
