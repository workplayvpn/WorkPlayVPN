from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.models.vpn_node_profile import VpnNodeProfile
from app.services.vpn_profile_link_builder import (
    vpn_profile_link_builder,
)

from .base import ClientProfile


class GenericProfile(ClientProfile):

    def build_links(
        self,
        device: VpnDevice,
        nodes: list[VpnNode],
        profiles: list[VpnNodeProfile],
        include_happ_mobile: bool = False,
    ) -> list[str]:
        links: list[str] = []

        profiles_by_node: dict[int, list[VpnNodeProfile]] = {}

        for profile in profiles:
            if not profile.is_active:
                continue

            # Mobile endpoints must never leak into a Basic feed through
            # clients that do not identify themselves as Happ.
            if (profile.settings or {}).get("happ_access_mode") == "mobile":
                continue

            profiles_by_node.setdefault(
                profile.node_id,
                [],
            ).append(profile)

        seen_node_ids: set[int] = set()

        for node in nodes:
            if node.id in seen_node_ids:
                continue

            seen_node_ids.add(node.id)

            node_profiles = profiles_by_node.get(
                node.id,
                [],
            )

            for profile in node_profiles:
                if profile.protocol != "vless":
                    continue

                links.append(
                    vpn_profile_link_builder.build_vless_link(
                        device=device,
                        node=node,
                        profile=profile,
                    )
                )

        return links
