"""Real PostgreSQL locks, payment hook, endpoint ownership and registration."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select,delete
from fastapi import HTTPException
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.referral import ReferralInvite, ReferralCommission
from app.services import referrals as svc
from app.services.payment_service import payment_service
from app.api.users import create_user
from app.schemas.user import UserCreate
from app.api.referrals import current_user

@pytest.fixture
def referral_db(monkeypatch):
    monkeypatch.setattr(settings,'payment_mode','live')
    monkeypatch.setattr(settings,'robokassa_is_test',False)
    with SessionLocal() as db:
        db.execute(delete(User).where(User.telegram_id.between(990921001,990921009)));db.commit()
        inviter=User(telegram_id=990921001,is_active=True);friend=User(telegram_id=990921002,is_active=True)
        db.add_all([inviter,friend]);db.commit()
        svc.bind_new_user(db,friend,svc.account(db,inviter.id).code);db.commit()
        yield db,inviter,friend
        db.rollback();db.execute(delete(User).where(User.telegram_id.between(990921001,990921009)));db.commit()

def payable(db,friend):
    p=payment_service.create_payment(db,friend.telegram_id,'standard_1m','test','referral-'+str(uuid4()))
    p.provider='robokassa';db.commit();return p

def test_payment_hook_and_stale_replay(referral_db):
    db,inviter,friend=referral_db;p=payable(db,friend)
    with SessionLocal() as stale:
        stale.get(Payment,p.id)
        payment_service.mark_succeeded(db,p.id)
        payment_service.mark_succeeded(stale,p.id)
    db.expire_all()
    assert svc.account(db,inviter.id).balance_kopecks==2985
    assert db.get(ReferralCommission,p.id).amount_kopecks==2985

def test_payment_failure_rolls_back_reward(referral_db,monkeypatch):
    from app.services.subscription_service import subscription_service
    db,inviter,friend=referral_db;p=payable(db,friend)
    def fail(**kwargs):raise RuntimeError('activation failed before commit')
    monkeypatch.setattr(subscription_service,'activate_subscription',fail)
    with pytest.raises(RuntimeError):payment_service.mark_succeeded(db,p.id)
    assert db.get(Payment,p.id).status=='pending'
    assert db.get(ReferralCommission,p.id) is None
    assert svc.account(db,inviter.id).balance_kopecks==0

def test_concurrent_same_webhook_credits_once(referral_db):
    db,inviter,friend=referral_db;p=payable(db,friend);pid=p.id;db.commit();barrier=Barrier(2)
    def success(_):
        with SessionLocal() as other:
            barrier.wait(timeout=10);payment_service.mark_succeeded(other,pid)
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(success,range(2)))
    db.expire_all();assert svc.account(db,inviter.id).balance_kopecks==2985

def test_concurrent_withdrawals_cannot_reserve_twice(referral_db):
    db,inviter,friend=referral_db;wallet=svc.account(db,inviter.id);wallet.balance_kopecks=60000;uid=inviter.id;db.commit();barrier=Barrier(2)
    def request(i):
        with SessionLocal() as other:
            barrier.wait(timeout=10)
            try:
                svc.request_withdrawal(other,uid,50000,'race-request-key-'+str(i));other.commit();return 'created'
            except HTTPException as exc:other.rollback();return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(request,range(2)))
    assert sorted(map(str,results))==['409','created']
    assert svc.reserved(db,uid)==50000

def test_existing_user_cannot_be_reattributed(referral_db):
    db,inviter,friend=referral_db
    third=create_user(UserCreate(telegram_id=990921003,referral_code=svc.account(db,inviter.id).code),db)
    assert db.get(ReferralInvite,third.id).referrer_id==inviter.id
    with pytest.raises(HTTPException) as exc:create_user(UserCreate(telegram_id=friend.telegram_id,referral_code=svc.account(db,third.id).code),db)
    assert exc.value.status_code==409
    assert db.get(ReferralInvite,friend.id).referrer_id==inviter.id

def test_referrals_require_active_current_user(referral_db):
    db,inviter,friend=referral_db
    with pytest.raises(HTTPException):current_user(db,SimpleNamespace(user=SimpleNamespace(id=990921009)))
    friend.is_active=False;db.commit()
    with pytest.raises(HTTPException):current_user(db,SimpleNamespace(user=SimpleNamespace(id=friend.telegram_id)))
