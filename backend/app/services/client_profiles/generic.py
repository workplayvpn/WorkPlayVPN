from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.xray_node import xray_node_service

from .base import ClientProfile


class GenericProfile(ClientProfile):

    def build_links(
        self,
        device: VpnDevice,
        nodes: list[VpnNode],
    ) -> list[str]:

        links: list[str] = []

        seen_node_ids: set[int] = set()

        for node in nodes:
            if node.id in seen_node_ids:
                continue

            seen_node_ids.add(node.id)

            links.append(
                xray_node_service.build_vless_url(
                    user_uuid=device.xray_uuid,
                    node_name=node.name,
                )
            )

        return links