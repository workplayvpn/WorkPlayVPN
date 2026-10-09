"""Build opt-in Happ network-labelled Pro candidates.

Happ Premium may filter entries with ``only WiFi`` / ``only Mobile`` in
their names. These labels do not claim an active tunnel will reconnect.
"""

from urllib.parse import quote, unquote, urlsplit, urlunsplit


def _with_label(link: str, label: str) -> str:
    parts = urlsplit(link)
    return urlunsplit(parts._replace(fragment=quote(label, safe="")))


def network_candidates(
    links: list[str], *, direct_uuid: str, mobile_uuid: str | None,
) -> list[str]:
    """Return Wi-Fi Direct, cellular Direct, and cellular CDN for one device.

    Fail closed to the original feed when a route or credential is missing.
    The link builder has already validated and constructed these VLESS URLs.
    """
    if len(links) != 2 or not mobile_uuid or mobile_uuid == direct_uuid:
        return links

    direct, mobile = map(urlsplit, links)
    if (
        direct.scheme != "vless" or mobile.scheme != "vless"
        or direct.username != direct_uuid or mobile.username != mobile_uuid
        or not direct.fragment or not mobile.fragment
    ):
        return links

    direct_label = unquote(direct.fragment)
    mobile_label = unquote(mobile.fragment)
    if direct_label.endswith(" — Wi-Fi"):
        base = direct_label.removesuffix(" — Wi-Fi")
    else:
        base = direct_label

    return [
        _with_label(links[0], f"{base} — Wi-Fi only WiFi"),
        _with_label(links[0], f"{base} — Direct only Mobile"),
        _with_label(links[1], f"{mobile_label} only Mobile"),
    ]
