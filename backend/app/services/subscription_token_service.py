import base64
import hashlib
import hmac
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.subscription_token import SubscriptionToken
from app.models.user import User


class SubscriptionTokenService:

    def _sign(
        self,
        user_id: int,
        version: int,
        access_tier: str = "basic",
    ) -> str:
        message = (
            f"{user_id}:{version}" if access_tier == "basic"
            else f"{user_id}:{version}:{access_tier}"
        ).encode("utf-8")

        digest = hmac.new(
            settings.subscription_token_secret.encode("utf-8"),
            message,
            hashlib.sha256,
        ).digest()

        return (
            base64.urlsafe_b64encode(digest)
            .decode("ascii")
            .rstrip("=")
        )

    def _build_raw_token(
        self,
        user_id: int,
        version: int,
        access_tier: str = "basic",
    ) -> str:
        if access_tier not in {"basic", "mobile"}:
            raise ValueError("Invalid access tier")
        signature = self._sign(
            user_id=user_id,
            version=version,
            access_tier=access_tier,
        )

        if access_tier == "mobile":
            return f"{user_id}.{version}.mobile.{signature}"
        # Keep every existing three-part link valid for Basic.
        return f"{user_id}.{version}.{signature}"

    def scoped_token(self, token: SubscriptionToken, access_tier: str) -> str:
        return self._build_raw_token(token.user_id, token.version, access_tier)

    def get_or_create_token(
        self,
        database: Session,
        telegram_id: int,
    ) -> tuple[SubscriptionToken, str]:
        user = database.scalar(
            select(User)
            .where(
                User.telegram_id == telegram_id,
                User.is_active.is_(True),
            )
            .with_for_update()
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        token = database.scalar(
            select(SubscriptionToken).where(
                SubscriptionToken.user_id == user.id,
            )
        )

        if token is None:
            token = SubscriptionToken(
                user_id=user.id,
                version=1,
            )

            database.add(token)
            database.commit()
            database.refresh(token)

        raw_token = self._build_raw_token(
            user_id=user.id,
            version=token.version,
        )

        return token, raw_token

    def rotate_token(
        self,
        database: Session,
        telegram_id: int,
    ) -> tuple[SubscriptionToken, str]:
        user = database.scalar(
            select(User)
            .where(
                User.telegram_id == telegram_id,
                User.is_active.is_(True),
            )
            .with_for_update()
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        token = database.scalar(
            select(SubscriptionToken)
            .where(
                SubscriptionToken.user_id == user.id,
            )
            .with_for_update()
        )

        if token is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription token not found",
            )

        token.version += 1
        token.rotated_at = datetime.now(UTC)

        database.commit()
        database.refresh(token)

        raw_token = self._build_raw_token(
            user_id=user.id,
            version=token.version,
        )

        return token, raw_token

    def resolve_token_scope(
        self,
        database: Session,
        raw_token: str,
    ) -> tuple[User, str]:
        parts = raw_token.split(".")
        if len(parts) == 3:
            user_id_raw, version_raw, provided_signature = parts
            access_tier = "basic"
        elif len(parts) == 4 and parts[2] == "mobile":
            user_id_raw, version_raw, _, provided_signature = parts
            access_tier = "mobile"
        else:
            raise HTTPException(status_code=404, detail="Subscription token not found")
        try:
            user_id = int(user_id_raw)
            version = int(version_raw)
        except ValueError as exc:
            raise HTTPException(
                status_code=404, detail="Subscription token not found",
            ) from exc
        token = database.scalar(select(SubscriptionToken).where(
            SubscriptionToken.user_id == user_id,
        ))
        if token is None or token.version != version:
            raise HTTPException(status_code=404, detail="Subscription token not found")
        expected = self._sign(user_id, version, access_tier)
        if not hmac.compare_digest(expected, provided_signature):
            raise HTTPException(status_code=404, detail="Subscription token not found")
        user = database.get(User, user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=404, detail="User not found")
        return user, access_tier

    def resolve_token(self, database: Session, raw_token: str) -> User:
        user, _ = self.resolve_token_scope(database, raw_token)
        return user


subscription_token_service = SubscriptionTokenService()
