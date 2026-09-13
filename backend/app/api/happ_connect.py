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
            expires_at = expires_at.replace(
                tzinfo=UTC
            )

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
        content="width=device-width, initial-scale=1, viewport-fit=cover"
    >
    <meta name="color-scheme" content="dark light">

    <title>Подключение Work&PlayVPN</title>

    <script src="https://telegram.org/js/telegram-web-app.js"></script>

    <style>
        :root {{
            color-scheme: dark;
            --background: #080b14;
            --surface: #111725;
            --surface-soft: #171f31;
            --text: #f7f8fc;
            --muted: #aab3c8;
            --accent: #6d7cff;
            --accent-strong: #5262f2;
            --border: rgba(255, 255, 255, 0.10);
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            min-height: 100vh;
            padding:
                max(20px, env(safe-area-inset-top))
                16px
                max(28px, env(safe-area-inset-bottom));
            background:
                radial-gradient(
                    circle at top right,
                    rgba(109, 124, 255, 0.22),
                    transparent 38%
                ),
                var(--background);
            color: var(--text);
            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
        }}

        main {{
            width: min(100%, 680px);
            margin: 0 auto;
        }}

        .hero {{
            padding: 8px 4px 20px;
        }}

        .eyebrow {{
            margin: 0 0 8px;
            color: #94a0ff;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}

        h1 {{
            margin: 0;
            font-size: clamp(28px, 8vw, 42px);
            line-height: 1.05;
        }}

        .lead {{
            margin: 14px 0 0;
            color: var(--muted);
            font-size: 16px;
            line-height: 1.5;
        }}

        .tabs {{
            display: flex;
            gap: 8px;
            margin: 4px 0 16px;
            padding-bottom: 4px;
            overflow-x: auto;
            scrollbar-width: none;
        }}

        .tabs::-webkit-scrollbar {{
            display: none;
        }}

        .tab {{
            flex: 0 0 auto;
            padding: 11px 14px;
            border: 1px solid var(--border);
            border-radius: 999px;
            background: var(--surface);
            color: var(--muted);
            font: inherit;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
        }}

        .tab.active {{
            border-color: transparent;
            background: var(--accent);
            color: #fff;
        }}

        .panel {{
            display: none;
            padding: 22px;
            border: 1px solid var(--border);
            border-radius: 24px;
            background: rgba(17, 23, 37, 0.96);
            box-shadow: 0 22px 60px rgba(0, 0, 0, 0.28);
        }}

        .panel.active {{
            display: block;
        }}

        h2 {{
            margin: 0 0 16px;
            font-size: 23px;
        }}

        ol {{
            margin: 0;
            padding-left: 22px;
        }}

        li {{
            margin: 0 0 14px;
            padding-left: 4px;
            color: var(--muted);
            line-height: 1.5;
        }}

        li strong {{
            color: var(--text);
        }}

        .downloads {{
            display: grid;
            gap: 10px;
            margin: 18px 0;
        }}

        .download,
        .connect {{
            display: block;
            width: 100%;
            padding: 15px 18px;
            border-radius: 15px;
            text-align: center;
            text-decoration: none;
            font-size: 16px;
            font-weight: 800;
        }}

        .download {{
            border: 1px solid var(--border);
            background: var(--surface-soft);
            color: var(--text);
        }}

        .connect {{
            margin-top: 18px;
            background: linear-gradient(
                135deg,
                var(--accent),
                var(--accent-strong)
            );
            color: #fff;
            box-shadow: 0 12px 28px rgba(82, 98, 242, 0.32);
        }}

        .note {{
            margin: 14px 0 0;
            color: var(--muted);
            font-size: 13px;
            line-height: 1.45;
            text-align: center;
        }}

        .desktop-note {{
            margin-top: 18px;
            padding: 14px;
            border: 1px solid var(--border);
            border-radius: 14px;
            background: var(--surface-soft);
            color: var(--muted);
            font-size: 14px;
            line-height: 1.5;
        }}
    </style>
</head>

<body>
    <main>
        <header class="hero">
            <p class="eyebrow">Work&amp;PlayVPN</p>
            <h1>Инструкция по подключению</h1>
            <p class="lead">
                Выберите своё устройство, установите HAPP
                и добавьте подписку одной кнопкой.
            </p>
        </header>

        <nav class="tabs" aria-label="Выбор устройства">
            <button class="tab" data-platform="ios">iPhone / iPad</button>
            <button class="tab" data-platform="android">Android</button>
            <button class="tab" data-platform="windows">Windows</button>
            <button class="tab" data-platform="macos">macOS</button>
            <button class="tab" data-platform="linux">Linux</button>
            <button class="tab" data-platform="tv">TV</button>
        </nav>

        <section class="panel" data-panel="ios">
            <h2>iPhone и iPad</h2>
            <ol>
                <li>Установите <strong>HAPP</strong> из App Store.</li>
                <li>Вернитесь в эту инструкцию.</li>
                <li>Нажмите <strong>«Открыть в HAPP»</strong>.</li>
                <li>Подтвердите открытие приложения и добавление подписки.</li>
            </ol>
            <div class="downloads">
                <a class="download" href="https://apps.apple.com/ru/app/happ-proxy-utility/id6783623643" target="_blank" rel="noopener noreferrer">
                    Скачать HAPP — App Store RU
                </a>
                <a class="download" href="https://apps.apple.com/us/app/happ-proxy-utility/id6504287215" target="_blank" rel="noopener noreferrer">
                    Скачать HAPP — App Store Global
                </a>
            </div>
            <a class="connect" href="{safe_happ_url}">Открыть в HAPP</a>
            <p class="note">iOS может показать системное окно подтверждения — нажмите «Открыть».</p>
        </section>

        <section class="panel" data-panel="android">
            <h2>Android</h2>
            <ol>
                <li>Установите <strong>HAPP</strong> из Google Play или официальный APK.</li>
                <li>Вернитесь в эту инструкцию.</li>
                <li>Нажмите <strong>«Открыть в HAPP»</strong> и подтвердите добавление.</li>
            </ol>
            <div class="downloads">
                <a class="download" href="https://play.google.com/store/apps/details?id=com.happproxy" target="_blank" rel="noopener noreferrer">
                    Скачать HAPP — Google Play
                </a>
                <a class="download" href="https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk" target="_blank" rel="noopener noreferrer">
                    Скачать официальный APK
                </a>
            </div>
            <a class="connect" href="{safe_happ_url}">Открыть в HAPP</a>
        </section>

        <section class="panel" data-panel="windows">
            <h2>Windows</h2>
            <ol>
                <li>Скачайте и установите <strong>HAPP</strong>.</li>
                <li>Разрешите запуск приложения, если Windows запросит подтверждение.</li>
                <li>Вернитесь сюда и нажмите <strong>«Открыть в HAPP»</strong>.</li>
            </ol>
            <div class="downloads">
                <a class="download" href="https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe" target="_blank" rel="noopener noreferrer">
                    Скачать HAPP для Windows x64
                </a>
            </div>
            <a class="connect" href="{safe_happ_url}">Открыть в HAPP</a>
        </section>

        <section class="panel" data-panel="macos">
            <h2>macOS</h2>
            <ol>
                <li>Установите <strong>HAPP</strong> из App Store или DMG.</li>
                <li>Запустите приложение хотя бы один раз.</li>
                <li>Вернитесь сюда и нажмите <strong>«Открыть в HAPP»</strong>.</li>
            </ol>
            <div class="downloads">
                <a class="download" href="https://apps.apple.com/ru/app/happ-proxy-utility/id6783623643" target="_blank" rel="noopener noreferrer">
                    Скачать HAPP — App Store RU
                </a>
                <a class="download" href="https://github.com/Happ-proxy/happ-desktop/releases/latest/download/Happ.macOS.universal.dmg" target="_blank" rel="noopener noreferrer">
                    Скачать HAPP — universal DMG
                </a>
            </div>
            <a class="connect" href="{safe_happ_url}">Открыть в HAPP</a>
        </section>

        <section class="panel" data-panel="linux">
            <h2>Linux</h2>
            <ol>
                <li>Выберите пакет для своего дистрибутива.</li>
                <li>Установите и запустите <strong>HAPP</strong>.</li>
                <li>Нажмите <strong>«Открыть в HAPP»</strong>.</li>
            </ol>
            <div class="downloads">
                <a class="download" href="https://github.com/Happ-proxy/happ-desktop/releases/latest/download/Happ.linux.x64.deb" target="_blank" rel="noopener noreferrer">Скачать DEB</a>
                <a class="download" href="https://github.com/Happ-proxy/happ-desktop/releases/latest/download/Happ.linux.x64.rpm" target="_blank" rel="noopener noreferrer">Скачать RPM</a>
                <a class="download" href="https://github.com/Happ-proxy/happ-desktop/releases/latest/download/Happ.linux.x64.pkg.tar.zst" target="_blank" rel="noopener noreferrer">Скачать Arch package</a>
            </div>
            <a class="connect" href="{safe_happ_url}">Открыть в HAPP</a>
        </section>

        <section class="panel" data-panel="tv">
            <h2>Apple TV и Android TV</h2>
            <ol>
                <li>Установите HAPP из магазина приложений телевизора.</li>
                <li>Откройте HAPP на телевизоре.</li>
                <li>Используйте ключ из бота или доступный в HAPP способ импорта.</li>
            </ol>
            <div class="downloads">
                <a class="download" href="https://apps.apple.com/us/app/happ-proxy-utility-for-tv/id6748297274" target="_blank" rel="noopener noreferrer">
                    HAPP для Apple TV
                </a>
                <a class="download" href="https://play.google.com/store/apps/details?id=com.happproxy" target="_blank" rel="noopener noreferrer">
                    HAPP для Android TV
                </a>
            </div>
            <div class="desktop-note">
                Для телевизора удобнее открыть в боте действие
                «Показать ключ», а затем перенести ключ на устройство.
            </div>
        </section>
    </main>

    <script>
        const telegramApp = window.Telegram?.WebApp;

        if (telegramApp) {{
            telegramApp.ready();
            telegramApp.expand();
        }}

        const tabs = Array.from(
            document.querySelectorAll("[data-platform]")
        );
        const panels = Array.from(
            document.querySelectorAll("[data-panel]")
        );

        function activatePlatform(platform) {{
            tabs.forEach((tab) => {{
                tab.classList.toggle(
                    "active",
                    tab.dataset.platform === platform
                );
            }});

            panels.forEach((panel) => {{
                panel.classList.toggle(
                    "active",
                    panel.dataset.panel === platform
                );
            }});

            const activeTab = tabs.find(
                (tab) => tab.dataset.platform === platform
            );

            activeTab?.scrollIntoView({{
                behavior: "smooth",
                block: "nearest",
                inline: "center",
            }});
        }}

        function detectPlatform() {{
            const userAgent = navigator.userAgent.toLowerCase();
            const platform = navigator.platform?.toLowerCase() || "";

            if (
                /iphone|ipad|ipod/.test(userAgent)
                || (platform === "macintel" && navigator.maxTouchPoints > 1)
            ) {{
                return "ios";
            }}

            if (/android/.test(userAgent)) {{
                return "android";
            }}

            if (/windows/.test(userAgent)) {{
                return "windows";
            }}

            if (/macintosh|mac os x/.test(userAgent)) {{
                return "macos";
            }}

            if (/linux/.test(userAgent)) {{
                return "linux";
            }}

            return "ios";
        }}

        tabs.forEach((tab) => {{
            tab.addEventListener("click", () => {{
                activatePlatform(tab.dataset.platform);
            }});
        }});

        activatePlatform(detectPlatform());
    </script>
</body>
</html>
"""

    return HTMLResponse(
        content=html,
        status_code=200,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": (
                "noindex, nofollow, noarchive"
            ),
        },
    )
