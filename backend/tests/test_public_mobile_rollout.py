from unittest.mock import MagicMock
import pytest
from app.core.config import settings
from app.services.rollout_access import rollout_allowed
from app.services.mobile_rollout import mobile_pilot_allowed
from app.api.happ_auto_route import auto_route_allowed
from app.api.subscription_feed import should_enable_happ_feature
from app.services.happ_subscription_info import hidden_settings_metadata
from app.api import happ_connect


@pytest.mark.parametrize('control,user_id,expected',[
    ('',999,False),('174',999,False),('174',174,True),('1, 174',174,True),
    ('*',999,True),(' 174, * ',999,True),('all',999,False),('*oops',999,False)])
def test_rollout_selection(control,user_id,expected):
    assert rollout_allowed(control,user_id) is expected


def test_public_mobile_and_auto_use_the_same_wildcard(monkeypatch):
    monkeypatch.setattr(settings,'mobile_pilot_user_ids','*')
    monkeypatch.setattr(settings,'happ_auto_route_user_ids','*')
    assert mobile_pilot_allowed(999)
    assert auto_route_allowed(999)
    monkeypatch.setattr(settings,'mobile_pilot_user_ids','174')
    monkeypatch.setattr(settings,'happ_auto_route_user_ids','174')
    assert not mobile_pilot_allowed(999)
    assert not auto_route_allowed(999)


def test_wildcard_does_not_add_happ_headers_to_other_clients():
    assert should_enable_happ_feature(client='happ',user_id=999,configured_user_ids='*')
    assert not should_enable_happ_feature(client='v2ray',user_id=999,configured_user_ids='*')


def test_public_provider_still_requires_valid_id():
    assert hidden_settings_metadata(provider_id='wp_provider',user_id=999,allowed_ids='*')['hide-settings']=='1'
    assert hidden_settings_metadata(provider_id='',user_id=999,allowed_ids='*')=={}


def test_public_crypt_import_and_closed_fallback(monkeypatch):
    monkeypatch.setattr(settings,'happ_crypt5_user_ids','*')
    encrypt=MagicMock(return_value='happ://crypt5/test')
    monkeypatch.setattr(happ_connect,'encrypted_happ_link',encrypt)
    assert happ_connect._import_link('https://test.local/feed',999)=='happ://crypt5/test'
    monkeypatch.setattr(settings,'happ_crypt5_user_ids','174')
    assert happ_connect._import_link('https://test.local/feed',999)=='happ://add/https://test.local/feed'
    encrypt.assert_called_once()
