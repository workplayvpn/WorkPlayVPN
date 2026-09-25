from app.services.client_profiles.generic import GenericProfile

from test_happ_client_profile import build_device, build_node, build_profile


def test_generic_feed_never_contains_mobile_cdn() -> None:
    direct = build_profile(
        profile_id=1,
        code="direct",
        network="tcp",
        security="reality",
        port=443,
        settings={},
    )
    mobile = build_profile(
        profile_id=2,
        code="mobile",
        network="xhttp",
        security="tls",
        port=443,
        settings={
            "happ_access_mode": "mobile",
            "happ_server_address": "cdn.bot-forma.ru",
            "path": "/wp-bf/",
        },
    )

    links = GenericProfile().build_links(
        device=build_device(),
        nodes=[build_node()],
        profiles=[direct, mobile],
    )

    assert len(links) == 1
    assert "security=reality" in links[0]
