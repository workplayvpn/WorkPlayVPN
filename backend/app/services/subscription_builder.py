from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.models.vpn_node_profile import VpnNodeProfile
from app.services.client_profiles.factory import (
    client_profile_factory,
)


class SubscriptionBuilder:

    def build(
        self,
        client: str,
        device: VpnDevice,
        nodes: list[VpnNode],
        profiles: list[VpnNodeProfile],
    ) -> list[str]:
        profile = client_profile_factory.get_profile(
            client
        )

        return profile.build_links(
            device=device,
            nodes=nodes,
            profiles=profiles,
        )


subscription_builder = SubscriptionBuilder()