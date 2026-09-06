import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.core.config import settings


_internal_bearer = HTTPBearer(auto_error=False)


def require_internal_api_secret(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_internal_bearer),
    ],
) -> None:
    credentials_are_valid = (
        credentials is not None
        and credentials.scheme.lower() == "bearer"
        and secrets.compare_digest(
            credentials.credentials,
            settings.internal_api_secret,
        )
    )

    if not credentials_are_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API credentials",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )