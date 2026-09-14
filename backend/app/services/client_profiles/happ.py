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

            wifi_profile = next(
                (
                    profile
                    for profile in node_profiles
                    if profile.protocol == "vless"
                    and profile.network == "xhttp"
                    and profile.security == "tls"
                ),
                None,
            )

            mobile_profile = next(
                (
                    profile
                    for profile in node_profiles
                    if profile.protocol == "vless"
                    and profile.network == "tcp"
                    and profile.security == "reality"
                ),
                None,
            )

            if wifi_profile is not None:
                links.append(
                    vpn_profile_link_builder.build_vless_link(
                        device=device,
                        node=node,
                        profile=wifi_profile,
                        display_name=(
                            f"{node.name} — Wi-Fi"
                        ),
                    )
                )

            if mobile_profile is not None:
                links.append(
                    vpn_profile_link_builder.build_vless_link(
                        device=device,
                        node=node,
                        profile=mobile_profile,
                        display_name=(
                            f"{node.name} — Mobile"
                        ),
                    )
                )

        return links