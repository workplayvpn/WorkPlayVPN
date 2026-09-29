"""Record Happ-supplied labels for an owned device, never the raw HWID."""

import hashlib
import hmac
import re
from collections.abc import Mapping, Sequence

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.vpn_device import VpnDevice


def _clean(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    value = " ".join(value.split())
    if not value or len(value) > limit or any(ord(char) < 32 for char in value):
        return None
    return value


def hwid_digest(value: str | None) -> str | None:
    if not value or len(value) > 256:
        return None
    return hmac.new(settings.subscription_token_secret.encode(),
                    value.encode(), hashlib.sha256).hexdigest()


def record_happ_device_metadata(
    database: Session,
    devices: Sequence[VpnDevice],
    headers: Mapping[str, str],
    *, selected_device: VpnDevice | None = None,
) -> None:
    if not headers.get("user-agent", "").lower().startswith("happ/"):
        return
    model = _clean(headers.get("x-device-model"), 100)
    os_name = _clean(headers.get("x-device-os"), 50)
    if model is None or os_name is None:
        return
    version = _clean(headers.get("x-ver-os"), 12)
    if version and re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,3}){0,2}", version):
        os_name = f"{os_name} {version}"
    digest = hwid_digest(headers.get("x-hwid"))

    device = selected_device
    if device is None and digest is not None:
        matches = [item for item in devices if item.happ_hwid_digest == digest]
        if len(matches) == 1:
            device = matches[0]
    if device is None and len(devices) == 1:
        device = devices[0]
    if device is None or device not in devices:
        return

    changed = False
    for field, value in (("happ_device_model", model), ("happ_device_os", os_name),
                         ("happ_hwid_digest", digest)):
        if value is not None and getattr(device, field) != value:
            setattr(device, field, value)
            changed = True
    if changed:
        database.commit()
