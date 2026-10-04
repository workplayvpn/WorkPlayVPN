"""Offline checks: no Telegram requests and no payments are sent."""
import os
os.environ.setdefault('TELEGRAM_BOT_TOKEN', '123456789:test-token')
os.environ.setdefault('INTERNAL_API_SECRET', 'test-secret-for-offline-checks-only')
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from ui.main import main_menu
from texts.description import DESCRIPTION, SHORT_DESCRIPTION
from ui.subscription import build_subscription_keyboard
from ui.media import get_screen_photo
from handlers import subscription, plans, locations
from ui.helpers import edit_screen


def response(payload, status=200):
    return httpx.Response(status, json=payload, request=httpx.Request('GET','http://test/'))


def callback(data):
    message = MagicMock()
    message.chat.type = 'private'
    message.answer = AsyncMock()
    return SimpleNamespace(data=data, from_user=SimpleNamespace(id=123), answer=AsyncMock(), message=message, id='offline-check')


ACTIVE={'status':'active','total_device_limit':5,'active_subscriptions':[
    {'access_tier':'basic','expires_at':'2026-12-01T00:00:00+00:00'},
    {'access_tier':'mobile','expires_at':'2026-12-02T00:00:00+00:00'}]}
CATALOG=[{'code':'standard_1m','access_tier':'basic','duration_days':30,'price_amount':'199.00','name':'1 месяц','device_limit':3},
         {'code':'mobile_1m','access_tier':'mobile','duration_days':30,'price_amount':'249.00','name':'Mobile 30 дней','device_limit':3}]


class MenuTests(unittest.TestCase):
    def test_catalogue_mobile_first_and_basic_neutral(self):
        from ui.subscription import build_tier_keyboard
        rows = build_tier_keyboard({'basic', 'mobile'}, 'plans_tier').inline_keyboard
        self.assertEqual(rows[0][0].text, '📲 Mobile')
        self.assertEqual(rows[0][0].style, 'primary')
        self.assertIsNone(rows[1][0].style)

    def test_terms_back_to_catalogue_and_compact_mobile_labels(self):
        from ui.plans import build_plans_keyboard
        rows = build_plans_keyboard([CATALOG[1]], source='subscription').inline_keyboard
        self.assertEqual(rows[-1][0].callback_data, 'plans')
        self.assertEqual(rows[0][0].text, '1 месяц — 249 ₽')

    def test_bot_description_limits(self):
        self.assertLessEqual(len(SHORT_DESCRIPTION),120)
        self.assertLessEqual(len(DESCRIPTION),512)
        self.assertIn("Basic",DESCRIPTION)
        self.assertIn("Mobile",DESCRIPTION)

    def test_primary_buttons_first(self):
        for keyboard in [main_menu,build_subscription_keyboard(active=True,tier='basic'),build_subscription_keyboard(active=True,tier='mobile')]:
            styles=[row[0].style=='primary' for row in keyboard.inline_keyboard]
            self.assertEqual(styles,sorted(styles,reverse=True))
            self.assertTrue(all(len(row)==1 for row in keyboard.inline_keyboard))

    def test_slot_payment_keyboard(self):
        from ui.payments import build_payment_keyboard
        rows = build_payment_keyboard('https://pay.test', 7, source='slots').inline_keyboard
        self.assertEqual(rows[0][0].url, 'https://pay.test')
        self.assertEqual(rows[-1][0].callback_data, 'device_slots')

    def test_referral_link(self):
        buttons=[row[0] for row in main_menu.inline_keyboard]
        self.assertTrue(any(b.web_app and 'view=referrals' in b.web_app.url for b in buttons))

    def test_banner_changes(self):
        self.assertTrue(str(get_screen_photo('subscription_key:basic','Key').path).endswith('key.png'))
        self.assertTrue(str(get_screen_photo('plans_tier:mobile','Terms').path).endswith('terms.png'))
        self.assertTrue(str(get_screen_photo('main_menu','Home').path).endswith('welcome.png'))

    def test_device_metadata_and_shared_limit(self):
        text=subscription._build_subscription_text(ACTIVE,[{'device_name':'iPhone 14 Pro Max (iOS 27.0)','public_id':'WP-TEST'}])
        self.assertIn('1 из 5',text)
        self.assertIn('iPhone 14 Pro Max (iOS 27.0)',text)
        self.assertIn('WP-TEST',text)
        self.assertIn('01.12.2026',text)
        self.assertIn('02.12.2026',text)


class FlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_slot_purchase_creates_correct_payment_and_button(self):
        from handlers import device_slots
        with patch.object(device_slots, 'backend_post', AsyncMock(return_value=response({'id': 7, 'amount': '449.00', 'confirmation_url': 'https://pay.test'},201))) as payment, patch.object(device_slots, 'edit_screen', AsyncMock()) as screen:
            await device_slots.buy_slots(callback('buy_slots:device_slots_2'))
            self.assertEqual(payment.call_args.args[1]['plan_code'],'device_slots_2')
            self.assertEqual(screen.call_args.args[2].inline_keyboard[0][0].url,'https://pay.test')

    async def test_terms_describe_basic_and_mobile(self):
        for tier, phrase in [('basic','рабочих сервисов'),('mobile','резервный маршрут')]:
            with patch.object(plans,'backend_get',AsyncMock(return_value=response(CATALOG))),patch.object(plans,'edit_screen',AsyncMock()) as screen:
                await plans.show_plans(callback('plans_tier:'+tier))
                self.assertIn(phrase,screen.call_args.args[1])

    async def test_catalogue_selects_tier_before_duration(self):
        with patch.object(plans,'backend_get',AsyncMock(return_value=response(CATALOG))), patch.object(plans,'edit_screen',AsyncMock()) as screen:
            await plans.show_plans(callback('plans'))
            rows=screen.call_args.args[2].inline_keyboard
            self.assertEqual([r[0].callback_data for r in rows[:-1]],['plans_tier:mobile','plans_tier:basic'])
            self.assertNotIn('249',screen.call_args.args[1])
            await plans.show_plans(callback('plans_tier:mobile'))
            rows=screen.call_args.args[2].inline_keyboard
            self.assertEqual(rows[0][0].callback_data,'select_plan:mobile_1m:main')
            self.assertFalse(any('standard_' in (r[0].callback_data or '') for r in rows))

    async def test_qr_uses_selected_tier_link(self):
        for tier in ('basic', 'mobile'):
            payload = {'url': 'happ://crypt5/' + tier, 'qr_png_base64': 'cG5n'}
            with patch.object(subscription,'_load_subscription_data',AsyncMock(return_value=(ACTIVE,[{'id':11}],None))), patch.object(subscription,'backend_get',AsyncMock(return_value=response(payload))) as request, patch.object(subscription,'edit_screen',AsyncMock()) as screen:
                await subscription.show_subscription_qr(callback(f'subscription_qr:{tier}:11'))
                request.assert_awaited_once_with(f'/subscription-tokens/happ/{tier}?telegram_id=123')
                self.assertEqual(screen.call_args.kwargs['photo'].data, b'png')

    async def test_legacy_qr_requests_tier_choice(self):
        with patch.object(subscription,'_load_subscription_data',AsyncMock(return_value=(ACTIVE,[],None))),patch.object(subscription,'_get_token',AsyncMock()) as token,patch.object(subscription,'edit_screen',AsyncMock()) as screen:
            await subscription.show_subscription_qr(callback('subscription_qr'))
            token.assert_not_called()
            self.assertIn('subscription_qr:mobile',[r[0].callback_data for r in screen.call_args.args[2].inline_keyboard])

    async def test_inactive_mobile_cannot_get_basic_qr(self):
        only_basic=dict(ACTIVE,active_subscriptions=ACTIVE['active_subscriptions'][:1])
        with patch.object(subscription,'_load_subscription_data',AsyncMock(return_value=(only_basic,[],None))),patch.object(subscription,'_get_token',AsyncMock()) as token,patch.object(subscription,'edit_screen',AsyncMock()):
            await subscription.show_subscription_qr(callback('subscription_qr:mobile'))
            token.assert_not_called()

    async def test_stale_mobile_purchase_does_not_create_payment(self):
        with patch.object(plans,'backend_get',AsyncMock(return_value=response(CATALOG[:1]))),patch.object(plans,'backend_post',AsyncMock()) as payment,patch.object(plans,'edit_screen',AsyncMock()):
            await plans.pay_plan(callback('pay_plan:mobile_1m:subscription'))
            payment.assert_not_called()

    async def test_renewal_keeps_mobile_plan_code(self):
        with patch.object(plans,'backend_get',AsyncMock(return_value=response(CATALOG))),patch.object(plans,'backend_post',AsyncMock(return_value=response({'confirmation_url':'https://pay.test','id':1,'amount':'249.00'},201))) as payment,patch.object(plans,'edit_screen',AsyncMock()):
            await plans.pay_plan(callback('pay_plan:mobile_1m:subscription'))
            self.assertEqual(payment.call_args.args[1]['plan_code'],'mobile_1m')

    async def test_region_changes_whole_account(self):
        with patch.object(locations,'backend_patch',AsyncMock(return_value=response({'name':'Нидерланды'}))) as backend,patch.object(locations,'edit_screen',AsyncMock()):
            await locations.change_device_region(callback('region_location:99:NL'))
            self.assertEqual(backend.call_args.args[0],'/users/123/region')
            self.assertEqual(backend.call_args.args[1],{'location_code':'NL'})

    async def test_leaving_qr_replaces_media(self):
        cb=callback('plans')
        cb.message.edit_media=AsyncMock()
        await edit_screen(cb,'Catalogue',main_menu)
        self.assertTrue(str(cb.message.edit_media.call_args.kwargs['media'].media.path).endswith('plans.png'))

    async def test_long_caption_has_readable_text(self):
        cb=callback('devices')
        cb.message.edit_media=AsyncMock()
        cb.message.answer=AsyncMock()
        await edit_screen(cb,'Devices\n'+'x'*1200,main_menu)
        self.assertLessEqual(len(cb.message.edit_media.call_args.kwargs['media'].caption),1024)
        cb.message.answer.assert_awaited_once()



if __name__ == '__main__':
    unittest.main()


class RenewalNavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_catalogue_and_renewal_back_targets(self):
        for tier in ('basic', 'mobile'):
            for renewal in (False, True):
                data = f'plans_tier:{tier}' + (':renew' if renewal else '')
                with patch.object(plans, 'backend_get', AsyncMock(return_value=response(CATALOG))), patch.object(plans, 'edit_screen', AsyncMock()) as screen:
                    await plans.show_plans(callback(data))
                    rows = screen.call_args.args[2].inline_keyboard
                    self.assertEqual(rows[-1][0].callback_data, f'subscription_tier:{tier}' if renewal else 'plans')
                    self.assertTrue(rows[0][0].callback_data.endswith(f':renew_{tier}' if renewal else ':main'))

    def test_payment_back_preserves_renewal(self):
        from ui.payments import build_payment_confirmation_keyboard, build_payment_keyboard
        for tier in ('basic', 'mobile'):
            buttons = [row[0] for row in build_subscription_keyboard(active=True, tier=tier).inline_keyboard]
            self.assertTrue(any(b.callback_data == f'plans_tier:{tier}:renew' for b in buttons))
            for keyboard in (build_payment_confirmation_keyboard('standard_1m', source=f'renew_{tier}'), build_payment_keyboard('https://pay.test', 1, source=f'renew_{tier}')):
                self.assertEqual(keyboard.inline_keyboard[-1][0].callback_data, f'plans_tier:{tier}:renew')
