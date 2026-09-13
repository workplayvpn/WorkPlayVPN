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

    expires_at = subscription.expires_at

    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at <= now:
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

    html = f"""
<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Подключение Work&PlayVPN</title>

    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            min-height: 100vh;
            margin: 0;
            padding: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
            background:
                linear-gradient(
                    160deg,
                    #111827 0%,
                    #1e1b4b 100%
                );
            color: #f8fafc;
        }}

        .card {{
            width: 100%;
            max-width: 460px;
            padding: 32px 24px;
            text-align: center;
            background: rgba(15, 23, 42, 0.92);
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 24px;
            box-shadow:
                0 24px 60px rgba(0, 0, 0, 0.35);
        }}

        .logo {{
            width: 64px;
            height: 64px;
            margin: 0 auto 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 20px;
            background:
                linear-gradient(
                    135deg,
                    #6366f1,
                    #8b5cf6
                );
            font-size: 32px;
        }}

        h1 {{
            margin: 0 0 12px;
            font-size: 28px;
        }}

        .status {{
            margin: 0 0 24px;
            color: #cbd5e1;
            line-height: 1.5;
        }}

        .button {{
            display: block;
            width: 100%;
            padding: 16px 20px;
            margin: 0;
            border-radius: 14px;
            text-decoration: none;
            font-size: 18px;
            font-weight: 700;
            background:
                linear-gradient(
                    135deg,
                    #6366f1,
                    #8b5cf6
                );
            color: #fff;
        }}

        .hint {{
            margin: 20px 0 0;
            color: #94a3b8;
            line-height: 1.5;
            font-size: 14px;
        }}
    </style>

    <script>
        window.addEventListener("load", function () {{
            window.setTimeout(function () {{
                const happLink = document.getElementById(
                    "happ-link"
                );

                window.location.replace(happLink.href);
            }}, 150);
        }});
    </script>
</head>

<body>
    <main class="card">
        <div class="logo">🛡️</div>

        <h1>Work&PlayVPN</h1>

        <p class="status">
            Подписка готова. Открываем приложение HAPP…
        </p>

        <a
            id="happ-link"
            class="button"
            href="{safe_happ_url}"
        >
            🚀 Открыть HAPP
        </a>

        <p class="hint">
            Если приложение не открылось автоматически,
            нажмите кнопку «Открыть HAPP».
        </p>
    </main>
</body>
</html>
"""

    return HTMLResponse(
        content=html,
        status_code=status.HTTP_200_OK,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": (
                "noindex, nofollow, noarchive"
            ),
        },
    )