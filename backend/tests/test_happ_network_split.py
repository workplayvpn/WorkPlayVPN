import base64
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import quote, unquote, urlencode, urlsplit

import pytest

from app.services.happ_network_split import (
    CLEARWAY_HOST, NOTICE, network_split_allowed, network_split_links,
)

DIRECT = '11111111-2222-4333-8444-555555555555'
MOBILE = '22222222-3333-4444-8555-666666666666'


def links():
    return [
        f'vless://{DIRECT}@node.example:443?' + urlencode({
            'type': 'tcp', 'security': 'reality', 'sni': 'cover.example',
        }) + '#' + quote('🇳🇱 Нидерланды — Wi-Fi'),
        f'vless://{MOBILE}@{CLEARWAY_HOST}:443?' + urlencode({
            'type': 'xhttp', 'security': 'tls', 'sni': CLEARWAY_HOST,
            'host': CLEARWAY_HOST, 'path': '/wp-cw-device-route/',
            'extra': '{"uplinkHTTPMethod":"GET","uplinkDataPlacement":"header"}',
        }) + '#' + quote('🇳🇱 Нидерланды — Pro'),
    ]


def test_labels_only_change_names_keep_endpoint_uuid_and_transport():
    original = links()
    result = network_split_links(original, direct_uuid=DIRECT, mobile_uuid=MOBILE)
    assert len(result) == 2
    assert [unquote(urlsplit(link).fragment) for link in result] == [
        '🇳🇱 Нидерланды — Pro (only WiFi)',
        '🇳🇱 Нидерланды — Pro (only Mobile)',
    ]
    assert [link.split('#')[0] for link in result] == [link.split('#')[0] for link in original]
    assert original == links()


@pytest.mark.parametrize('client,tier,user_id,allowed', [
    ('happ','mobile',812,True), ('happ','basic',812,False),
    ('happ','mobile',978,False), ('generic','mobile',812,False),
])
def test_pilot_scope(client, tier, user_id, allowed):
    assert network_split_allowed(client=client, access_tier=tier, user_id=user_id) is allowed


@pytest.mark.parametrize('values,credential', [
    (links()[:1], MOBILE), (links(), DIRECT), (links(), None),
    ([links()[0], links()[1].replace(CLEARWAY_HOST, 'other.example')], MOBILE),
])
def test_invalid_sources_do_not_hide_routes(values, credential):
    assert network_split_links(values, direct_uuid=DIRECT, mobile_uuid=credential) is None


@pytest.mark.parametrize('tier', ['mobile', 'basic'])
@pytest.mark.parametrize('device_route', [False, True])
def test_feed_preserves_provider_registration_routing_and_expiry(monkeypatch, tier, device_route):
    from app.api import subscription_feed as feed
    from app.core.config import settings
    from starlette.requests import Request

    monkeypatch.setattr(settings, 'happ_auto_route_user_ids', '*')
    monkeypatch.setattr(settings, 'happ_hidden_settings_user_ids', '*')
    monkeypatch.setattr(settings, 'happ_mobile_network_hint_user_ids', '*')
    monkeypatch.setattr(settings, 'happ_smart_routing_user_ids', '*')
    monkeypatch.setattr(settings, 'happ_provider_id', 'existing-provider')
    monkeypatch.setattr(settings, 'happ_account_device_registration_enabled', True)
    monkeypatch.setattr(feed.subscription_token_service, 'resolve_token_scope',
                        lambda *args, **kwargs: (SimpleNamespace(id=812), tier))
    expiry = datetime(2026, 11, 14, tzinfo=UTC)
    monkeypatch.setattr(feed, 'active_entitlements', lambda db, uid: {
        tier: (SimpleNamespace(expires_at=expiry), object()),
    })
    selected = SimpleNamespace(id=33, node_id=1, xray_uuid=DIRECT, mobile_xray_uuid=MOBILE,
                               mobile_xray_email='mobile@test')
    other = SimpleNamespace(id=35, node_id=1, xray_uuid='other-device')
    registration_calls = []
    def register(*args, **kwargs):
        registration_calls.append(args)
        return selected
    monkeypatch.setattr(feed, 'resolve_happ_account_device', register)
    class Database:
        calls = 0
        def scalars(self, query):
            self.calls += 1
            value = [other, selected] if self.calls == 1 else [SimpleNamespace(id=1)]
            return SimpleNamespace(all=lambda: value)
    monkeypatch.setattr(feed.vpn_node_profile_service, 'get_active_profiles_for_nodes', lambda **kw: [])
    monkeypatch.setattr(feed.subscription_builder, 'build', lambda **kw: (
        links() if kw['include_happ_mobile'] else links()[:1]))
    monkeypatch.setattr(feed, 'record_happ_device_metadata', lambda *args, **kw: None)
    def no_json(*args):
        pytest.fail('The split pilot must not use JSON Auto')
    monkeypatch.setattr(feed, 'get_routed_mobile_subscription', no_json)
    request = Request({'type': 'http', 'headers': [(b'user-agent', b'Happ/3.0')]})
    if device_route and tier == 'mobile':
        from app.api import happ_auto_route as auto
        response = auto.get_routed_auto_route_for_device(33, 'private-token', request, Database())
    else:
        response = feed._build_subscription_feed('private-token', request, Database())
    assert registration_calls
    decoded = base64.b64decode(response.body).decode()
    emitted = [line for line in decoded.splitlines() if line.startswith('vless://')]
    assert response.headers['providerid'] == 'existing-provider'
    assert response.headers['hide-settings'] == '1'
    assert 'routing' in response.headers
    assert response.headers['subscription-userinfo'] == f'expire={int(expiry.timestamp())}'
    assert all('?serverDescription=' in link for link in emitted)
    if tier == 'mobile':
        assert len(emitted) == 2
        assert 'only WiFi' in unquote(emitted[0])
        assert 'only Mobile' in unquote(emitted[1])
        assert response.headers['dont-use-filter'] == '0'
        announcement = base64.b64decode(response.headers['announce'].removeprefix('base64:')).decode()
        assert announcement == NOTICE
        assert '#dont-use-filter: 0' in decoded
    else:
        assert len(emitted) == 1
        assert 'only Mobile' not in decoded
        assert 'dont-use-filter' not in response.headers


def test_other_account_keeps_existing_auto(monkeypatch):
    from app.api import subscription_feed as feed
    from app.core.config import settings
    from starlette.requests import Request
    monkeypatch.setattr(settings, 'happ_auto_route_user_ids', '*')
    monkeypatch.setattr(feed.subscription_token_service, 'resolve_token_scope',
                        lambda **kw: (SimpleNamespace(id=978), 'mobile'))
    monkeypatch.setattr(feed, 'active_entitlements', lambda db, uid: {'mobile': (object(),object())})
    marker = object()
    monkeypatch.setattr(feed, 'get_routed_mobile_subscription', lambda *args: marker)
    request = Request({'type': 'http', 'headers': [(b'user-agent',b'Happ/3.0')]})
    assert feed._build_subscription_feed('private-token', request, object()) is marker
