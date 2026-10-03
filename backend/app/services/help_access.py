"""A help-only key and short-lived session, independent of VPN credentials."""
import hashlib
import hmac
import re
import secrets
import time
from collections import OrderedDict
from threading import Lock

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.subscription_token import SubscriptionToken
from app.models.user import User
from app.services.subscription_token_service import subscription_token_service

COOKIE = "__Host-workplay-help"
SESSION_SECONDS = 3600
KEY_PATTERN = re.compile(r"^tg-([1-9][0-9]{0,18})-([a-f0-9]{32})$")


def _sign(message: str) -> str:
    return hmac.new(settings.subscription_token_secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def key_for(user: User, token: SubscriptionToken) -> str:
    signature = _sign(f"help-key:v1:{user.id}:{user.telegram_id}:{token.version}")[:32]
    return f"tg-{user.telegram_id}-{signature}"


def issue_key(db: Session, user: User) -> str:
    token, _ = subscription_token_service.get_or_create_token(db, user.telegram_id)
    return key_for(user, token)


def resolve_key(db: Session, key: str) -> tuple[User, SubscriptionToken]:
    match = KEY_PATTERN.fullmatch(key.strip().lower())
    if match and int(match[1]) <= 9223372036854775807:
        user = db.scalar(select(User).where(User.telegram_id == int(match[1]), User.is_active.is_(True)))
        if user:
            token = db.scalar(select(SubscriptionToken).where(SubscriptionToken.user_id == user.id))
            if token and hmac.compare_digest(key_for(user, token), key.strip().lower()):
                return user, token
    raise HTTPException(401, "Ключ не найден. Скопируй ключ помощи в боте → «Помощь».")


def session_for(user: User, token: SubscriptionToken, *, mini: bool = False) -> str:
    # Domain-separated signature; no VPN token or help key in the cookie.
    body = f"{user.id}.{token.version}.{int(time.time()) + SESSION_SECONDS}.{secrets.token_hex(8)}"
    purpose = 'mini-help-session:v1:' if mini else 'help-session:v1:'
    return f"{body}.{_sign(purpose + body)}"


def resolve_session(db: Session, value: str | None, *, mini: bool = False) -> User:
    denied = HTTPException(403, "HELP_KEY_REQUIRED")
    if not value or len(value) > 220:
        raise denied
    parts = value.split('.')
    if len(parts) != 5:
        raise denied
    uid, version, expiry, nonce, signature = parts
    if not all(x.isdecimal() for x in (uid, version, expiry)) or not re.fullmatch(r"[a-f0-9]{16}", nonce):
        raise denied
    purpose = 'mini-help-session:v1:' if mini else 'help-session:v1:'
    expected = _sign(purpose + '.'.join(parts[:-1]))
    if not hmac.compare_digest(expected, signature) or not int(time.time()) < int(expiry) <= int(time.time()) + SESSION_SECONDS:
        raise denied
    user = db.get(User, int(uid))
    token = db.scalar(select(SubscriptionToken).where(SubscriptionToken.user_id == int(uid)))
    if not user or not user.is_active or not token or token.version != int(version):
        raise denied
    return user


# Bounded per-process throttle. The 128-bit key secret also makes guessing impractical.
_attempts: OrderedDict[str, tuple[float, int]] = OrderedDict()
_attempt_lock = Lock()


def check_attempts(client: str) -> None:
    now = time.monotonic()
    with _attempt_lock:
        start, count = _attempts.pop(client, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        _attempts[client] = (start, count + 1)
        while len(_attempts) > 4096:
            _attempts.popitem(last=False)
        if count >= 30:
            raise HTTPException(429, "Слишком много попыток. Попробуй через минуту.", headers={"Retry-After": "60"})
