import base64

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.subscription import Subscription
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.subscription_token_service import (
    subscription_token_service,
)
from app.services.subscription_builder import (
    subscription_builder,
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
        .order_by(Subscription.created_at.desc())
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
        .order_by(VpnDevice.id.asc())
    ).all()

    if not devices:
        return Response(
            content="",
            media_type="text/plain",
        )

    # Пока используем UUID первого активного устройства.
    # Позже subscription credentials вынесем отдельно.
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
        .order_by(VpnNode.id.asc())
    ).all()

    links = subscription_builder.build(
    client=client,
    device=source_device,
    nodes=nodes,
)

    payload = "\n".join(links)

    encoded = base64.b64encode(
        payload.encode("utf-8")
    ).decode("ascii")

    return Response(
        content=encoded,
        media_type="text/plain",
    )