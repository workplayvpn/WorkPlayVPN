import json
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from app.services.happ_auto_route import build_auto_route_config, build_routed_auto_config
from app.services.happ_clearway_reserve import (
    PRIMARY_HOST, RESERVE_HOST, auto_config, reserve_config, reserve_link,
)

DIRECT = '11111111-2222-4333-8444-555555555555'
MOBILE = '22222222-3333-4444-8555-666666666666'


def links():
    return [
        f'vless://{DIRECT}@node.example:443?' + urlencode({
            'type': 'tcp', 'security': 'reality', 'sni': 'cover.example',
            'pbk': 'public-key', 'sid': 'a1b2', 'fp': 'chrome',
        }),
        f'vless://{MOBILE}@{PRIMARY_HOST}:443?' + urlencode({
            'type': 'xhttp', 'security': 'tls', 'sni': PRIMARY_HOST,
            'host': PRIMARY_HOST, 'path': '/wp-cw-device-route/', 'mode': 'packet-up',
            'extra': '{"uplinkHTTPMethod":"GET","uplinkDataPlacement":"header"}',
        }),
    ]


@pytest.mark.parametrize('routed', [True, False])
def test_auto_probes_every_candidate_without_probing_domestic_direct(routed):
    source = links()
    builder = build_routed_auto_config if routed else build_auto_route_config
    primary = builder(*source)[0]
    reserve = reserve_config(source[0], reserve_link(source, user_id=812, mobile_uuid=MOBILE),
                             routed=routed)
    snapshot = json.dumps([primary, reserve])
    config = auto_config(primary, reserve)
    expected = ['vpn-direct', 'vpn-cdn', 'vpn-reserve']
    assert config['observatory']['subjectSelector'] == expected
    assert config['observatory']['enableConcurrency'] is True
    assert config['observatory']['probeInterval'] == '15s'
    balancer = config['routing']['balancers'][0]
    assert balancer['selector'] == expected
    assert balancer['strategy'] == {'type': 'leastPing'}
    assert balancer['fallbackTag'] == 'vpn-reserve'
    actual_tags = {outbound['tag'] for outbound in config['outbounds']}
    assert set(expected).issubset(actual_tags)
    assert balancer['fallbackTag'] in actual_tags
    for rule in config['routing']['rules']:
        if 'balancerTag' in rule:
            assert rule['balancerTag'] == balancer['tag']
    reserve_outbound = next(o for o in config['outbounds'] if o['tag'] == 'vpn-reserve')
    assert reserve_outbound['settings']['vnext'][0]['address'] == RESERVE_HOST
    assert reserve_outbound['settings']['vnext'][0]['users'][0]['id'] == MOBILE
    assert reserve_outbound['streamSettings']['xhttpSettings']['extra']['uplinkHTTPMethod'] == 'PUT'
    assert config['outbounds'][:len(primary['outbounds'])] == primary['outbounds']
    assert config['routing']['rules'] == primary['routing']['rules']
    if routed:
        assert config['dns'] == primary['dns']
        assert 'ru-direct' not in expected
    assert json.dumps([primary, reserve]) == snapshot
    # Modifications to the Auto entry cannot affect the manual reserve.
    reserve_outbound['settings']['vnext'][0]['address'] = 'changed.example'
    assert json.dumps([primary, reserve]) == snapshot


@pytest.mark.parametrize('user_id', [812, 978])
def test_api_only_changes_pilot_and_preserves_hidden_settings(monkeypatch, user_id):
    from app.api import happ_auto_route as route
    from app.core.config import settings

    monkeypatch.setattr(settings, 'happ_auto_route_user_ids', '*')
    monkeypatch.setattr(settings, 'happ_hidden_settings_user_ids', '*')
    monkeypatch.setattr(settings, 'happ_provider_id', 'existing-provider')
    monkeypatch.setattr(route.subscription_token_service, 'resolve_token_scope',
                        lambda db, token: (SimpleNamespace(id=user_id), 'mobile'))
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
    assert response.headers['providerid'] == 'existing-provider'
    assert response.headers['hide-settings'] == '1'
    assert all(entry['meta']['serverDescription'] == 'Work&PlayVPN Pro' for entry in configs)
    if user_id == 812:
        assert len(configs) == 2
        assert configs[0]['remarks'] == 'Work&PlayVPN Pro — Авто'
        assert configs[0]['observatory']['subjectSelector'] == ['vpn-direct', 'vpn-cdn', 'vpn-reserve']
        assert configs[1]['remarks'] == 'Work&PlayVPN Pro — Вход 2'
        assert 'observatory' not in configs[1]
    else:
        assert len(configs) == 1
        assert configs[0]['observatory']['subjectSelector'] == ['vpn-direct']
        assert len(configs[0]['outbounds']) == 3
        assert configs[0]['routing']['balancers'][0]['fallbackTag'] == 'vpn-cdn'


def test_invalid_auto_keeps_existing_primary(monkeypatch):
    from app.api import happ_auto_route as route
    from app.core.config import settings

    monkeypatch.setattr(settings, 'happ_auto_route_user_ids', '*')
    monkeypatch.setattr(route.subscription_token_service, 'resolve_token_scope',
                        lambda db, token: (SimpleNamespace(id=812), 'mobile'))
    monkeypatch.setattr(route, 'active_entitlements', lambda db, uid: {
        'mobile': (SimpleNamespace(expires_at=None), object()),
    })
    device = SimpleNamespace(node_id=1, mobile_xray_uuid=MOBILE, mobile_xray_email='mobile@test')

    class Database:
        calls = 0
        def scalars(self, query):
            self.calls += 1
            value = [device] if self.calls == 1 else [SimpleNamespace(id=1)]
            return SimpleNamespace(all=lambda: value)

    monkeypatch.setattr(route.vpn_node_profile_service, 'get_active_profiles_for_nodes', lambda **kw: [])
    monkeypatch.setattr(route.subscription_builder, 'build', lambda **kw: links())
    def unavailable(*args):
        raise ValueError('Unavailable')
    monkeypatch.setattr(route, 'auto_config', unavailable)
    response = route.get_routed_mobile_subscription('private-token', Database())
    configs = json.loads(response.body)
    assert len(configs) == 2
    assert configs[0]['observatory']['subjectSelector'] == ['vpn-direct']
    assert configs[1]['remarks'] == 'Work&PlayVPN Pro — Вход 2'
