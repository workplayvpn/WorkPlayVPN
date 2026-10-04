"""Keep the crypt5 string identical across bot, Mini App, QR and restarts."""
import hashlib
from collections.abc import Callable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.happ_import_link import HappImportLink
from app.models.user import User
from app.services.happ_crypt_link import CRYPT5_PATTERN, encrypted_happ_link


def stable_happ_import_link(database: Session, *, user_id: int, access_tier: str,
                            subscription_url: str,
                            encrypt: Callable[[str], str] = encrypted_happ_link) -> str:
    if access_tier not in {"basic", "mobile"}:
        raise ValueError("Unknown subscription tier")
    digest = hashlib.sha256(subscription_url.encode("utf-8")).hexdigest()
    # Serialize the first generation and source changes across all backend
    # processes using the same account lock as token rotation/registration.
    owner = database.scalar(select(User.id).where(
        User.id == user_id, User.is_active.is_(True)).with_for_update())
    if owner is None:
        raise HTTPException(404, "User not found")
    saved = database.scalar(select(HappImportLink).where(
        HappImportLink.user_id == user_id,
        HappImportLink.access_tier == access_tier,
    ).execution_options(populate_existing=True))
    if (saved is not None and saved.source_digest == digest
            and CRYPT5_PATTERN.fullmatch(saved.encrypted_url)):
        return saved.encrypted_url
    url = encrypt(subscription_url)
    if not isinstance(url, str) or not CRYPT5_PATTERN.fullmatch(url):
        raise ValueError("Unexpected Happ crypto response")
    if saved is None:
        saved = HappImportLink(user_id=user_id, access_tier=access_tier,
                               source_digest=digest, encrypted_url=url)
        database.add(saved)
    else:
        saved.source_digest = digest
        saved.encrypted_url = url
    database.commit()
    return url
