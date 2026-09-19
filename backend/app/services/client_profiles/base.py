from abc import ABC, abstractmethod

from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.models.vpn_node_profile import VpnNodeProfile


class ClientProfile(ABC):

    @abstractmethod
    def build_links(
        self,
        device: VpnDevice,
        nodes: list[VpnNode],
        profiles: list[VpnNodeProfile],
        include_happ_mobile: bool = False,
    ) -> list[str]:
        pass
