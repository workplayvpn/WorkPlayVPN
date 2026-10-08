from app.services.payment_order_number import public_order_number
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.telegram_webapp_auth import require_telegram_webapp_auth
from app.core.config import settings
from app.db.dependencies import get_db
from app.models.gift import GiftCertificate
from app.models.payment import Payment
from app.models.user import User
from app.services.catalog import available_plans
from app.services.gifts import display_code, raw_code, preview_gift, redeem_gift
from app.services.gifts import utc
from datetime import UTC, datetime
from app.services.payment_service import payment_service
from app.services.payment_redirect_service import payment_redirect_service
from app.services.gift_checkout import gift_checkout_is_current

router = APIRouter(prefix="/mini-app/gifts", tags=["gifts"], dependencies=[Depends(require_telegram_webapp_auth)])


class BuyGift(BaseModel):
    plan_code: str = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=8, max_length=180)


class RedeemGift(BaseModel):
    code: str = Field(min_length=1, max_length=128)


def owner(database, auth):
    user = database.scalar(select(User).where(User.telegram_id == auth.user.id, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(404, "User not found")
    return user


@router.get("/catalog")
def catalog(auth=Depends(require_telegram_webapp_auth), database: Session = Depends(get_db)):
    user = owner(database, auth)
    return [dict(code=p.code, name=p.name, access_tier=p.access_tier, duration_days=p.duration_days,
                 device_limit=p.device_limit, amount=str(p.price_amount), currency=p.currency)
            for p in available_plans(database, user.telegram_id) if p.price_amount > 0]


@router.post("/payments", status_code=201)
def buy(payload: BuyGift, response: Response, auth=Depends(require_telegram_webapp_auth), database: Session = Depends(get_db)):
    user = owner(database, auth)
    payment = payment_service.create_payment(database, user.telegram_id, payload.plan_code,
        settings.payment_default_provider, payload.idempotency_key, purchase_kind="gift")
    response.headers["Cache-Control"] = "no-store"
    return dict(id=payment.id, order_number=public_order_number(payment), status=payment.status, amount=str(payment.amount), currency=payment.currency,
                confirmation_url=payment_redirect_service.build_public_confirmation_url(payment), expires_at=payment.expires_at)


@router.get("")
def mine(response: Response, auth=Depends(require_telegram_webapp_auth), database: Session = Depends(get_db), offset: int = Query(default=0, ge=0)):
    user = owner(database, auth)
    response.headers["Cache-Control"] = "no-store"
    offset = offset if isinstance(offset, int) else 0
    rows = list(database.scalars(select(GiftCertificate).where(
        (GiftCertificate.buyer_id == user.id) | (GiftCertificate.recipient_id == user.id))
        .order_by(GiftCertificate.created_at.desc(), GiftCertificate.id).offset(offset).limit(101)).all())
    next_offset = offset + 100 if len(rows) > 100 else None
    rows = rows[:100]
    purchased, activated = [], []
    for gift in rows:
        payment = database.get(Payment, gift.payment_id)
        data = dict(id=gift.id, payment_id=gift.payment_id, order_number=public_order_number(payment), access_tier=gift.access_tier,
                    duration_days=gift.duration_days, state=gift.state, redeemed_at=gift.redeemed_at,
                    created_at=gift.created_at, is_test=payment.is_gift_test)
        if gift.buyer_id == user.id:
            data.update(amount=str(payment.amount), currency=payment.currency)
            if gift.state == "pending":
                data["state"] = payment.status
                if payment.status == "pending" and payment.expires_at and utc(payment.expires_at) <= datetime.now(UTC):
                    data["state"] = "expired"
                if data["state"] == "pending" and not gift_checkout_is_current(payment):
                    data["state"] = "obsolete"
                data["confirmation_url"] = payment_redirect_service.build_public_confirmation_url(payment) if data["state"] == "pending" else None
            if gift.state == "ready" and payment.status == "succeeded":
                data["code"] = display_code(gift)
                data["share_url"] = "https://t.me/workplayvpn_bot?start=gift_" + raw_code(gift)
            purchased.append(data)
        elif gift.recipient_id == user.id:
            activated.append(data)
    return dict(purchased=purchased, activated=activated, next_offset=next_offset)


@router.post("/preview")
def preview(payload: RedeemGift, response: Response, auth=Depends(require_telegram_webapp_auth), database: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return preview_gift(database, owner(database, auth).id, payload.code)


@router.post("/redeem")
def redeem(payload: RedeemGift, response: Response, auth=Depends(require_telegram_webapp_auth), database: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return redeem_gift(database, owner(database, auth).id, payload.code)
