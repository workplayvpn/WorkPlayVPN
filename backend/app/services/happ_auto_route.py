"""Build an isolated Xray JSON canary with Direct preferred over CDN.

This module is deliberately not wired into the existing Mobile feed. Happ's
iOS JSON import and reconnect behaviour need a device test first.
"""

import json
from urllib.parse import parse_qs, urlsplit
from uuid import UUID


def _parse(link: str, *, transport: str, security: str) -> tuple:
    parts = urlsplit(link)
    query = parse_qs(parts.query, keep_blank_values=True)

    def value(key: str, default: str = "") -> str:
        values = query.get(key, [])
        if len(values) > 1:
            raise ValueError("Duplicate VLESS parameter")
        return values[0] if values else default

    try:
        credential = str(UUID(parts.username or ""))
        address = parts.hostname
        port = parts.port
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid VLESS endpoint") from exc
    if (parts.scheme != "vless" or not address or not port
            or value("type") != transport or value("security") != security
            or value("encryption", "none") != "none"):
        raise ValueError("Unsupported VLESS endpoint")

    user = {"id": credential, "encryption": "none"}
    if value("flow"):
        user["flow"] = value("flow")
    outbound = {
        "protocol": "vless",
        "settings": {"vnext": [{"address": address, "port": port, "users": [user]}]},
        "streamSettings": {"network": transport, "security": security},
    }
    return outbound, value


def build_auto_route_config(direct_link: str, cdn_link: str) -> list[dict]:
    """Create one experimental JSON subscription entry; never log the result."""
    direct, direct_param = _parse(direct_link, transport="tcp", security="reality")
    cdn, cdn_param = _parse(cdn_link, transport="xhttp", security="tls")
    if direct["settings"]["vnext"][0]["users"][0]["id"] == cdn["settings"]["vnext"][0]["users"][0]["id"]:
        raise ValueError("CDN must have its separate credential")
    if not direct_param("sni") or not direct_param("pbk") or not direct_param("fp"):
        raise ValueError("Incomplete Reality profile")
    if not cdn_param("sni") or not cdn_param("path").startswith("/"):
        raise ValueError("Incomplete CDN profile")

    direct["tag"] = "vpn-direct"
    direct["streamSettings"]["realitySettings"] = {
        "serverName": direct_param("sni"),
        "publicKey": direct_param("pbk"),
        "shortId": direct_param("sid"),
        "fingerprint": direct_param("fp"),
    }
    cdn["tag"] = "vpn-cdn"
    cdn["streamSettings"]["tlsSettings"] = {
        "serverName": cdn_param("sni"),
        "fingerprint": cdn_param("fp", "chrome"),
    }
    if cdn_param("alpn"):
        cdn["streamSettings"]["tlsSettings"]["alpn"] = cdn_param("alpn").split(",")
    xhttp = {"path": cdn_param("path")}
    for name in ("host", "mode"):
        if cdn_param(name):
            xhttp[name] = cdn_param(name)
    if cdn_param("extra"):
        try:
            extra = json.loads(cdn_param("extra"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid XHTTP extra") from exc
        if not isinstance(extra, dict):
            raise ValueError("Invalid XHTTP extra")
        xhttp["extra"] = extra
    cdn["streamSettings"]["xhttpSettings"] = xhttp

    return [{
        "remarks": "WorkPlayVPN Mobile Auto — pilot",
        "log": {"loglevel": "warning"},
        "inbounds": [
            {"tag": "local-socks", "listen": "127.0.0.1", "port": 10808,
             "protocol": "socks", "settings": {"udp": True}},
        ],
        "outbounds": [direct, cdn],
        "observatory": {
            "subjectSelector": ["vpn-direct"],
            "probeUrl": "https://www.gstatic.com/generate_204",
            "probeInterval": "15s",
        },
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [{"type": "field", "network": "tcp,udp",
                       "balancerTag": "prefer-direct"}],
            "balancers": [{
                "tag": "prefer-direct", "selector": ["vpn-direct"],
                "fallbackTag": "vpn-cdn", "strategy": {"type": "leastPing"},
            }],
        },
    }]
