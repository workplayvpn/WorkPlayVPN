from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.models.vpn_node_profile import VpnNodeProfile
from app.services.vpn_profile_link_builder import (
    vpn_profile_link_builder,
)

from .base import ClientProfile


class HiddifyProfile(ClientProfile):

    def build_links(
        self,
        device: VpnDevice,
        nodes: list[VpnNode],
        profiles: list[VpnNodeProfile],
        include_happ_mobile: bool = False,
    ) -> list[str]:
        links: list[str] = []

        profiles_by_node: dict[
            int,
            list[VpnNodeProfile],
        ] = {}

        for profile in profiles:
            profiles_by_node.setdefault(
                profile.node_id,
                [],
            ).append(profile)

        for node in nodes:
            node_profiles = profiles_by_node.get(
                node.id,
                [],
            )

            reality_profile = next(
                (
                    profile
                    for profile in node_profiles
                    if profile.protocol == "vless"
                    and profile.network == "tcp"
                    and profile.security == "reality"
                ),
                None,
            )

            if reality_profile is None:
                continue

            links.append(
                vpn_profile_link_builder.build_vless_link(
                    device=device,
                    node=node,
                    profile=reality_profile,
                )
            )

        return links
