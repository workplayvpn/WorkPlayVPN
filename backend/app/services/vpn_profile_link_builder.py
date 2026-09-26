import json
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
        server_address: str | None = None,
        display_name: str | None = None,
        credential_uuid: str | None = None,
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

        host = settings.get("host")
        if isinstance(host, str) and host:
            params["host"] = host

        mode = settings.get("mode")

        if mode:
            params["mode"] = mode

        alpn = settings.get("alpn")
        if isinstance(alpn, str) and alpn:
            params["alpn"] = alpn
        elif isinstance(alpn, list) and alpn and all(
            isinstance(protocol, str) and protocol
            for protocol in alpn
        ):
            params["alpn"] = ",".join(alpn)

        xhttp_extra = settings.get("xhttp_extra")
        if profile.network == "xhttp" and isinstance(xhttp_extra, dict):
            params["extra"] = json.dumps(
                xhttp_extra,
                ensure_ascii=False,
                separators=(",", ":"),
            )

        query = urlencode(
            params,
            safe="-_/",
        )

        name = quote(
            display_name or node.name,
            safe="",
        )

        address = server_address or node.host

        return (
            f"vless://{credential_uuid or device.xray_uuid}"
            f"@{address}:{profile.port}"
            f"?{query}"
            f"#{name}"
        )


vpn_profile_link_builder = VpnProfileLinkBuilder()
