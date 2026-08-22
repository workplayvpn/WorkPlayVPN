from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vpn_node_profile import VpnNodeProfile


class VpnNodeProfileService:

    def get_active_profiles_for_nodes(
        self,
        database: Session,
        node_ids: set[int],
    ) -> list[VpnNodeProfile]:
        if not node_ids:
            return []

        return list(
            database.scalars(
                select(VpnNodeProfile)
                .where(
                    VpnNodeProfile.node_id.in_(node_ids),
                    VpnNodeProfile.is_active.is_(True),
                )
                .order_by(
                    VpnNodeProfile.node_id.asc(),
                    VpnNodeProfile.id.asc(),
                )
            ).all()
        )


vpn_node_profile_service = VpnNodeProfileService()