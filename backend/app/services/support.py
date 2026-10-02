from datetime import UTC, datetime, timedelta
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select, func
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.support_ticket import SupportTicket

OPEN = ("new", "in_progress")
UNSET = object()

def owned(db, user_id, ticket_id):
    row = db.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.user_id == user_id))
    if row is None: raise HTTPException(404, "Обращение не найдено")
    return row

def public(row):
    return dict(id=row.id, category=row.category, tier=row.tier, network=row.network,
                description=row.description, diagnostics=row.diagnostics, status=row.status,
                response=row.response, created_at=row.created_at, updated_at=row.updated_at)

def create(db, user, payload):
    # Per-account lock serializes rate limits and repeated concurrent submissions.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    old = db.scalar(select(SupportTicket).where(SupportTicket.user_id == user.id, SupportTicket.idempotency_key == payload.idempotency_key))
    if old:
        fingerprint = (payload.category, payload.tier, payload.network, payload.description)
        if (old.category, old.tier, old.network, old.description) != fingerprint:
            raise HTTPException(409, "Заявка с этим идентификатором уже существует")
        return old
    if db.scalar(select(func.count()).select_from(SupportTicket).where(SupportTicket.user_id == user.id, SupportTicket.status.in_(OPEN))) >= 5:
        raise HTTPException(429, "Уже есть 5 открытых обращений. Дождитесь ответа поддержки")
    if db.scalar(select(func.count()).select_from(SupportTicket).where(SupportTicket.user_id == user.id, SupportTicket.created_at >= datetime.now(UTC)-timedelta(minutes=10))) >= 3:
        raise HTTPException(429, "Слишком много обращений. Попробуйте через 10 минут")
    diagnostic = {"app_version": "20261003-2", "platform": payload.platform}
    if payload.device_id is not None:
        device = db.scalar(select(VpnDevice).where(VpnDevice.id == payload.device_id, VpnDevice.user_id == user.id, VpnDevice.is_active.is_(True)))
        if device is None: raise HTTPException(404, "Устройство не найдено")
        diagnostic["device"] = {"id": device.public_id, "name": device.device_name}
    row = SupportTicket(id=str(uuid4()), user_id=user.id, category=payload.category, tier=payload.tier,
                        network=payload.network, description=payload.description, diagnostics=diagnostic,
                        idempotency_key=payload.idempotency_key)
    db.add(row); db.flush(); return row

def update(db, ticket_id, status, response=UNSET):
    row = db.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id).with_for_update())
    if row is None: raise HTTPException(404, "Обращение не найдено")
    if response is UNSET: response = row.response
    if status != row.status or response != row.response:
        row.status = status; row.response = response; row.updated_at = datetime.now(UTC); row.revision += 1
    return row
