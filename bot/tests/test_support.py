import unittest
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
from handlers import support

class SupportAdminTests(unittest.IsolatedAsyncioTestCase):
    def message(self,uid=123,kind="private"):
        return SimpleNamespace(from_user=SimpleNamespace(id=uid),chat=SimpleNamespace(type=kind),answer=AsyncMock())
    async def test_non_admin_cannot_read_queue(self):
        with patch.object(support,"support_admin_telegram_id",123),patch.object(support,"backend_get",new=AsyncMock()) as get:
            await support.commands(self.message(456),SimpleNamespace(command="tickets",args=None));get.assert_not_called()
    async def test_admin_command_in_group_is_ignored(self):
        with patch.object(support,"support_admin_telegram_id",123),patch.object(support,"backend_get",new=AsyncMock()) as get:
            await support.commands(self.message(kind="group"),SimpleNamespace(command="tickets",args=None));get.assert_not_called()
    async def test_owner_queue_and_status_reply(self):
        response=SimpleNamespace(raise_for_status=lambda:None,json=lambda:[])
        message=self.message()
        with patch.object(support,"support_admin_telegram_id",123),patch.object(support,"backend_get",new=AsyncMock(return_value=response)):
            await support.commands(message,SimpleNamespace(command="tickets",args=None));message.answer.assert_awaited_once_with("Открытых обращений нет.")
    async def test_disabled_notification_task_has_no_side_effect(self):
        bot=SimpleNamespace(send_message=AsyncMock())
        with patch.object(support,"support_admin_telegram_id",0),patch.object(support,"backend_get",new=AsyncMock()) as get:
            await support.deliver_notifications(bot);get.assert_not_called();bot.send_message.assert_not_called()

    async def test_failed_delivery_is_not_acknowledged(self):
        import asyncio
        ticket=dict(id="test-uuid",kind="admin",revision=0,telegram_id=456,category="connection",tier="basic",network="wifi",description="Ошибка подключения")
        response=SimpleNamespace(raise_for_status=lambda:None,json=lambda:[ticket])
        bot=SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError("unavailable")))
        with patch.object(support,"support_admin_telegram_id",123),patch.object(support,"backend_get",new=AsyncMock(return_value=response)),patch.object(support,"backend_post",new=AsyncMock()) as ack,patch.object(support.asyncio,"sleep",new=AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError): await support.deliver_notifications(bot)
            bot.send_message.assert_awaited_once();ack.assert_not_called()
