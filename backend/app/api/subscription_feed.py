from app.services.rollout_access import rollout_allowed
import base64
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.entitlements import active_entitlements
from app.db.dependencies import get_db
from app.models.subscription import Subscription
from app.models.plan import Plan
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.happ_smart_routing import (
    build_happ_smart_routing_link,
)
from app.services.happ_network_candidates import network_candidates
from app.services.happ_subscription_info import subscription_expiry_info
from app.services.happ_subscription_info import subscription_presentation
from app.services.happ_subscription_info import hidden_settings_metadata, happ_server_description
from app.services.happ_device_metadata import record_happ_device_metadata
from app.api.happ_auto_route import auto_route_allowed, get_routed_mobile_subscription
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
    "profile-title": "Work&PlayVPN Basic",
    "profile-update-interval": "3",
    "subscription-auto-update-enable": "1",
    "subscription-auto-update-open-enable": "1",
    "support-url": "https://t.me/workplayvpnteam",
}


def build_subscription_payload(
    *,
    client: str,
    links: list[str],
    access_tier: str = "basic",
    expires_at: datetime | None = None,
    routed_mobile: bool = False,
    provider_metadata: dict[str, str] | None = None,
) -> str:
    if client != "happ":
        return "\n".join(links)

    metadata = [
        f"#{name}: {value}"
        for name, value in {
            **HAPP_SUBSCRIPTION_HEADERS,
            **subscription_presentation(access_tier=access_tier, routed_mobile=routed_mobile),
            **(provider_metadata or {}),
        }.items()
    ]
    expiry_info = subscription_expiry_info(expires_at)
    if expiry_info is not None:
        metadata.append(f"#subscription-userinfo: {expiry_info}")

    return "\n".join([*metadata, *links])


def build_subscription_response_headers(
    *,
    client: str,
    routing_link: str | None = None,
    access_tier: str = "basic",
    expires_at: datetime | None = None,
    routed_mobile: bool = False,
    provider_metadata: dict[str, str] | None = None,
) -> dict[str, str]:
    response_headers = {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
    }

    if client != "happ":
        return response_headers

    response_headers.update(HAPP_SUBSCRIPTION_HEADERS)
    response_headers.update(subscription_presentation(
        access_tier=access_tier, routed_mobile=routed_mobile,
    ))
    response_headers.update(provider_metadata or {})
    expiry_info = subscription_expiry_info(expires_at)
    if expiry_info is not None:
        response_headers["subscription-userinfo"] = expiry_info
    if routing_link is not None:
        response_headers["routing"] = routing_link

    return response_headers


def should_enable_happ_feature(
    *,
    client: str,
    user_id: int,
    configured_user_ids: str,
) -> bool:
    if client != "happ":
        return False

    return rollout_allowed(configured_user_ids, user_id)


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
    return _build_subscription_feed(token, request, database)


@router.get("/device/{device_id}/{token}")
def get_device_subscription_feed(
    device_id: int, token: str, request: Request,
    database: Session = Depends(get_db),
):
    return _build_subscription_feed(token, request, database, device_id=device_id)


def _build_subscription_feed(
    token: str, request: Request, database: Session, *, device_id: int | None = None,
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

    user, access_tier = subscription_token_service.resolve_token_scope(
        database=database, raw_token=token,
    )
    if device_id is not None and access_tier != "basic":
        raise HTTPException(status_code=404)
    entitlement = active_entitlements(database, user.id).get(access_tier)
    if entitlement is None:
        return Response(content="", status_code=403, media_type="text/plain")
    if client == "happ" and access_tier == "mobile" and auto_route_allowed(user.id):
        # The canary's existing Mobile URL updates to the single routed JSON entry.
        # Legacy Mobile URLs for other users retain their current format.
        return get_routed_mobile_subscription(token, database, request)
    mobile_entitled = access_tier == "mobile"

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

    if device_id is not None:
        devices = [device for device in devices if device.id == device_id]
        if not devices:
            raise HTTPException(status_code=404)

    if not devices:
        return Response(
            content="",
            media_type="text/plain",
        )

    # Временная архитектура:
    # берём credential первого активного устройства.
    # Позже вынесем subscription credentials отдельно.
    source_device = devices[0]

    if mobile_entitled and not (
        source_device.mobile_xray_uuid and source_device.mobile_xray_email
    ):
        return Response(
            content="Mobile credential is not provisioned",
            status_code=503,
            media_type="text/plain",
            headers={"Cache-Control": "no-store"},
        )

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
        include_happ_mobile=mobile_entitled,
    )

    provider_metadata = hidden_settings_metadata(
        provider_id=settings.happ_provider_id,
        user_id=user.id,
        allowed_ids=settings.happ_hidden_settings_user_ids,
    ) if client == "happ" else {}
    if provider_metadata:
        caption = "Work&PlayVPN Mobile" if mobile_entitled else "Work&PlayVPN Basic"
        links = [happ_server_description(link, caption) for link in links]

    if mobile_entitled and should_enable_happ_feature(
        client=client,
        user_id=user.id,
        configured_user_ids=settings.happ_mobile_network_hint_user_ids,
    ):
        links = network_candidates(
            links,
            direct_uuid=source_device.xray_uuid,
            mobile_uuid=source_device.mobile_xray_uuid,
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
        access_tier=access_tier,
        expires_at=entitlement[0].expires_at,
        provider_metadata=provider_metadata,
    )

    encoded = base64.b64encode(
        payload.encode("utf-8")
    ).decode("ascii")

    response_headers = build_subscription_response_headers(
        client=client,
        routing_link=routing_link,
        access_tier=access_tier,
        expires_at=entitlement[0].expires_at,
        provider_metadata=provider_metadata,
    )

    if client == "happ":
        record_happ_device_metadata(
            database, devices, request.headers,
            selected_device=source_device if device_id is not None else None,
        )

    return Response(
        content=encoded,
        media_type="text/plain",
        headers=response_headers,
    )
