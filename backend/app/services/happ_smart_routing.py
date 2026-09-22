import base64
import json

HAPP_SMART_ROUTING_VERSION = 1790035200

HAPP_SMART_ROUTING_PROFILE = {
    "Name": "Work&PlayVPN Smart Routing",
    "GlobalProxy": "true",
    "RemoteDNSType": "DoH",
    "RemoteDNSDomain": (
        "https://cloudflare-dns.com/dns-query"
    ),
    "RemoteDNSIP": "1.1.1.1",
    "DomesticDNSType": "DoU",
    "DomesticDNSDomain": "",
    "DomesticDNSIP": "77.88.8.8",
    "Geoipurl": (
        "https://github.com/v2fly/geoip/releases/"
        "latest/download/geoip.dat"
    ),
    "Geositeurl": (
        "https://github.com/v2fly/domain-list-community/"
        "releases/latest/download/dlc.dat"
    ),
    "LastUpdated": str(HAPP_SMART_ROUTING_VERSION),
    "DnsHosts": {
        "cloudflare-dns.com": "1.1.1.1",
    },
    "DirectSites": [
        "geosite:category-ru",
    ],
    "DirectIp": [
        "geoip:ru",
        "geoip:private",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "224.0.0.0/4",
        "255.255.255.255",
    ],
    "ProxySites": [],
    "ProxyIp": [],
    "BlockSites": [],
    "BlockIp": [],
    "DomainStrategy": "IPIfNonMatch",
    "FakeDNS": "false",
}


def build_happ_smart_routing_link() -> str:
    serialized = json.dumps(
        HAPP_SMART_ROUTING_PROFILE,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    encoded = base64.b64encode(
        serialized.encode("utf-8")
    ).decode("ascii")

    return f"happ://routing/onadd/{encoded}"
