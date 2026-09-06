from urllib.parse import quote, urlencode

from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.models.vpn_node_profile import VpnNodeProfile


class VpnProfileLinkBuilder:

    def build_vless_link(
        self,
        device: VpnDevice,
        node: VpnNode,
        profile: VpnNodeProfile,
    ) -> str:
        settings = profile.settings or {}

        params: dict[str, str] = {
            "encryption": "none",
            "type": profile.network,
            "security": profile.security,
        }

        if profile.flow:
            params["flow"] = profile.flow

        if profile.server_name:
            params["sni"] = profile.server_name

        fingerprint = settings.get("fingerprint")

        if fingerprint:
            params["fp"] = fingerprint

        public_key = settings.get("public_key")

        if public_key:
            params["pbk"] = public_key

        short_id = settings.get("short_id")

        if short_id:
            params["sid"] = short_id

        header_type = settings.get("header_type")

        if header_type:
            params["headerType"] = header_type

        path = settings.get("path")

        if path:
            params["path"] = path

        mode = settings.get("mode")

        if mode:
            params["mode"] = mode

        query = urlencode(
            params,
            safe="-_/",
        )

        name = quote(
            node.name,
            safe="",
        )

        return (
            f"vless://{device.xray_uuid}"
            f"@{node.host}:{profile.port}"
            f"?{query}"
            f"#{name}"
        )


vpn_profile_link_builder = VpnProfileLinkBuilder()
