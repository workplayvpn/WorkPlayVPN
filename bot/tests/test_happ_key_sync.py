import os
os.environ.setdefault('TELEGRAM_BOT_TOKEN', '123456789:test-token')
os.environ.setdefault('INTERNAL_API_SECRET', 'test-secret-for-offline-checks-only')
import unittest
from unittest.mock import AsyncMock, patch
from test_ui_sync import ACTIVE, callback, response
from handlers import subscription
from ui.subscription import build_subscription_secret_keyboard, build_subscription_keyboard


class KeySyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_account_key_requested_without_device_choice(self):
        with patch.object(subscription, '_load_subscription_data', AsyncMock(return_value=(ACTIVE,[],None))), patch.object(subscription,'backend_get',AsyncMock(return_value=response({'url':'happ://crypt5/mobile'}))) as request, patch.object(subscription,'edit_screen',AsyncMock()) as screen:
            await subscription.show_subscription_key(callback('subscription_key:mobile'))
            request.assert_awaited_once_with('/subscription-tokens/happ/mobile?telegram_id=123')
            self.assertNotIn('Выберите устройство', screen.call_args.args[1])

    async def test_group_cannot_reveal_key(self):
        cb = callback('subscription_key:basic:11')
        cb.message.chat.type = 'supergroup'
        with patch.object(subscription, '_load_subscription_data', AsyncMock()) as load:
            await subscription.show_subscription_key(cb)
            load.assert_not_called()

    async def test_stale_device_callback_uses_account_key(self):
        with patch.object(subscription,'_load_subscription_data',AsyncMock(return_value=(ACTIVE,[{'id':11}],None))), patch.object(subscription,'backend_get',AsyncMock(return_value=response({'url':'happ://crypt5/basic'}))) as request, patch.object(subscription,'edit_screen',AsyncMock()):
            await subscription.show_subscription_key(callback('subscription_key:basic:99'))
            request.assert_awaited_once_with('/subscription-tokens/happ/basic?telegram_id=123')

    async def test_long_key_is_complete_and_not_in_copy_button(self):
        key = 'happ://crypt5/' + 'A' * 1000
        cb = callback('subscription_key:basic:11')
        with patch.object(subscription,'_load_subscription_data',AsyncMock(return_value=(ACTIVE,[{'id':11}],None))), patch.object(subscription,'backend_get',AsyncMock(return_value=response({'url':key}))), patch.object(subscription,'edit_screen',AsyncMock()):
            await subscription.show_subscription_key(cb)
        cb.message.answer.assert_not_called()
        keyboard = build_subscription_secret_keyboard(copy_value=key,tier='basic')
        self.assertTrue(keyboard.inline_keyboard[0][0].web_app)
        self.assertIn('key_action=copy', keyboard.inline_keyboard[0][0].web_app.url)
        self.assertIn('key_tier=basic', keyboard.inline_keyboard[0][0].web_app.url)
        self.assertFalse(any(row[0].copy_text for row in keyboard.inline_keyboard))

    async def test_mobile_requests_single_account_link(self):
        get = AsyncMock(return_value=response({'url':'happ://crypt5/legacy'}))
        with patch.object(subscription,'_load_subscription_data',AsyncMock(return_value=(ACTIVE,[{'id':11}],None))), patch.object(subscription,'backend_get',get), patch.object(subscription,'edit_screen',AsyncMock()):
            await subscription.show_subscription_key(callback('subscription_key:mobile:11'))
        get.assert_awaited_once_with('/subscription-tokens/happ/mobile?telegram_id=123')

    async def test_encryption_error_does_not_reveal_plaintext(self):
        cb = callback('subscription_key:basic:11')
        with patch.object(subscription,'_load_subscription_data',AsyncMock(return_value=(ACTIVE,[{'id':11}],None))), patch.object(subscription,'backend_get',AsyncMock(return_value=response({},503))), patch.object(subscription,'edit_screen',AsyncMock()):
            await subscription.show_subscription_key(cb)
        cb.message.answer.assert_not_called()

    def test_subscription_copy_button_targets_correct_tier(self):
        for tier in ('basic', 'mobile'):
            button = build_subscription_keyboard(active=True, tier=tier).inline_keyboard[0][0]
            self.assertEqual(button.text, '📋 Скопировать ключ')
            self.assertIn('key_action=copy', button.web_app.url)
            self.assertIn('key_tier='+tier, button.web_app.url)
