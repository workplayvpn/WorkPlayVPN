from datetime import UTC, datetime
from html import escape
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.responses import FileResponse, HTMLResponse
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

STATIC_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "static"
)


@router.get(
    "/assets/happ-connect.css",
    include_in_schema=False,
)
def get_happ_connect_styles() -> FileResponse:
    return FileResponse(
        path=STATIC_DIRECTORY / "happ_connect.css",
        media_type="text/css",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/assets/happ-connect.js",
    include_in_schema=False,
)
def get_happ_connect_script() -> FileResponse:
    return FileResponse(
        path=STATIC_DIRECTORY / "happ_connect.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
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
    <meta name="color-scheme" content="dark">
    <meta name="theme-color" content="#081524">

    <title>Подключение WorkPlayVPN</title>

    <link
        rel="stylesheet"
        href="/connect/happ/assets/happ-connect.css"
    >

    <script
        src="https://telegram.org/js/telegram-web-app.js"
    ></script>

    <script
        src="/connect/happ/assets/happ-connect.js"
        defer
    ></script>
</head>

<body>
    <main class="app">
        <header class="topbar">
            <div class="brand">
                <div
                    class="brand-mark"
                    aria-hidden="true"
                >
                    W
                </div>

                <div>
                    <p class="brand-name">
                        WorkPlayVPN
                    </p>

                    <p class="brand-caption">
                        Безопасное подключение
                    </p>
                </div>
            </div>
        </header>

        <section class="hero">
            <p class="eyebrow">
                <span aria-hidden="true">✦</span>
                Быстрое подключение
            </p>

            <h1>
                Подключите HAPP за несколько шагов
            </h1>

            <p class="lead">
                Выберите своё устройство, установите HAPP
                и добавьте подписку одной кнопкой.
            </p>
        </section>

        <p class="platform-title">
            Выберите платформу
        </p>

        <nav
            class="platforms"
            aria-label="Выбор платформы"
            role="tablist"
        >
            <button
                class="platform-tab"
                type="button"
                role="tab"
                aria-controls="panel-ios"
                aria-selected="false"
                data-platform="ios"
            >
                <span
                    class="platform-icon"
                    aria-hidden="true"
                >
                    
                </span>

                <span>
                    <span class="platform-label">
                        iPhone / iPad
                    </span>

                    <span class="platform-detail">
                        iOS и iPadOS
                    </span>
                </span>
            </button>

            <button
                class="platform-tab"
                type="button"
                role="tab"
                aria-controls="panel-android"
                aria-selected="false"
                data-platform="android"
            >
                <span
                    class="platform-icon"
                    aria-hidden="true"
                >
                    🤖
                </span>

                <span>
                    <span class="platform-label">
                        Android
                    </span>

                    <span class="platform-detail">
                        Телефоны и планшеты
                    </span>
                </span>
            </button>

            <button
                class="platform-tab"
                type="button"
                role="tab"
                aria-controls="panel-windows"
                aria-selected="false"
                data-platform="windows"
            >
                <span
                    class="platform-icon"
                    aria-hidden="true"
                >
                    ▦
                </span>

                <span>
                    <span class="platform-label">
                        Windows
                    </span>

                    <span class="platform-detail">
                        Компьютеры и ноутбуки
                    </span>
                </span>
            </button>

            <button
                class="platform-tab"
                type="button"
                role="tab"
                aria-controls="panel-macos"
                aria-selected="false"
                data-platform="macos"
            >
                <span
                    class="platform-icon"
                    aria-hidden="true"
                >
                    
                </span>

                <span>
                    <span class="platform-label">
                        macOS
                    </span>

                    <span class="platform-detail">
                        MacBook и Mac
                    </span>
                </span>
            </button>

            <button
                class="platform-tab"
                type="button"
                role="tab"
                aria-controls="panel-linux"
                aria-selected="false"
                data-platform="linux"
            >
                <span
                    class="platform-icon"
                    aria-hidden="true"
                >
                    🐧
                </span>

                <span>
                    <span class="platform-label">
                        Linux
                    </span>

                    <span class="platform-detail">
                        DEB, RPM и Arch
                    </span>
                </span>
            </button>

            <button
                class="platform-tab"
                type="button"
                role="tab"
                aria-controls="panel-tv"
                aria-selected="false"
                data-platform="tv"
            >
                <span
                    class="platform-icon"
                    aria-hidden="true"
                >
                    📺
                </span>

                <span>
                    <span class="platform-label">
                        Телевизор
                    </span>

                    <span class="platform-detail">
                        Apple TV и Android TV
                    </span>
                </span>
            </button>
        </nav>

        <section
            class="panel"
            id="panel-ios"
            role="tabpanel"
            aria-hidden="true"
            data-panel="ios"
        >
            <div class="panel-heading">
                <div
                    class="panel-heading-icon"
                    aria-hidden="true"
                >
                    
                </div>

                <div>
                    <h2>iPhone и iPad</h2>

                    <p class="panel-subtitle">
                        Подключение через App Store
                    </p>
                </div>
            </div>

            <ol class="steps">
                <li class="step">
                    Установите <strong>HAPP</strong>
                    из App Store.
                </li>

                <li class="step">
                    После установки вернитесь
                    в эту инструкцию.
                </li>

                <li class="step">
                    Нажмите
                    <strong>«Открыть в HAPP»</strong>.
                </li>

                <li class="step">
                    Подтвердите открытие приложения
                    и добавление подписки.
                </li>
            </ol>

            <div class="actions">
                <a
                    class="button button-secondary"
                    href="https://apps.apple.com/ru/app/happ-proxy-utility/id6783623643"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    Скачать HAPP — App Store RU
                </a>

                <a
                    class="button button-secondary"
                    href="https://apps.apple.com/us/app/happ-proxy-utility/id6504287215"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    Скачать HAPP — App Store Global
                </a>

                <a
                    class="button button-primary"
                    href="{safe_happ_url}"
                    data-happ-link
                >
                    Открыть в HAPP
                    <span aria-hidden="true">→</span>
                </a>
            </div>

            <div class="notice">
                <span
                    class="notice-icon"
                    aria-hidden="true"
                >
                    ℹ️
                </span>

                <span>
                    iOS может показать системное окно.
                    Нажмите «Открыть», чтобы перейти в HAPP.
                </span>
            </div>
        </section>

        <section
            class="panel"
            id="panel-android"
            role="tabpanel"
            aria-hidden="true"
            data-panel="android"
        >
            <div class="panel-heading">
                <div
                    class="panel-heading-icon"
                    aria-hidden="true"
                >
                    🤖
                </div>

                <div>
                    <h2>Android</h2>

                    <p class="panel-subtitle">
                        Google Play или официальный APK
                    </p>
                </div>
            </div>

            <ol class="steps">
                <li class="step">
                    Установите <strong>HAPP</strong>
                    из Google Play или с официального GitHub.
                </li>

                <li class="step">
                    После установки вернитесь
                    в эту инструкцию.
                </li>

                <li class="step">
                    Нажмите
                    <strong>«Открыть в HAPP»</strong>.
                </li>

                <li class="step">
                    Подтвердите добавление подписки.
                </li>
            </ol>

            <div class="actions">
                <a
                    class="button button-secondary"
                    href="https://play.google.com/store/apps/details?id=com.happproxy"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    Скачать HAPP — Google Play
                </a>

                <a
                    class="button button-secondary"
                    href="https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    Скачать официальный APK
                </a>

                <a
                    class="button button-primary"
                    href="{safe_happ_url}"
                    data-happ-link
                >
                    Открыть в HAPP
                    <span aria-hidden="true">→</span>
                </a>
            </div>
        </section>

        <section
            class="panel"
            id="panel-windows"
            role="tabpanel"
            aria-hidden="true"
            data-panel="windows"
        >
            <div class="panel-heading">
                <div
                    class="panel-heading-icon"
                    aria-hidden="true"
                >
                    ▦
                </div>

                <div>
                    <h2>Windows</h2>

                    <p class="panel-subtitle">
                        Windows 10 и Windows 11
                    </p>
                </div>
            </div>

            <ol class="steps">
                <li class="step">
                    Скачайте и установите
                    <strong>HAPP</strong>.
                </li>

                <li class="step">
                    Разрешите запуск приложения,
                    если Windows запросит подтверждение.
                </li>

                <li class="step">
                    Вернитесь сюда и нажмите
                    <strong>«Открыть в HAPP»</strong>.
                </li>

                <li class="step">
                    Подтвердите добавление подписки.
                </li>
            </ol>

            <div class="actions">
                <a
                    class="button button-secondary"
                    href="https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    Скачать HAPP для Windows x64
                </a>

                <a
                    class="button button-primary"
                    href="{safe_happ_url}"
                    data-happ-link
                >
                    Открыть в HAPP
                    <span aria-hidden="true">→</span>
                </a>
            </div>
        </section>

        <section
            class="panel"
            id="panel-macos"
            role="tabpanel"
            aria-hidden="true"
            data-panel="macos"
        >
            <div class="panel-heading">
                <div
                    class="panel-heading-icon"
                    aria-hidden="true"
                >
                    
                </div>

                <div>
                    <h2>macOS</h2>

                    <p class="panel-subtitle">
                        Для Mac на Apple Silicon и Intel
                    </p>
                </div>
            </div>

            <ol class="steps">
                <li class="step">
                    Установите <strong>HAPP</strong>
                    из App Store или DMG-файла.
                </li>

                <li class="step">
                    Запустите приложение хотя бы один раз.
                </li>

                <li class="step">
                    Вернитесь сюда и нажмите
                    <strong>«Открыть в HAPP»</strong>.
                </li>

                <li class="step">
                    Подтвердите добавление подписки.
                </li>
            </ol>

            <div class="actions">
                <a
                    class="button button-secondary"
                    href="https://apps.apple.com/ru/app/happ-proxy-utility/id6783623643"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    Скачать HAPP — App Store
                </a>

                <a
                    class="button button-secondary"
                    href="https://github.com/Happ-proxy/happ-desktop/releases/latest/download/Happ.macOS.universal.dmg"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    Скачать HAPP — universal DMG
                </a>

                <a
                    class="button button-primary"
                    href="{safe_happ_url}"
                    data-happ-link
                >
                    Открыть в HAPP
                    <span aria-hidden="true">→</span>
                </a>
            </div>
        </section>

        <section
            class="panel"
            id="panel-linux"
            role="tabpanel"
            aria-hidden="true"
            data-panel="linux"
        >
            <div class="panel-heading">
                <div
                    class="panel-heading-icon"
                    aria-hidden="true"
                >
                    🐧
                </div>

                <div>
                    <h2>Linux</h2>

                    <p class="panel-subtitle">
                        Популярные форматы пакетов
                    </p>
                </div>
            </div>

            <ol class="steps">
                <li class="step">
                    Выберите пакет для своего дистрибутива.
                </li>

                <li class="step">
                    Установите и запустите
                    <strong>HAPP</strong>.
                </li>

                <li class="step">
                    Вернитесь сюда и нажмите
                    <strong>«Открыть в HAPP»</strong>.
                </li>

                <li class="step">
                    Подтвердите добавление подписки.
                </li>
            </ol>

            <div class="actions">
                <a
                    class="button button-secondary"
                    href="https://github.com/Happ-proxy/happ-desktop/releases/latest/download/Happ.linux.x64.deb"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    Скачать DEB
                </a>

                <a
                    class="button button-secondary"
                    href="https://github.com/Happ-proxy/happ-desktop/releases/latest/download/Happ.linux.x64.rpm"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    Скачать RPM
                </a>

                <a
                    class="button button-secondary"
                    href="https://github.com/Happ-proxy/happ-desktop/releases/latest/download/Happ.linux.x64.pkg.tar.zst"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    Скачать Arch package
                </a>

                <a
                    class="button button-primary"
                    href="{safe_happ_url}"
                    data-happ-link
                >
                    Открыть в HAPP
                    <span aria-hidden="true">→</span>
                </a>
            </div>
        </section>

        <section
            class="panel"
            id="panel-tv"
            role="tabpanel"
            aria-hidden="true"
            data-panel="tv"
        >
            <div class="panel-heading">
                <div
                    class="panel-heading-icon"
                    aria-hidden="true"
                >
                    📺
                </div>

                <div>
                    <h2>Телевизор</h2>

                    <p class="panel-subtitle">
                        Apple TV и Android TV
                    </p>
                </div>
            </div>

            <ol class="steps">
                <li class="step">
                    Установите <strong>HAPP</strong>
                    из магазина приложений телевизора.
                </li>

                <li class="step">
                    Откройте HAPP на телевизоре.
                </li>

                <li class="step">
                    Используйте доступный в приложении
                    способ импорта подписки.
                </li>
            </ol>

            <div class="actions">
                <a
                    class="button button-secondary"
                    href="https://apps.apple.com/us/app/happ-proxy-utility-for-tv/id6748297274"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    HAPP для Apple TV
                </a>

                <a
                    class="button button-secondary"
                    href="https://play.google.com/store/apps/details?id=com.happproxy"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    HAPP для Android TV
                </a>
            </div>

            <div class="notice">
                <span
                    class="notice-icon"
                    aria-hidden="true"
                >
                    ℹ️
                </span>

                <span>
                    Подробный безопасный способ переноса
                    подписки на телевизор мы добавим
                    отдельным этапом.
                </span>
            </div>
        </section>

        <aside class="help-card">
            <h3>Не получилось подключиться?</h3>

            <p>
                Вернитесь в Telegram-бот WorkPlayVPN
                и откройте раздел поддержки.
            </p>
        </aside>

        <footer class="footer">
            WorkPlayVPN · Безопасное подключение
        </footer>
    </main>
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