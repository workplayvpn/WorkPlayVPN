from abc import ABC, abstractmethod

from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode


class ClientProfile(ABC):

    @abstractmethod
    def build_links(
        self,
        device: VpnDevice,
        nodes: list[VpnNode],
    ) -> list[str]:
        pass