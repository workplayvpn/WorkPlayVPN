"""Network-name filtering pilot; Happ requires reconnecting after network changes."""

from app.services.happ_subscription_info import PRO_DESCRIPTION

from urllib.parse import parse_qs, quote, unquote, urlsplit, urlunsplit


PILOT_USER_IDS = frozenset({812})
CLEARWAY_HOST = "d0mbqz.whitechannel-x1-cdn.ru"
NOTICE = PRO_DESCRIPTION


def network_split_allowed(*, client: str, access_tier: str, user_id: int) -> bool:
    return client == "happ" and access_tier == "mobile" and user_id in PILOT_USER_IDS


def network_split_links(links: list[str], *, direct_uuid: str, mobile_uuid: str | None) -> list[str] | None:
    if len(links) != 2 or not mobile_uuid or mobile_uuid == direct_uuid:
        return None
    try:
        direct, mobile = map(urlsplit, links)
        direct_params = parse_qs(direct.query)
        mobile_params = parse_qs(mobile.query)
        if not (
            direct.scheme == mobile.scheme == "vless"
            and direct.username == str(direct_uuid) and mobile.username == str(mobile_uuid)
            and direct_params.get("security") == ["reality"]
            and direct_params.get("type") == ["tcp"]
            and mobile_params.get("security") == ["tls"]
            and mobile_params.get("type") == ["xhttp"]
            and mobile.hostname == CLEARWAY_HOST and mobile.port == 443
            and direct.fragment and mobile.fragment
        ):
            return None
        base = unquote(direct.fragment.split("?serverDescription=", 1)[0]).strip()
        base = base.removesuffix(" — Wi-Fi").strip()
        return [urlunsplit(parts._replace(fragment=quote(
            f"{base} — Pro ({suffix})", safe="",
        ))) for parts, suffix in ((direct, "only WiFi"), (mobile, "only Mobile"))]
    except (TypeError, ValueError):
        return None


# Temporary diagnostic: expose the existing CDN link on both networks for one installation.
def clearway_diagnostic_links(links: list[str], *, user_id: int,
                             device_id: int, device_public_id: str | None) -> list[str]:
    if (user_id, device_id, device_public_id) != (812, 33, "WP-FDCA3BAB5287F68A"):
        return links
    if len(links) != 2:
        return links
    try:
        mobile = urlsplit(links[1])
        params = parse_qs(mobile.query)
        if not (mobile.scheme == "vless" and mobile.hostname == CLEARWAY_HOST
                and mobile.port == 443 and params.get("type") == ["xhttp"]
                and params.get("security") == ["tls"]
                and unquote(mobile.fragment).endswith("(only Mobile)")):
            return links
        title = unquote(mobile.fragment).removesuffix(" (only Mobile)")
        return [links[0], urlunsplit(mobile._replace(
            fragment=quote(title + " — тест ClearWay", safe="")))]
    except (TypeError, ValueError):
        return links
