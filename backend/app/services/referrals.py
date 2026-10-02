"""Transactional referral rewards; all callers commit with their business operation."""
import secrets
from uuid import uuid4
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.user import User
from app.models.payment import Payment
from app.models.plan import Plan
# Load referenced tables for the standalone operator CLI as well as FastAPI.
from app.models.subscription import Subscription  # noqa: F401
from app.models.location import Location  # noqa: F401
from app.models.referral import ReferralAccount, ReferralInvite, ReferralCommission, ReferralWithdrawal

RATE = 15
MINIMUM = 50000
OPEN = ("requested", "processing")

def kopecks(amount):
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def commission_amount(gross):
    return (gross * RATE + 50) // 100

def account(db: Session, user_id: int, *, lock=False):
    # Unique user_id makes concurrent first reads converge on one permanent code.
    if db.bind.dialect.name == "postgresql":
        db.execute(insert(ReferralAccount).values(user_id=user_id, code=secrets.token_hex(12), balance_kopecks=0).on_conflict_do_nothing(index_elements=[ReferralAccount.user_id]))
    elif db.get(ReferralAccount, user_id) is None:
        db.add(ReferralAccount(user_id=user_id, code=secrets.token_hex(12), balance_kopecks=0)); db.flush()
    q=select(ReferralAccount).where(ReferralAccount.user_id==user_id)
    if lock: q=q.with_for_update().execution_options(populate_existing=True)
    return db.scalar(q)

def bind_new_user(db, user, code):
    # Called ONLY inside first user creation, never from a later /start or arbitrary query string.
    if not code: return
    inviter=db.scalar(select(ReferralAccount).join(User, User.id==ReferralAccount.user_id).where(ReferralAccount.code==code, User.is_active.is_(True)))
    if inviter and inviter.user_id != user.id:
        db.add(ReferralInvite(user_id=user.id, referrer_id=inviter.user_id))

def credit_payment(db, payment, plan):
    if (settings.payment_mode != "live" or payment.provider == "test"
        or (payment.provider == "robokassa" and settings.robokassa_is_test)
        or payment.currency != "RUB" or not plan or plan.access_tier not in ("basic", "mobile")
        or payment.status != "succeeded" or payment.amount <= 0): return
    invitation=db.get(ReferralInvite, payment.user_id)
    if not invitation: return
    wallet=account(db, invitation.referrer_id, lock=True)
    # Wallet lock serializes different payments as well as retries.
    if db.get(ReferralCommission, payment.id): return
    gross=kopecks(payment.amount); reward=commission_amount(gross)
    if reward <= 0: return
    db.add(ReferralCommission(payment_id=payment.id, referrer_id=invitation.referrer_id,
        gross_kopecks=gross, amount_kopecks=reward, refunded_kopecks=0, reversed_kopecks=0))
    wallet.balance_kopecks += reward
    db.flush()

def reserved(db, user_id):
    return int(db.scalar(select(func.coalesce(func.sum(ReferralWithdrawal.amount_kopecks),0)).where(ReferralWithdrawal.user_id==user_id, ReferralWithdrawal.status.in_(OPEN))) or 0)

def request_withdrawal(db, user_id, amount, key):
    wallet=account(db,user_id,lock=True)
    previous=db.scalar(select(ReferralWithdrawal).where(ReferralWithdrawal.user_id==user_id, ReferralWithdrawal.idempotency_key==key))
    if previous:
        if previous.amount_kopecks != amount: raise HTTPException(409,"Withdrawal key already used")
        return previous
    if amount < MINIMUM: raise HTTPException(422,"Withdrawal minimum is 500 RUB")
    if reserved(db,user_id): raise HTTPException(409,"Withdrawal already pending")
    if amount > wallet.balance_kopecks: raise HTTPException(409,"Insufficient referral balance")
    item=ReferralWithdrawal(id=str(uuid4()),user_id=user_id,amount_kopecks=amount,idempotency_key=key,status="requested")
    db.add(item); db.flush(); return item

def cancel_withdrawal(db,user_id,withdrawal_id):
    account(db,user_id,lock=True)
    item=db.scalar(select(ReferralWithdrawal).where(ReferralWithdrawal.id==withdrawal_id,ReferralWithdrawal.user_id==user_id).with_for_update().execution_options(populate_existing=True))
    if not item: raise HTTPException(404,"Withdrawal not found")
    if item.status == "canceled": return item
    if item.status != "requested": raise HTTPException(409,"Withdrawal cannot be canceled")
    item.status="canceled";db.flush();return item

def process_withdrawal(db,withdrawal_id,action,reference=None,note=None):
    item=db.get(ReferralWithdrawal,withdrawal_id)
    if not item: raise HTTPException(404,"Withdrawal not found")
    wallet=account(db,item.user_id,lock=True)
    item=db.scalar(select(ReferralWithdrawal).where(ReferralWithdrawal.id==withdrawal_id).with_for_update().execution_options(populate_existing=True))
    if action not in ("processing","paid","rejected"): raise HTTPException(422,"Invalid withdrawal action")
    if item.status==action:
        if action=="paid" and item.transfer_reference != reference: raise HTTPException(409,"Transfer reference mismatch")
        return item
    if item.status not in OPEN: raise HTTPException(409,"Withdrawal is closed")
    if action in ("processing","paid") and reserved(db,item.user_id)>wallet.balance_kopecks:
        raise HTTPException(409,"Balance changed after refund; reject the request")
    if action=="paid":
        if item.status!="processing": raise HTTPException(409,"Start processing before confirming payment")
        if not reference or len(reference)>200: raise HTTPException(422,"Bank transfer reference required")
        wallet.balance_kopecks -= item.amount_kopecks
        item.transfer_reference=reference
    item.status=action;item.note=note;db.flush();return item

def reverse_refund(db,payment_id,total_refunded):
    # Cumulative confirmed refund amount, not a delta: retry cannot debit twice.
    payment=db.scalar(select(Payment).where(Payment.id==payment_id).with_for_update())
    if not payment or payment.status!="succeeded": raise HTTPException(409,"Succeeded payment required")
    reward=db.get(ReferralCommission,payment_id)
    if not reward: return None
    wallet=account(db,reward.referrer_id,lock=True)
    db.refresh(reward)
    if total_refunded < reward.refunded_kopecks or total_refunded > reward.gross_kopecks:
        raise HTTPException(422,"Invalid cumulative refund amount")
    remaining=commission_amount(reward.gross_kopecks-total_refunded)
    new_reversal=reward.amount_kopecks-remaining
    wallet.balance_kopecks -= new_reversal-reward.reversed_kopecks
    reward.refunded_kopecks=total_refunded;reward.reversed_kopecks=new_reversal
    db.flush();return reward

def summary(db,user_id):
    wallet=account(db,user_id,lock=True); held=reserved(db,user_id)
    rewards=db.scalars(select(ReferralCommission).where(ReferralCommission.referrer_id==user_id).order_by(ReferralCommission.created_at.desc(),ReferralCommission.payment_id.desc()).limit(100)).all()
    withdrawals=db.scalars(select(ReferralWithdrawal).where(ReferralWithdrawal.user_id==user_id).order_by(ReferralWithdrawal.created_at.desc(),ReferralWithdrawal.id.desc()).limit(100)).all()
    invited=db.scalar(select(func.count()).select_from(ReferralInvite).where(ReferralInvite.referrer_id==user_id)) or 0
    paying=db.scalar(select(func.count(func.distinct(Payment.user_id))).join(ReferralCommission,ReferralCommission.payment_id==Payment.id).where(ReferralCommission.referrer_id==user_id,ReferralCommission.amount_kopecks>ReferralCommission.reversed_kopecks)) or 0
    return dict(code=wallet.code,link=f"https://t.me/workplayvpn_bot?start=ref_{wallet.code}",rate_percent=RATE,
        live_payments=settings.payment_mode=="live",minimum_kopecks=MINIMUM,balance_kopecks=wallet.balance_kopecks,reserved_kopecks=held,
        available_kopecks=max(0,wallet.balance_kopecks-held),invited_count=invited,paying_count=paying,
        commissions=[dict(payment_id=x.payment_id,amount_kopecks=x.amount_kopecks,reversed_kopecks=x.reversed_kopecks,created_at=x.created_at) for x in rewards],
        withdrawals=[dict(id=x.id,amount_kopecks=x.amount_kopecks,status=x.status,note=x.note,created_at=x.created_at) for x in withdrawals])
