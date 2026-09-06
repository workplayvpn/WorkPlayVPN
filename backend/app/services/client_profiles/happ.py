from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.models.vpn_node_profile import VpnNodeProfile
from app.services.vpn_profile_link_builder import (
    vpn_profile_link_builder,
)

from .base import ClientProfile


class HappProfile(ClientProfile):

    def build_links(
        self,
        device: VpnDevice,
        nodes: list[VpnNode],
        profiles: list[VpnNodeProfile],
    ) -> list[str]:
        links: list[str] = []

        profiles_by_node: dict[
            int,
            list[VpnNodeProfile],
        ] = {}

        for profile in profiles:
            if not profile.is_active:
                continue

            profiles_by_node.setdefault(
                profile.node_id,
                [],
            ).append(profile)

        for node in nodes:
            node_profiles = profiles_by_node.get(
                node.id,
                [],
            )

            xhttp_profile = next(
                (
                    profile
                    for profile in node_profiles
                    if profile.protocol == "vless"
                    and profile.network == "xhttp"
                    and profile.security == "tls"
                ),
                None,
            )

            if xhttp_profile is None:
                continue

            links.append(
                vpn_profile_link_builder.build_vless_link(
                    device=device,
                    node=node,
                    profile=xhttp_profile,
                )
            )

        return links
