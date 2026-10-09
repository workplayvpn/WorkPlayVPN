from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vpn_node_profile import VpnNodeProfile
from app.services.client_profiles.happ import HappProfile


def require_mobile_profile(database: Session, node_id: int) -> None:
    profiles = database.scalars(
        select(VpnNodeProfile).where(
            VpnNodeProfile.node_id == node_id,
            VpnNodeProfile.is_active.is_(True),
        )
    ).all()
    if any(HappProfile._is_mobile_profile_ready(profile) for profile in profiles):
        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Pro access is not available in this location",
    )
