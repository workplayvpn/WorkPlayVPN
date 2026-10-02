import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import httpx
from handlers import help


class HelpKeyTests(unittest.IsolatedAsyncioTestCase):
    async def test_help_shows_personal_copy_button(self):
        key = 'tg-123-' + 'a' * 32
        response = httpx.Response(200, json={'key':key}, request=httpx.Request('GET','https://test.invalid'))
        callback = SimpleNamespace(data='help', from_user=SimpleNamespace(id=123), message=SimpleNamespace(chat=SimpleNamespace(type='private')), answer=AsyncMock())
        with patch.object(help, 'backend_get', AsyncMock(return_value=response)) as get, patch.object(help, 'edit_screen', AsyncMock()) as screen:
            await help.show_help(callback)
            get.assert_awaited_once_with('/internal/support/access-key/123')
            self.assertIn(key, screen.call_args.args[1])
            keyboard = screen.call_args.args[2]
            self.assertEqual(keyboard.inline_keyboard[0][0].copy_text.text, key)
            self.assertNotIn('<code>', screen.call_args.args[1])

    async def test_key_error_keeps_direct_support_available(self):
        callback = SimpleNamespace(data='help', from_user=SimpleNamespace(id=123), message=SimpleNamespace(chat=SimpleNamespace(type='private')), answer=AsyncMock())
        with patch.object(help, 'backend_get', AsyncMock(side_effect=RuntimeError('offline'))), patch.object(help, 'edit_screen', AsyncMock()) as screen:
            await help.show_help(callback)
            self.assertIn('Не удалось получить ключ', screen.call_args.args[1])
            links = [b.url for row in screen.call_args.args[2].inline_keyboard for b in row if b.url]
            self.assertIn('https://t.me/workplayvpnteam', links)

    async def test_group_cannot_reveal_personal_key(self):
        callback = SimpleNamespace(data='help', from_user=SimpleNamespace(id=123), message=SimpleNamespace(chat=SimpleNamespace(type='group')), answer=AsyncMock())
        with patch.object(help, 'backend_get', AsyncMock()) as get, patch.object(help, 'edit_screen', AsyncMock()) as screen:
            await help.show_help(callback)
            get.assert_not_called()
            screen.assert_not_called()
