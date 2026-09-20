from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.internal_auth import require_internal_api_secret
from app.db.dependencies import get_db
from app.models.vpn_node import VpnNode
from app.models.vpn_node_profile import VpnNodeProfile
from app.services.client_profiles.happ import HappProfile


router = APIRouter(
    prefix="/internal/happ",
    tags=["internal-happ"],
    dependencies=[
        Depends(require_internal_api_secret),
    ],
)


@router.get("/mobile-readiness")
def get_mobile_readiness(
    database: Session = Depends(get_db),
):
    profiles = database.scalars(
        select(VpnNodeProfile)
        .order_by(VpnNodeProfile.id.asc())
    ).all()

    mobile_profile = next(
        (
            profile
            for profile in profiles
            if HappProfile._access_mode(profile) == "mobile"
        ),
        None,
    )

    if mobile_profile is None:
        return {
            "status": "not_ready",
            "mobile_profile_found": False,
            "profile_active": False,
            "node_active": False,
            "configuration_valid": False,
            "issues": [
                "mobile_profile_missing",
            ],
        }

    node = database.get(
        VpnNode,
        mobile_profile.node_id,
    )

    node_active = (
        node is not None
        and node.is_active
    )

    configuration_valid = (
        HappProfile._is_mobile_profile_ready(
            mobile_profile
        )
    )

    issues: list[str] = []

    if not mobile_profile.is_active:
        issues.append("profile_inactive")

    if not node_active:
        issues.append("node_inactive")

    if not configuration_valid:
        issues.append("configuration_invalid")

    ready = (
        mobile_profile.is_active
        and node_active
        and configuration_valid
    )

    return {
        "status": "ready" if ready else "not_ready",
        "mobile_profile_found": True,
        "profile_active": mobile_profile.is_active,
        "node_active": node_active,
        "configuration_valid": configuration_valid,
        "issues": issues,
    }