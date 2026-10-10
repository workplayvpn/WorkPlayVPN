import json
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

from app.services.happ_auto_route import build_routed_auto_config
from app.services.happ_clearway_reserve import (
    PRIMARY_HOST, RESERVE_HOST, RESERVE_TITLE, reserve_config, reserve_link,
)

DIRECT = '11111111-2222-4333-8444-555555555555'
MOBILE = '22222222-3333-4444-8555-666666666666'
PATH = '/wp-cw-private-route/'


def links():
    return [
        f'vless://{DIRECT}@node.example:443?' + urlencode({
            'type': 'tcp', 'security': 'reality', 'sni': 'cover.example',
            'pbk': 'public-key', 'sid': 'a1b2', 'fp': 'chrome',
        }),
        f'vless://{MOBILE}@{PRIMARY_HOST}:443?' + urlencode({
            'type': 'xhttp', 'security': 'tls', 'sni': PRIMARY_HOST,
            'host': PRIMARY_HOST, 'path': PATH, 'mode': 'packet-up',
            'fp': 'chrome', 'alpn': 'h2',
            'extra': json.dumps({'uplinkHTTPMethod': 'GET', 'uplinkDataPlacement': 'header'}),
        }),
    ]


def test_reserve_reuses_device_credential_and_gateway_path():
    original = links()
    result = reserve_link(original, user_id=812, mobile_uuid=MOBILE)
    parsed = urlsplit(result)
    params = parse_qs(parsed.query)
    assert parsed.username == MOBILE
    assert parsed.hostname == RESERVE_HOST and parsed.port == 443
    assert params['path'] == [PATH]
    assert params['sni'] == params['host'] == [RESERVE_HOST]
    assert params['fp'] == ['chrome'] and params['alpn'] == ['h2']
    assert json.loads(params['extra'][0]) == {
        'mode': 'packet-up', 'scMaxEachPostBytes': 1000000,
        'uplinkDataPlacement': 'body', 'uplinkHTTPMethod': 'PUT',
    }
    assert original == links()


@pytest.mark.parametrize('user_id,credential', [(978, MOBILE), (812, DIRECT), (812, None)])
def test_no_reserve_for_other_accounts_or_wrong_device(user_id, credential):
    assert reserve_link(links(), user_id=user_id, mobile_uuid=credential) is None


@pytest.mark.parametrize('alter', [
    lambda values: [values[0]],
    lambda values: values + [values[1]],
    lambda values: [values[1].replace('443?', 'invalid?')],
    lambda values: [values[1] + '&type=xhttp'],
    lambda values: [values[1].replace('wp-cw-', 'other-')],
    lambda values: [values[1].replace(PRIMARY_HOST, 'other.example')],
])
def test_unmatched_or_ambiguous_source_keeps_primary_only(alter):
    assert reserve_link(alter(links()), user_id=812, mobile_uuid=MOBILE) is None


@pytest.mark.parametrize('routed', [True, False])
def test_separate_json_entry_uses_reserve_and_preserves_primary(routed):
    original = links()
    primary = build_routed_auto_config(*original)
    snapshot = json.dumps(primary)
    reserve = reserve_link(original, user_id=812, mobile_uuid=MOBILE)
    config = reserve_config(original[0], reserve, routed=routed)
    assert config['remarks'] == RESERVE_TITLE
    assert 'observatory' not in config and 'balancers' not in config['routing']
    assert all('balancerTag' not in rule for rule in config['routing']['rules'])
    assert config['routing']['rules'][-1]['outboundTag'] == 'vpn-cdn'
    assert [outbound['tag'] for outbound in config['outbounds']] == (
        ['vpn-cdn', 'ru-direct'] if routed else ['vpn-cdn'])
    outbound = config['outbounds'][0]
    assert outbound['settings']['vnext'][0]['address'] == RESERVE_HOST
    assert outbound['settings']['vnext'][0]['users'][0]['id'] == MOBILE
    assert outbound['streamSettings']['xhttpSettings']['path'] == PATH
    if routed:
        assert config['routing']['rules'][:2] == primary[0]['routing']['rules'][:2]
        assert config['dns'] == primary[0]['dns']
    assert json.dumps(primary) == snapshot


@pytest.mark.parametrize('user_id,count', [(812, 2), (978, 1)])
def test_api_preserves_provider_id_and_limits_pilot(monkeypatch, user_id, count):
    from app.api import happ_auto_route as route
    from app.core.config import settings

    monkeypatch.setattr(settings, 'happ_auto_route_user_ids', '*')
    monkeypatch.setattr(settings, 'happ_hidden_settings_user_ids', '*')
    monkeypatch.setattr(settings, 'happ_provider_id', 'existing-provider')
    monkeypatch.setattr(route.subscription_token_service, 'resolve_token_scope',
                        lambda database, token: (SimpleNamespace(id=user_id), 'mobile'))
    monkeypatch.setattr(route, 'active_entitlements', lambda db, uid: {
        'mobile': (SimpleNamespace(expires_at=datetime(2026, 11, 14, tzinfo=UTC)), object()),
    })
    device = SimpleNamespace(node_id=1, mobile_xray_uuid=MOBILE, mobile_xray_email='mobile@test')

    class Result:
        def __init__(self, value):
            self.value = value
        def all(self):
            return self.value

    class Database:
        calls = 0
        def scalars(self, query):
            self.calls += 1
            return Result([device] if self.calls == 1 else [SimpleNamespace(id=1)])

    monkeypatch.setattr(route.vpn_node_profile_service, 'get_active_profiles_for_nodes',
                        lambda **kwargs: [])
    monkeypatch.setattr(route.subscription_builder, 'build', lambda **kwargs: links())
    response = route.get_routed_mobile_subscription('private-token', Database())
    configs = json.loads(response.body)
    assert len(configs) == count
    assert configs[0]['outbounds'][1]['settings']['vnext'][0]['address'] == PRIMARY_HOST
    assert response.headers['providerid'] == 'existing-provider'
    assert all(entry['meta'] == {'serverDescription': 'Work&PlayVPN Pro'} for entry in configs)
