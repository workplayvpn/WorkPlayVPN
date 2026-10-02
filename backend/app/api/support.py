from typing import Annotated, Literal
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from app.api.telegram_webapp_auth import require_telegram_webapp_auth
from app.api.internal_auth import require_internal_api_secret
from app.db.dependencies import get_db
from app.services.telegram_webapp_auth import TelegramWebAppAuthResult
from app.models.user import User
from app.models.support_ticket import SupportTicket
from app.services import support
from app.api.help_access import require_mini_help_access

router = APIRouter(tags=["support"])
Auth = Annotated[TelegramWebAppAuthResult, Depends(require_telegram_webapp_auth)]
Db = Annotated[Session, Depends(get_db)]

class TicketCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["connection", "speed", "device", "payment", "referral", "other"]
    tier: Literal["basic", "mobile", "unknown"] = "unknown"
    network: Literal["wifi", "mobile", "both", "unknown"] = "unknown"
    description: str = Field(min_length=20, max_length=3000)
    device_id: int | None = Field(default=None, gt=0)
    platform: Literal["ios", "android", "windows", "macos", "linux", "other", "unknown"] = "unknown"
    idempotency_key: str = Field(min_length=16, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    @field_validator("description", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value

class TicketUpdate(BaseModel):
    status: Literal["new", "in_progress", "resolved", "closed"]
    response: str | None = Field(default=None, max_length=2000)

class NotificationAck(BaseModel):
    kind: Literal["admin", "user"]
    revision: int = Field(ge=0)

def user(db, auth):
    row = db.scalar(select(User).where(User.telegram_id == auth.user.id, User.is_active.is_(True)))
    if row is None: raise HTTPException(404, "Пользователь не найден")
    return row

@router.get("/mini-app/support/tickets", dependencies=[Depends(require_mini_help_access)])
def list_own(auth: Auth, db: Db):
    uid = user(db, auth).id
    return [support.public(x) for x in db.scalars(select(SupportTicket).where(SupportTicket.user_id == uid).order_by(SupportTicket.created_at.desc()).limit(50))]

@router.post("/mini-app/support/tickets", status_code=201, dependencies=[Depends(require_mini_help_access)])
def create_ticket(payload: TicketCreate, auth: Auth, db: Db):
    row = support.create(db, user(db, auth), payload); db.commit(); return support.public(row)

internal = [Depends(require_internal_api_secret)]

@router.get("/internal/support/tickets", dependencies=internal)
def admin_list(db: Db):
    return [dict(support.public(x), telegram_id=t) for x,t in db.execute(select(SupportTicket, User.telegram_id).join(User, User.id == SupportTicket.user_id).where(SupportTicket.status.in_(support.OPEN)).order_by(SupportTicket.created_at).limit(20))]

@router.get("/internal/support/tickets/{ticket_id}", dependencies=internal)
def admin_get(ticket_id: str, db: Db):
    row = db.get(SupportTicket, ticket_id)
    if row is None: raise HTTPException(404, "Обращение не найдено")
    return dict(support.public(row), telegram_id=db.get(User, row.user_id).telegram_id)

@router.post("/internal/support/tickets/{ticket_id}", dependencies=internal)
def admin_update(ticket_id: str, payload: TicketUpdate, db: Db):
    response = payload.response if "response" in payload.model_fields_set else support.UNSET
    row = support.update(db, ticket_id, payload.status, response); db.commit(); return support.public(row)

@router.get("/internal/support/notifications", dependencies=internal)
def notifications(db: Db):
    items=[]
    rows=db.execute(select(SupportTicket, User.telegram_id).join(User, User.id==SupportTicket.user_id).where(or_(SupportTicket.admin_notified_at.is_(None), SupportTicket.revision>SupportTicket.user_notified_revision)).order_by(SupportTicket.created_at).limit(10))
    for row, tid in rows:
        if row.admin_notified_at is None: items.append(dict(support.public(row), kind="admin", revision=row.revision, telegram_id=tid))
        if row.revision>row.user_notified_revision: items.append(dict(support.public(row), kind="user", revision=row.revision, telegram_id=tid))
    return items

@router.post("/internal/support/notifications/{ticket_id}/ack", dependencies=internal)
def ack(ticket_id: str, payload: NotificationAck, db: Db):
    row = db.scalar(select(SupportTicket).where(SupportTicket.id==ticket_id).with_for_update())
    if row is None: raise HTTPException(404, "Обращение не найдено")
    if payload.kind=="admin": row.admin_notified_at=datetime.now(UTC)
    else: row.user_notified_revision=max(row.user_notified_revision, min(payload.revision,row.revision))
    db.commit(); return {"ok": True}
