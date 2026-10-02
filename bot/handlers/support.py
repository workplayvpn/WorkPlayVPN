"""Owner-only support commands and durable notification delivery."""
import asyncio
import logging
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import Message
from config import support_admin_telegram_id
from api.backend import backend_get, backend_post

router = Router(name="support-admin")

@router.message(Command("support_id"))
async def show_support_id(message: Message):
    if message.chat.type == "private" and message.from_user:
        await message.answer(f"Твой Telegram ID для настройки поддержки: {message.from_user.id}")
STATUS = {"new":"Новое", "in_progress":"В работе", "resolved":"Решено", "closed":"Закрыто"}

def is_admin(message):
    return bool(support_admin_telegram_id and message.chat.type=="private" and message.from_user and message.from_user.id==support_admin_telegram_id)

@router.message(Command("tickets", "ticket", "ticket_status"))
async def commands(message: Message, command: CommandObject):
    if not is_admin(message): return
    args=(command.args or "").split(maxsplit=2)
    try:
        if command.command=="tickets":
            r=await backend_get("/internal/support/tickets");r.raise_for_status()
            lines=[f"{x['id']} · {STATUS[x['status']]} · {x['category']}" for x in r.json()]
            await message.answer("Открытые обращения (до 20):\n"+"\n".join(lines) if lines else "Открытых обращений нет.");return
        if not args: await message.answer("/ticket НОМЕР\n/ticket_status НОМЕР in_progress|resolved|closed Ответ пользователю");return
        if command.command=="ticket_status":
            if len(args)<2 or args[1] not in STATUS: await message.answer("Статус: new, in_progress, resolved или closed");return
            payload={"status":args[1]}
            if len(args)>2: payload["response"]=args[2]
            r=await backend_post(f"/internal/support/tickets/{args[0]}", payload)
        else:r=await backend_get(f"/internal/support/tickets/{args[0]}")
        r.raise_for_status();x=r.json()
        diagnostics=x.get("diagnostics",{})
        device=diagnostics.get("device",{})
        text=(f"Обращение {x['id']}\n{STATUS[x['status']]} · {x['category']} · {x['tier']} · {x['network']}\n"
              f"Telegram ID: {x.get('telegram_id','—')}\nПлатформа: {diagnostics.get('platform','unknown')}\n"
              f"Устройство: {device.get('name','Не выбрано')} · {device.get('id','—')}\n\n{x['description']}")
        await message.answer(text[:4000])
        if x.get("response"): await message.answer("Последний ответ поддержки:\n"+x["response"])
    except Exception:
        await message.answer("Не удалось обработать обращение. Проверь номер и попробуй снова.")

async def deliver_notifications(bot):
    if not support_admin_telegram_id: return
    while True:
        try:
            r=await backend_get("/internal/support/notifications");r.raise_for_status()
            for x in r.json():
                try:
                    if x['kind']=="admin":
                        chat=support_admin_telegram_id
                        text=(f"🛟 Новое обращение Work&PlayVPN\nНомер: {x['id']}\nПользователь: {x['telegram_id']}\nТема: {x['category']} · {x['tier']} · {x['network']}\n\n{x['description']}\n\n/ticket {x['id']}\n/ticket_status {x['id']} in_progress")
                    else:
                        chat=x['telegram_id']
                        text=f"🛟 Обращение {x['id']}\nСтатус: {STATUS[x['status']]}\n\n{x.get('response') or 'Статус обращения обновлён.'}\n\nИстория доступна в Mini App → Помощь."
                    await bot.send_message(chat,text[:4000])
                    ack=await backend_post(f"/internal/support/notifications/{x['id']}/ack", {"kind":x['kind'],"revision":x['revision']});ack.raise_for_status()
                except TelegramForbiddenError:
                    if x["kind"] == "user":
                        # Blocked bots cannot deliver; the answer remains in Mini App.
                        await backend_post(f"/internal/support/notifications/{x['id']}/ack", {"kind":"user","revision":x["revision"]})
                    else: logging.warning("Support recipient cannot receive messages; check SUPPORT_ADMIN_TELEGRAM_ID")
                except TelegramRetryAfter as exc:
                    await asyncio.sleep(min(exc.retry_after, 60))
                    break
                except Exception: logging.warning("Support notification delivery failed; retained for retry")
        except Exception: logging.warning("Support notification queue unavailable; will retry")
        await asyncio.sleep(30)
