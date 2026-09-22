import base64

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.dependencies import get_db
from app.models.subscription import Subscription
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.happ_smart_routing import (
    build_happ_smart_routing_link,
)
from app.services.subscription_builder import (
    subscription_builder,
)
from app.services.subscription_client_diagnostics import (
    build_subscription_client_diagnostics,
)
from app.services.subscription_token_service import (
    subscription_token_service,
)
from app.services.vpn_node_profile_service import (
    vpn_node_profile_service,
)


def detect_subscription_client(
    user_agent: str,
) -> str:
    user_agent_lower = user_agent.lower()

    if user_agent_lower.startswith("happ/"):
        return "happ"

    if "hiddifynext/" in user_agent_lower:
        return "hiddify"

    return "generic"


router = APIRouter(
    prefix="/sub",
    tags=["subscription-feed"],
)


HAPP_SUBSCRIPTION_HEADERS = {
    "profile-title": "Work&PlayVPN",
    "profile-update-interval": "12",
    "subscription-auto-update-enable": "1",
    "subscription-auto-update-open-enable": "1",
    "support-url": "https://t.me/workplayvpnteam",
}


def build_subscription_payload(
    *,
    client: str,
    links: list[str],
    routing_link: str | None = None,
) -> str:
    if client != "happ":
        return "\n".join(links)

    metadata = [
        f"#{name}: {value}"
        for name, value in HAPP_SUBSCRIPTION_HEADERS.items()
    ]

    routing = (
        [routing_link]
        if routing_link is not None
        else []
    )

    return "\n".join([*metadata, *routing, *links])


def should_enable_happ_feature(
    *,
    client: str,
    user_id: int,
    configured_user_ids: str,
) -> bool:
    if client != "happ":
        return False

    allowed_values = {
        value.strip()
        for value in configured_user_ids.split(",")
        if value.strip()
    }

    return (
        "*" in allowed_values
        or str(user_id) in allowed_values
    )


def should_include_happ_mobile_profile(
    *,
    client: str,
    user_id: int,
    configured_user_ids: str,
) -> bool:
    return should_enable_happ_feature(
        client=client,
        user_id=user_id,
        configured_user_ids=configured_user_ids,
    )


def should_include_happ_smart_routing(
    *,
    client: str,
    user_id: int,
    configured_user_ids: str,
) -> bool:
    return should_enable_happ_feature(
        client=client,
        user_id=user_id,
        configured_user_ids=configured_user_ids,
    )


@router.get(
    "/{token}",
)
def get_subscription_feed(
    token: str,
    request: Request,
    database: Session = Depends(get_db),
):
    user_agent = request.headers.get(
        "user-agent",
        "",
    )

    client = detect_subscription_client(
        user_agent
    )

    print(
        "SUBSCRIPTION_REQUEST",
        {
            "client": client,
            "user_agent": user_agent,
            "accept": request.headers.get(
                "accept",
                "",
            ),
        },
        flush=True,
    )

    if settings.subscription_client_diagnostics:
        print(
            "SUBSCRIPTION_CLIENT_DIAGNOSTICS",
            build_subscription_client_diagnostics(
                request.headers
            ),
            flush=True,
        )

    user = subscription_token_service.resolve_token(
        database=database,
        raw_token=token,
    )

    subscription = database.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status == "active",
        )
        .order_by(
            Subscription.created_at.desc()
        )
    )

    if subscription is None:
        return Response(
            content="",
            status_code=403,
            media_type="text/plain",
        )

    devices = database.scalars(
        select(VpnDevice)
        .where(
            VpnDevice.user_id == user.id,
            VpnDevice.is_active.is_(True),
        )
        .order_by(
            VpnDevice.id.asc()
        )
    ).all()

    if not devices:
        return Response(
            content="",
            media_type="text/plain",
        )

    # Временная архитектура:
    # берём credential первого активного устройства.
    # Позже вынесем subscription credentials отдельно.
    source_device = devices[0]

    node_ids = {
        device.node_id
        for device in devices
    }

    nodes = database.scalars(
        select(VpnNode)
        .where(
            VpnNode.id.in_(node_ids),
            VpnNode.is_active.is_(True),
        )
        .order_by(
            VpnNode.id.asc()
        )
    ).all()

    profiles = (
        vpn_node_profile_service.get_active_profiles_for_nodes(
            database=database,
            node_ids=node_ids,
        )
    )

    print(
        "NODE_PROFILES",
        [
            {
                "code": profile.code,
                "protocol": profile.protocol,
                "network": profile.network,
                "security": profile.security,
                "port": profile.port,
            }
            for profile in profiles
        ],
        flush=True,
    )

    links = subscription_builder.build(
        client=client,
        device=source_device,
        nodes=nodes,
        profiles=profiles,
        include_happ_mobile=(
            should_include_happ_mobile_profile(
                client=client,
                user_id=user.id,
                configured_user_ids=(
                    settings.happ_mobile_profile_user_ids
                ),
            )
        ),
    )

    routing_link = None

    if should_include_happ_smart_routing(
        client=client,
        user_id=user.id,
        configured_user_ids=(
            settings.happ_smart_routing_user_ids
        ),
    ):
        routing_link = build_happ_smart_routing_link()

    payload = build_subscription_payload(
        client=client,
        links=links,
        routing_link=routing_link,
    )

    encoded = base64.b64encode(
        payload.encode("utf-8")
    ).decode("ascii")

    response_headers = {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
    }

    if client == "happ":
        response_headers.update(
            HAPP_SUBSCRIPTION_HEADERS
        )

    return Response(
        content=encoded,
        media_type="text/plain",
        headers=response_headers,
    )
