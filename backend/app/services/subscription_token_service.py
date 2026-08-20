import hashlib
import secrets
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription_token import SubscriptionToken
from app.models.user import User


class SubscriptionTokenService:
    def get_or_create_token(
        self,
        database: Session,
        telegram_id: int,
    ) -> tuple[SubscriptionToken, str]:
        user = database.scalar(
            select(User).where(
                User.telegram_id == telegram_id,
                User.is_active.is_(True),
            )
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        existing = database.scalar(
            select(SubscriptionToken).where(
                SubscriptionToken.user_id == user.id
            )
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Subscription token already exists",
            )

        raw_token = secrets.token_urlsafe(32)

        token_hash = hashlib.sha256(
            raw_token.encode("utf-8")
        ).hexdigest()

        token = SubscriptionToken(
            user_id=user.id,
            token_hash=token_hash,
        )

        database.add(token)
        database.commit()
        database.refresh(token)

        return token, raw_token

    def rotate_token(
        self,
        database: Session,
        telegram_id: int,
    ) -> tuple[SubscriptionToken, str]:
        user = database.scalar(
            select(User).where(
                User.telegram_id == telegram_id,
                User.is_active.is_(True),
            )
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        token = database.scalar(
            select(SubscriptionToken).where(
                SubscriptionToken.user_id == user.id
            )
        )

        if token is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription token not found",
            )

        raw_token = secrets.token_urlsafe(32)

        token.token_hash = hashlib.sha256(
            raw_token.encode("utf-8")
        ).hexdigest()

        token.rotated_at = datetime.now(UTC)

        database.commit()
        database.refresh(token)

        return token, raw_token

    def resolve_token(
        self,
        database: Session,
        raw_token: str,
    ) -> User:
        token_hash = hashlib.sha256(
            raw_token.encode("utf-8")
        ).hexdigest()

        token = database.scalar(
            select(SubscriptionToken).where(
                SubscriptionToken.token_hash == token_hash
            )
        )

        if token is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription token not found",
            )

        user = database.get(
            User,
            token.user_id,
        )

        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return user


subscription_token_service = SubscriptionTokenService()