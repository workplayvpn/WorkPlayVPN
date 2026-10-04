"""Credential-free Happ profiles explaining device access restrictions."""
import base64

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.services.happ_subscription_info import subscription_presentation

LIMIT_MESSAGE = (
    "Превышен лимит устройств. Либо удалите устройство из списка, "
    "либо докупите слоты. Затем обновите подписку в Happ."
)

REMOVED_MESSAGE = (
    "Устройство удалено из личного кабинета. Доступ на этом устройстве "
    "заблокирован. Обновление подписки не восстанавливает доступ."
)


def is_device_removed_error(error: HTTPException) -> bool:
    return (error.status_code == 403
            and error.detail == "Device was removed; add it again from your account")


def is_device_limit_error(error: HTTPException) -> bool:
    return error.status_code == 409 and error.detail == "Device limit reached"


def device_limit_response(tier: str) -> JSONResponse:
    return device_block_response(tier)


def device_block_response(tier: str, *, removed: bool = False) -> JSONResponse:
    # Use a valid Xray configuration with only a blackhole outbound. Never
    # return an existing device's credentials or a working fallback endpoint.
    # This is a notice profile, not a registered account device.
    message = REMOVED_MESSAGE if removed else LIMIT_MESSAGE
    label = "Устройство заблокировано" if removed else "Превышен лимит устройств"
    encoded = base64.b64encode(message.encode("utf-8")).decode("ascii")
    headers = subscription_presentation(access_tier=tier)
    headers.update({
        "Cache-Control": "no-store", "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
        "announce": f"base64:{encoded}",
        "subscription-always-hwid-enable": "1",
        "profile-update-interval": "1",
    })
    return JSONResponse(content=[{
        "remarks": label,
        "meta": {"serverDescription": message},
        "inbounds": [{"tag": "socks", "listen": "127.0.0.1", "port": 10808,
                      "protocol": "socks", "settings": {"auth": "noauth", "udp": True}}],
        "outbounds": [{"tag": "blocked", "protocol": "blackhole", "settings": {}}],
        "routing": {"rules": [{"type": "field", "network": "tcp,udp",
                                  "outboundTag": "blocked"}]},
    }], headers=headers)
