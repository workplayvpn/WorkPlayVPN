import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.internal_auth import require_internal_api_secret
from app.api.telegram_webapp_auth import require_telegram_webapp_auth
from app.db.dependencies import get_db
from app.models.user import User
from app.services import help_access
from app.services.telegram_webapp_auth import TelegramWebAppAuthResult

router = APIRouter(tags=["help-access"])
Db = Annotated[Session, Depends(get_db)]
Auth = Annotated[TelegramWebAppAuthResult, Depends(require_telegram_webapp_auth)]
ARTICLES = json.loads((Path(__file__).parents[1] / "data" / "knowledge.json").read_text(encoding="utf-8"))


class Login(BaseModel):
    key: str = Field(min_length=1, max_length=120)


def _no_cache(response: Response):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Vary"] = "Cookie, X-Help-Session, X-Telegram-Init-Data"


def _origin(request: Request):
    # Only same-origin browser writes. Caddy preserves the public Host.
    origin = request.headers.get("origin")
    if origin and origin != f"https://{request.headers.get('host', '')}":
        raise HTTPException(403, "Запрос с другого сайта запрещён")


def require_help_user(request: Request, db: Db) -> User:
    return help_access.resolve_session(db, request.cookies.get(help_access.COOKIE))


def require_mini_help_access(request: Request, auth: Auth, db: Db):
    # Telegram Web may block cookies in its embedded Mini App.
    session_header = request.headers.get("X-Help-Session")
    owner = help_access.resolve_session(db, session_header, mini=True) if session_header else help_access.resolve_session(db, request.cookies.get(help_access.COOKIE))
    if owner.telegram_id != auth.user.id:
        raise HTTPException(403, "HELP_KEY_REQUIRED")
    return owner


def _telegram_user(db, auth):
    user = db.scalar(select(User).where(User.telegram_id == auth.user.id, User.is_active.is_(True)))
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    return user


@router.post("/help-access/login")
def login(payload: Login, request: Request, response: Response, db: Db):
    _origin(request)
    help_access.check_attempts(request.client.host if request.client else "unknown")
    user, token = help_access.resolve_key(db, payload.key)
    response.set_cookie(help_access.COOKIE, help_access.session_for(user, token), max_age=help_access.SESSION_SECONDS, secure=True, httponly=True, samesite="strict", path="/")
    _no_cache(response)
    return {"ok": True}


@router.post("/mini-app/support/login")
def mini_login(payload: Login, request: Request, response: Response, auth: Auth, db: Db):
    _origin(request)
    help_access.check_attempts(request.client.host if request.client else "unknown")
    user, token = help_access.resolve_key(db, payload.key)
    if user.telegram_id != auth.user.id:
        raise HTTPException(403, "Используй ключ помощи своего Telegram-аккаунта")
    response.set_cookie(help_access.COOKIE, help_access.session_for(user, token), max_age=help_access.SESSION_SECONDS, secure=True, httponly=True, samesite="strict", path="/")
    _no_cache(response)
    return {"ok": True, "session": help_access.session_for(user, token, mini=True)}


@router.post("/help-access/logout")
def logout(request: Request, response: Response):
    _origin(request)
    response.delete_cookie(help_access.COOKIE, secure=True, httponly=True, samesite="strict", path="/")
    _no_cache(response)
    return {"ok": True}


@router.get("/help-access/session")
def session(response: Response, owner: Annotated[User, Depends(require_help_user)]):
    _no_cache(response)
    return {"ok": True}


@router.get("/help-access/knowledge")
def public_knowledge(response: Response, owner: Annotated[User, Depends(require_help_user)]):
    _no_cache(response)
    # Public website describes Basic; Pro stays inside the authenticated Mini App.
    public = [dict(a, paragraphs=list(a["paragraphs"])) for a in ARTICLES if a["id"] != "tiers"]
    for a in public:
        if a["id"] == "keys":
            a["paragraphs"][1] = a["paragraphs"][1].replace("выбранной подписки", "Basic")
    return public


@router.get("/mini-app/support/access-key")
def access_key(response: Response, auth: Auth, db: Db):
    _no_cache(response)
    return {"key": help_access.issue_key(db, _telegram_user(db, auth))}


@router.get("/mini-app/support/session")
def mini_session(response: Response, owner: Annotated[User, Depends(require_mini_help_access)]):
    _no_cache(response)
    return {"ok": True}


@router.get("/mini-app/support/knowledge")
def mini_knowledge(response: Response, owner: Annotated[User, Depends(require_mini_help_access)]):
    _no_cache(response)
    return ARTICLES


@router.get("/internal/support/access-key/{telegram_id}", dependencies=[Depends(require_internal_api_secret)])
def internal_key(telegram_id: int, response: Response, db: Db):
    user = db.scalar(select(User).where(User.telegram_id == telegram_id, User.is_active.is_(True)))
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    _no_cache(response)
    return {"key": help_access.issue_key(db, user)}
