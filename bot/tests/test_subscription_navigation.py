"""Subscription-origin navigation checks; no real API calls or purchases."""
import os
os.environ.setdefault('TELEGRAM_BOT_TOKEN', '123456789:test-token')
os.environ.setdefault('INTERNAL_API_SECRET', 'offline-test-secret')
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from handlers import device_slots, locations, plans
from ui.subscription import build_subscription_keyboard
from ui.navigation import subscription_tier
from ui.media import get_screen_photo


def callback(data):
    return SimpleNamespace(data=data, from_user=SimpleNamespace(id=123),
        answer=AsyncMock(), message=MagicMock(), id='offline-navigation')


def response(payload, status=200):
    return httpx.Response(status, json=payload, request=httpx.Request('GET', 'http://test/'))


def actions(screen):
    return [button.callback_data for row in screen.call_args.args[2].inline_keyboard for button in row]


OFFERS = {'total_limit': 6, 'offers': [
    {'slots': 1, 'price_amount': '249.00', 'new_limit': 7, 'code': 'device_slots_1'}]}
REGIONS = [{'code': 'NL', 'name': 'Нидерланды', 'available': True}]


class NavigationTests(unittest.TestCase):
    def test_subscription_buttons_carry_origin(self):
        for tier in ('basic', 'mobile'):
            with self.subTest(tier=tier):
                buttons = [b.callback_data for row in build_subscription_keyboard(active=True, tier=tier).inline_keyboard for b in row]
                self.assertIn('device_slots:'+tier, buttons)
                self.assertIn('change_region:'+tier, buttons)
                self.assertTrue(all(len(b.encode()) <= 64 for b in buttons if b))

    def test_region_banner_and_unknown_origin(self):
        self.assertTrue(str(get_screen_photo('change_region:basic', '').path).endswith('region.png'))
        self.assertIsNone(subscription_tier('device_slots:invalid'))


class FlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_slot_offer_back_and_purchase_preserve_both_tiers(self):
        for tier in ('basic', 'mobile'):
            with self.subTest(tier=tier), patch.object(device_slots, 'backend_get', AsyncMock(return_value=response(OFFERS))), patch.object(device_slots, 'edit_screen', AsyncMock()) as screen:
                await device_slots.show_slots(callback('device_slots:'+tier))
                self.assertEqual(actions(screen), ['buy_slots:device_slots_1:'+tier, 'subscription_tier:'+tier])

    async def test_legacy_slot_offer_stays_compatible(self):
        with patch.object(device_slots, 'backend_get', AsyncMock(return_value=response(OFFERS))), patch.object(device_slots, 'edit_screen', AsyncMock()) as screen:
            await device_slots.show_slots(callback('device_slots'))
            self.assertEqual(actions(screen), ['buy_slots:device_slots_1', 'subscription'])

    async def test_slot_offer_errors_preserve_origin(self):
        for tier in ('basic', 'mobile'):
            with patch.object(device_slots, 'backend_get', AsyncMock(return_value=response({}, 409))), patch.object(device_slots, 'edit_screen', AsyncMock()) as screen:
                await device_slots.show_slots(callback('device_slots:'+tier))
                self.assertEqual(actions(screen)[-1], 'subscription_tier:'+tier)
            with patch.object(device_slots, 'backend_get', AsyncMock(side_effect=httpx.ConnectError('offline'))), patch.object(device_slots, 'edit_screen', AsyncMock()) as screen:
                await device_slots.show_slots(callback('device_slots:'+tier))
                self.assertEqual(actions(screen), ['device_slots:'+tier, 'subscription_tier:'+tier])

    async def test_slot_payment_returns_to_origin_offer(self):
        for tier in ('basic', 'mobile'):
            with patch.object(device_slots, 'backend_post', AsyncMock(return_value=response({'id': 7, 'amount': '249.00', 'confirmation_url': 'https://pay.test'}, 201))) as backend, patch.object(device_slots, 'edit_screen', AsyncMock()) as screen:
                await device_slots.buy_slots(callback('buy_slots:device_slots_1:'+tier))
                self.assertEqual(backend.call_args.args[1]['plan_code'], 'device_slots_1')
                self.assertEqual(actions(screen)[-1], 'device_slots:'+tier)
                self.assertEqual(backend.await_count, 1)

    async def test_failed_slot_payment_returns_to_origin_offer(self):
        for tier in ('basic', 'mobile'):
            with patch.object(device_slots, 'backend_post', AsyncMock(return_value=response({}, 409))), patch.object(device_slots, 'edit_screen', AsyncMock()) as screen:
                await device_slots.buy_slots(callback('buy_slots:device_slots_1:'+tier))
                self.assertEqual(actions(screen), ['device_slots:'+tier])

    async def test_region_choice_back_and_action_preserve_origin(self):
        for tier in ('basic', 'mobile'):
            with patch.object(locations, 'backend_get', AsyncMock(return_value=response(REGIONS))), patch.object(locations, 'edit_screen', AsyncMock()) as screen:
                await locations.show_region_devices(callback('change_region:'+tier))
                self.assertEqual(actions(screen), ['account_region:NL:'+tier, 'subscription_tier:'+tier])

    async def test_region_result_keeps_origin_and_sends_region_code(self):
        for tier in ('basic', 'mobile'):
            with patch.object(locations, 'backend_patch', AsyncMock(return_value=response({'name': 'Нидерланды'}))) as backend, patch.object(locations, 'edit_screen', AsyncMock()) as screen:
                await locations.change_device_region(callback('account_region:NL:'+tier))
                self.assertEqual(backend.call_args.args, ('/users/123/region', {'location_code': 'NL'}))
                self.assertEqual(actions(screen), ['change_region:'+tier, 'subscription_tier:'+tier])

    async def test_legacy_region_callbacks_keep_region_code(self):
        for data in ('account_region:NL', 'region_location:7:NL'):
            with patch.object(locations, 'backend_patch', AsyncMock(return_value=response({'name': 'NL'}))) as backend, patch.object(locations, 'edit_screen', AsyncMock()) as screen:
                await locations.change_device_region(callback(data))
                self.assertEqual(backend.call_args.args[1], {'location_code': 'NL'})
                self.assertEqual(actions(screen), ['change_region', 'subscription'])

    async def test_region_errors_keep_origin(self):
        for tier in ('basic', 'mobile'):
            with patch.object(locations, 'backend_get', AsyncMock(side_effect=httpx.ConnectError('offline'))), patch.object(locations, 'edit_screen', AsyncMock()) as screen:
                await locations.show_region_devices(callback('change_region:'+tier))
                self.assertEqual(actions(screen), ['change_region:'+tier, 'subscription_tier:'+tier])
            with patch.object(locations, 'backend_patch', AsyncMock(return_value=response({}, 409))), patch.object(locations, 'edit_screen', AsyncMock()) as screen:
                await locations.change_device_region(callback('account_region:NL:'+tier))
                self.assertEqual(actions(screen), ['change_region:'+tier, 'subscription_tier:'+tier])

    async def test_confirmation_explains_included_devices_without_creating_payment(self):
        catalog = [{'code': 'standard_1m', 'access_tier': 'basic', 'duration_days': 30,
                    'price_amount': '199.00', 'device_limit': 3}]
        with patch.object(plans, 'backend_get', AsyncMock(return_value=response(catalog))), patch.object(plans, 'backend_post', AsyncMock()) as post, patch.object(plans, 'edit_screen', AsyncMock()) as screen:
            await plans.select_plan(callback('select_plan:standard_1m:main'))
            self.assertIn('В тариф включено устройств: 3', screen.call_args.args[1])
            self.assertIn('Купленные дополнительные слоты сохраняются.', screen.call_args.args[1])
            post.assert_not_awaited()
