from datetime import UTC, datetime
from html import escape

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.dependencies import get_db
from app.models.subscription import Subscription
from app.services.subscription_token_service import (
    subscription_token_service,
)


router = APIRouter(
    prefix="/connect/happ",
    tags=["connect-happ"],
)


@router.get(
    "/{token}",
    response_class=HTMLResponse,
)
def connect_happ(
    token: str,
    database: Session = Depends(get_db),
):
    user = subscription_token_service.resolve_token(
        database=database,
        raw_token=token,
    )

    subscription = database.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status == "active",
        )
        .order_by(
            Subscription.created_at.desc()
        )
    )

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required",
        )

    now = datetime.now(UTC)

    if (
        subscription.expires_at is not None
        and subscription.expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subscription expired",
        )

    subscription_url = (
        f"{settings.subscription_base_url.rstrip('/')}/"
        f"{token}"
    )

    happ_url = (
        "happ://add/"
        f"{subscription_url}"
    )

    safe_happ_url = escape(
        happ_url,
        quote=True,
    )

    safe_subscription_url = escape(
        subscription_url,
        quote=True,
    )

    html = f"""
<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Work&PlayVPN</title>

    <style>
        body {{
            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
            max-width: 520px;
            margin: 0 auto;
            padding: 32px 20px;
            text-align: center;
            background: #f7f7f8;
            color: #111;
        }}

        .card {{
            background: #fff;
            padding: 28px 20px;
            border-radius: 20px;
        }}

        h1 {{
            margin-top: 0;
        }}

        .button {{
            display: block;
            padding: 16px 20px;
            margin: 20px 0;
            border-radius: 14px;
            text-decoration: none;
            font-size: 18px;
            font-weight: 700;
            background: #111;
            color: #fff;
        }}

        .secondary {{
            background: #eee;
            color: #111;
        }}

        .hint {{
            color: #666;
            line-height: 1.5;
            font-size: 14px;
        }}
    </style>
</head>

<body>
    <div class="card">
        <h1>Work&PlayVPN</h1>

        <p>
            Подписка готова к подключению.
        </p>

        <a
            class="button"
            href="{safe_happ_url}"
        >
            🚀 Подключить в HAPP
        </a>

        <a
            class="button secondary"
            href="{safe_subscription_url}"
        >
            🔗 Открыть подписку
        </a>

        <p class="hint">
            Если HAPP установлен, приложение откроется
            и предложит добавить подписку автоматически.
        </p>
    </div>

    <script>
        setTimeout(function () {{
            window.location.href = "{safe_happ_url}";
        }}, 500);
    </script>
</body>
</html>
"""

    return HTMLResponse(
        content=html,
        status_code=200,
    )