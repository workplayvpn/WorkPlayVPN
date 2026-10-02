from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.telegram_webapp_auth import require_telegram_webapp_auth
from app.db.dependencies import get_db
from app.models.user import User
from app.services.telegram_webapp_auth import TelegramWebAppAuthResult
from app.services import referrals

router=APIRouter(prefix="/mini-app/referrals",tags=["referrals"])
Auth=Annotated[TelegramWebAppAuthResult,Depends(require_telegram_webapp_auth)]
Db=Annotated[Session,Depends(get_db)]

def current_user(db,auth):
    user=db.scalar(select(User).where(User.telegram_id==auth.user.id,User.is_active.is_(True)))
    if not user: raise HTTPException(404,"User not found")
    return user

class WithdrawalCreate(BaseModel):
    amount_kopecks: int = Field(ge=50000,le=1000000000,strict=True)
    idempotency_key: str = Field(min_length=16,max_length=64,pattern=r"^[a-zA-Z0-9_-]+$")

@router.get("")
def get_referrals(auth:Auth,db:Db):
    result=referrals.summary(db,current_user(db,auth).id);db.commit();return result

@router.post("/withdrawals",status_code=201)
def request_withdrawal(payload:WithdrawalCreate,auth:Auth,db:Db):
    user=current_user(db,auth)
    item=referrals.request_withdrawal(db,user.id,payload.amount_kopecks,payload.idempotency_key)
    db.commit();return {"id":item.id,"status":item.status}

@router.post("/withdrawals/{withdrawal_id}/cancel")
def cancel_withdrawal(withdrawal_id:str,auth:Auth,db:Db):
    item=referrals.cancel_withdrawal(db,current_user(db,auth).id,withdrawal_id)
    db.commit();return {"id":item.id,"status":item.status}
