"""Account 812 pilot: add ClearWay Entry 2 without changing the primary route."""

import json
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from app.services.happ_auto_route import build_auto_route_config, build_routed_auto_config


PILOT_USER_IDS = frozenset({812})
PRIMARY_HOST = "d0mbqz.whitechannel-x1-cdn.ru"
RESERVE_HOST = "d0mbqz.edge-assets.ru"
RESERVE_TITLE = "Work&PlayVPN Pro — Вход 2"


def reserve_link(links: list[str], *, user_id: int, mobile_uuid: str | None) -> str | None:
    """Reuse only the authenticated device's existing ClearWay credential and path."""
    if user_id not in PILOT_USER_IDS or not mobile_uuid:
        return None
    matches = []
    for link in links:
        try:
            parts = urlsplit(link)
            pairs = parse_qsl(parts.query, keep_blank_values=True)
            params = dict(pairs)
            if len(params) != len(pairs):
                continue
            if not (
                parts.scheme == "vless" and parts.hostname == PRIMARY_HOST
                and parts.port == 443 and parts.username == str(mobile_uuid)
                and parts.password is None
                and params.get("type") == "xhttp" and params.get("security") == "tls"
                and params.get("sni") == PRIMARY_HOST and params.get("host") == PRIMARY_HOST
                and params.get("path", "").startswith("/wp-cw-")
            ):
                continue
            params.update({
                "sni": RESERVE_HOST, "host": RESERVE_HOST, "mode": "packet-up",
                "extra": json.dumps({
                    "mode": "packet-up", "scMaxEachPostBytes": 1000000,
                    "uplinkDataPlacement": "body", "uplinkHTTPMethod": "PUT",
                }, separators=(",", ":")),
            })
            matches.append(urlunsplit((
                "vless", f"{parts.username}@{RESERVE_HOST}:443",
                parts.path, urlencode(params), quote(RESERVE_TITLE, safe=""),
            )))
        except (TypeError, ValueError):
            continue
    return matches[0] if len(matches) == 1 else None


def reserve_config(direct_link: str, entry2_link: str, *, routed: bool) -> dict:
    """Separate selectable entry; retain the existing domestic routing policy."""
    builder = build_routed_auto_config if routed else build_auto_route_config
    config = builder(direct_link, entry2_link)[0]
    config["remarks"] = RESERVE_TITLE
    config["outbounds"] = [outbound for outbound in config["outbounds"]
                           if outbound["tag"] != "vpn-direct"]
    config.pop("observatory", None)
    config["routing"].pop("balancers", None)
    for rule in config["routing"]["rules"]:
        if "balancerTag" in rule:
            rule.pop("balancerTag")
            rule["outboundTag"] = "vpn-cdn"
    return config
