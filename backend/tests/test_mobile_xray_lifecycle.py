import pytest

from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.xray_node import XrayNodeService


def make_device() -> VpnDevice:
    return VpnDevice(
        user_id=1,
        node_id=1,
        device_name="phone",
        xray_uuid="11111111-2222-4333-8444-555555555555",
        xray_email="device@workplayvpn",
        mobile_xray_uuid="22222222-3333-4444-8555-666666666666",
        mobile_xray_email="mobile_" + "a" * 32 + "@workplayvpn",
        is_active=True,
    )


def test_add_and_remove_use_both_inbounds(monkeypatch) -> None:
    service = XrayNodeService()
    commands = []
    monkeypatch.setattr(service, "_run", lambda node, command: commands.append(command))
    node = VpnNode()
    device = make_device()

    service.add_device(node, device)
    service.remove_device(node, device)

    assert commands == [
        f"add-user {device.xray_uuid} {device.xray_email}",
        f"add-mobile-user {device.mobile_xray_uuid} {device.mobile_xray_email}",
        f"remove-mobile-user {device.mobile_xray_email}",
        f"remove-user {device.xray_email}",
    ]


def test_mobile_provision_failure_rolls_back_direct(monkeypatch) -> None:
    service = XrayNodeService()
    commands = []

    def run(node, command):
        commands.append(command)
        if command.startswith("add-mobile-user "):
            raise RuntimeError("CDN unavailable")

    monkeypatch.setattr(service, "_run", run)
    device = make_device()

    with pytest.raises(RuntimeError, match="CDN unavailable"):
        service.add_device(VpnNode(), device)

    assert commands[-1] == f"remove-user {device.xray_email}"
