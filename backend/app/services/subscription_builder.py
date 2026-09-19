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
        include_happ_mobile: bool = False,
    ) -> list[str]:
        profile = client_profile_factory.get_profile(
            client
        )

        return profile.build_links(
            device=device,
            nodes=nodes,
            profiles=profiles,
            include_happ_mobile=include_happ_mobile,
        )


subscription_builder = SubscriptionBuilder()
