"""Real server-side access checks, not UI-only locks."""
import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db.session import Base
from app.db.dependencies import get_db
from app.models.user import User
from app.models.subscription_token import SubscriptionToken
from app.api.help_access import router
from app.api.support import router as tickets_router
from app.api.telegram_webapp_auth import require_telegram_webapp_auth
from app.services import help_access


class HelpAccessTests(unittest.TestCase):
    def setUp(self):
        for name in ("location", "plan", "subscription", "payment", "payment_fulfillment", "vpn_node", "vpn_node_profile", "vpn_device", "device_activation", "referral", "support_ticket"):
            importlib.import_module("app.models." + name)
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.db.add_all([User(id=1, telegram_id=101, is_active=True), User(id=2, telegram_id=102, is_active=True)])
        self.db.add_all([SubscriptionToken(id=1, user_id=1, version=1), SubscriptionToken(id=2, user_id=2, version=1)])
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.include_router(tickets_router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[require_telegram_webapp_auth] = lambda: SimpleNamespace(user=SimpleNamespace(id=101))
        self.client = TestClient(self.app, base_url="https://testserver")
        help_access._attempts.clear()
        self.key = help_access.key_for(self.db.get(User, 1), self.db.get(SubscriptionToken, 1))

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def login(self, mini=False, key=None):
        return self.client.post("/mini-app/support/login" if mini else "/help-access/login", json={"key": key or self.key})

    def test_knowledge_and_tickets_reject_without_key(self):
        for path in ("/help-access/knowledge", "/help-access/session", "/mini-app/support/session", "/mini-app/support/knowledge", "/mini-app/support/tickets"):
            self.assertEqual(self.client.get(path).status_code, 403, path)
        result = self.client.post("/mini-app/support/tickets", json={"category":"other", "description":"Это тестовое обращение поддержки", "idempotency_key":"valid-test-key-0001"})
        self.assertEqual(result.status_code, 403)

    def test_key_opens_only_help_and_cookie_is_protected(self):
        result = self.login()
        self.assertEqual(result.status_code, 200)
        cookie = result.headers['set-cookie'].lower()
        for flag in ('httponly', 'secure', 'samesite=strict', 'path=/'):
            self.assertIn(flag, cookie)
        self.assertNotIn(self.key.lower(), cookie)
        self.assertEqual(self.client.get('/help-access/session').status_code, 200)
        public = self.client.get('/help-access/knowledge')
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.headers['cache-control'], 'no-store, private')
        self.assertNotIn('Pro', public.text)
        self.assertEqual(self.client.get('/internal/support/access-key/101').status_code, 401)

    def test_mini_login_cannot_use_foreign_key(self):
        other = help_access.key_for(self.db.get(User, 2), self.db.get(SubscriptionToken, 2))
        self.assertEqual(self.login(mini=True, key=other).status_code, 403)
        self.assertEqual(self.client.get('/mini-app/support/knowledge').status_code, 403)
        # Even a public-site session for another user cannot replace Telegram auth.
        self.assertEqual(self.login(key=other).status_code, 200)
        self.assertEqual(self.client.get('/mini-app/support/tickets').status_code, 403)

    def test_mini_access_requires_both_key_and_telegram(self):
        self.assertEqual(self.login(mini=True).status_code, 200)
        self.assertEqual(self.client.get('/mini-app/support/knowledge').status_code, 200)
        self.app.dependency_overrides.pop(require_telegram_webapp_auth)
        self.assertEqual(self.client.get('/mini-app/support/knowledge').status_code, 401)
        self.assertEqual(self.client.get('/mini-app/support/tickets').status_code, 401)

    def test_invalid_and_forged_keys_fail_uniformly(self):
        for key in ('tg-101-incorrect', 'tg-9999999999999999999-' + 'a'*32, self.key[:-1] + ('a' if self.key[-1] != 'a' else 'b')):
            self.assertEqual(self.login(key=key).status_code, 401)
        self.assertEqual(self.client.get('/help-access/knowledge').status_code, 403)

    def test_session_expiry_and_token_rotation(self):
        self.login()
        with patch.object(help_access.time, 'time', return_value=help_access.time.time()+3601):
            self.assertEqual(self.client.get('/help-access/knowledge').status_code, 403)
        token = self.db.get(SubscriptionToken, 1)
        token.version = 2
        self.db.commit()
        self.assertEqual(self.client.get('/help-access/knowledge').status_code, 403)
        self.assertEqual(self.login().status_code, 401)

    def test_disabled_account_and_logout(self):
        self.login()
        self.assertEqual(self.client.post('/help-access/logout').status_code, 200)
        self.assertEqual(self.client.get('/help-access/session').status_code, 403)
        self.login()
        self.db.get(User, 1).is_active = False
        self.db.commit()
        self.assertEqual(self.client.get('/help-access/knowledge').status_code, 403)
        self.assertEqual(self.login().status_code, 401)

    def test_cross_site_write_is_rejected(self):
        result = self.client.post('/help-access/login', json={'key':self.key}, headers={'Origin':'https://foreign.invalid'})
        self.assertEqual(result.status_code, 403)
        self.assertEqual(self.client.post('/help-access/logout', headers={'Origin':'https://foreign.invalid'}).status_code, 403)

    def test_get_own_key_without_paid_subscription(self):
        # No active subscriptions in this fixture: help remains available.
        result = self.client.get('/mini-app/support/access-key')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['key'], self.key)
        self.assertNotIn('subscription_url', result.json())

    def test_attempts_are_throttled(self):
        for _ in range(30):
            self.login(key='bad')
        result = self.login()
        self.assertEqual(result.status_code, 429)
        self.assertEqual(result.headers['retry-after'], '60')

    def test_tampered_session_is_rejected(self):
        self.login()
        value = self.client.cookies.get(help_access.COOKIE)
        parts = value.split('.')
        parts[0] = '2'
        self.client.cookies.clear()
        self.client.cookies.set(help_access.COOKIE, '.'.join(parts), domain='testserver.local', path='/')
        self.assertEqual(self.client.get('/help-access/knowledge').status_code, 403)

    def test_mini_header_session_works_without_cookies(self):
        value = self.login(mini=True).json()['session']
        self.assertNotIn(self.key, value)
        self.client.cookies.clear()
        headers = {'X-Help-Session': value}
        for path in ('/mini-app/support/session', '/mini-app/support/knowledge', '/mini-app/support/tickets'):
            self.assertEqual(self.client.get(path, headers=headers).status_code, 200, path)
        self.assertEqual(self.client.get('/mini-app/support/session').status_code, 403)
        self.assertEqual(self.client.get('/help-access/knowledge', headers=headers).status_code, 403)
        self.client.cookies.set(help_access.COOKIE, value)
        self.assertEqual(self.client.get('/help-access/session').status_code, 403)
        self.client.cookies.clear()
        self.app.dependency_overrides.pop(require_telegram_webapp_auth)
        self.assertEqual(self.client.get('/mini-app/support/session', headers=headers).status_code, 401)

    def test_mini_header_session_cannot_cross_accounts(self):
        value = self.login(mini=True).json()['session']
        self.client.cookies.clear()
        self.app.dependency_overrides[require_telegram_webapp_auth] = lambda: SimpleNamespace(user=SimpleNamespace(id=102))
        self.assertEqual(self.client.get('/mini-app/support/session', headers={'X-Help-Session': value}).status_code, 403)

    def test_mini_header_session_rejects_forgery_expiry_and_rotation(self):
        value = self.login(mini=True).json()['session']
        self.client.cookies.clear()
        headers = {'X-Help-Session': value}
        forged = value[:-1] + ('a' if value[-1] != 'a' else 'b')
        self.assertEqual(self.client.get('/mini-app/support/session', headers={'X-Help-Session': forged}).status_code, 403)
        with patch.object(help_access.time, 'time', return_value=help_access.time.time()+3601):
            self.assertEqual(self.client.get('/mini-app/support/session', headers=headers).status_code, 403)
        token = self.db.get(SubscriptionToken, 1)
        token.version = 2
        self.db.commit()
        self.assertEqual(self.client.get('/mini-app/support/session', headers=headers).status_code, 403)

    def test_invalid_header_does_not_fall_back_to_cookie(self):
        self.login(mini=True)
        self.assertEqual(self.client.get('/mini-app/support/session', headers={'X-Help-Session': 'invalid'}).status_code, 403)
