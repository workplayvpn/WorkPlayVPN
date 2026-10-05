import os
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456789:test-token")
os.environ.setdefault("INTERNAL_API_SECRET", "test-secret-for-offline-checks-only")
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import httpx
from handlers.start import handle_start
from ui.main import main_menu


class GiftStartTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, arg, chat_type="private"):
        message = SimpleNamespace(from_user=SimpleNamespace(id=111, username="test", first_name="Test"),
                                  chat=SimpleNamespace(type=chat_type), answer=AsyncMock())
        with patch("handlers.start.backend_post", new_callable=AsyncMock) as post, patch("handlers.start.send_home_message", new_callable=AsyncMock) as home:
            post.return_value = httpx.Response(409)
            await handle_start(message, SimpleNamespace(args=arg))
            return message, post, home

    async def test_private_gift_opens_confirmation_without_redemption(self):
        message, post, home = await self.invoke("gift_"+"A"*24)
        home.assert_not_awaited()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.args[0], "/users")
        keyboard = message.answer.call_args.kwargs["reply_markup"]
        self.assertIn("view=gifts&gift_code="+"A"*24, keyboard.inline_keyboard[0][0].web_app.url)

    async def test_group_does_not_reveal_gift_button(self):
        message, post, home = await self.invoke("gift_"+"A"*24, "group")
        message.answer.assert_not_awaited()
        home.assert_awaited_once()

    async def test_invalid_code_uses_home(self):
        for arg in ("gift_invalid", "gift_"+"A"*24+" extra"):
            message, post, home = await self.invoke(arg)
            home.assert_awaited_once()

    def test_gifts_has_separate_menu_button(self):
        self.assertTrue(any(button.text=="🎁 Подарки" and "view=gifts" in button.web_app.url
                            for row in main_menu.inline_keyboard for button in row if button.web_app))
