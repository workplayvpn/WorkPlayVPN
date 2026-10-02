import os
os.environ.setdefault('TELEGRAM_BOT_TOKEN','123456789:test-token')
os.environ.setdefault('INTERNAL_API_SECRET','test-secret-for-offline-checks-only')
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import httpx
from handlers.start import handle_start

class ReferralStartTests(unittest.IsolatedAsyncioTestCase):
    async def test_referral_registration_payload(self):
        msg=SimpleNamespace(from_user=SimpleNamespace(id=111,username='test',first_name='Test'),answer=AsyncMock())
        for status in (201,409):
            with patch('handlers.start.backend_post',new_callable=AsyncMock) as post,patch('handlers.start.send_home_message',new_callable=AsyncMock):
                post.return_value=httpx.Response(status)
                await handle_start(msg,SimpleNamespace(args='ref_'+'a'*24))
                self.assertEqual(post.call_args.args[1]['referral_code'],'a'*24)
    async def test_invalid_argument_ignored(self):
        msg=SimpleNamespace(from_user=SimpleNamespace(id=111,username=None,first_name='Test'),answer=AsyncMock())
        for arg in (None,'ref_123','ref_'+'a'*24+' extra','https://example.com'):
            with patch('handlers.start.backend_post',new_callable=AsyncMock) as post,patch('handlers.start.send_home_message',new_callable=AsyncMock):
                post.return_value=httpx.Response(201)
                await handle_start(msg,SimpleNamespace(args=arg))
                self.assertNotIn('referral_code',post.call_args.args[1])
