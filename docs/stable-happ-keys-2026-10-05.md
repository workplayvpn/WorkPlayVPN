# Постоянные Happ-ключи Basic и Mobile

Причина подтверждена проверкой на телефоне: одна и та же сохранённая crypt5-строка обновляет профиль, повторное копирование из Mini App создавало новую карточку. Раньше сервер заново шифровал адрес при каждом запросе. Теперь crypt5 сохраняется в базе: одна строка для Basic и одна для Mobile каждого пользователя.

Бот вызывает тот же обработчик ключа, поэтому копирование, QR-код и добавление из бота и Mini App получают один и тот же сохранённый ключ. Рестарт приложения не сбрасывает сохранённые ссылки. Регион, устройства и обычное продление не меняют строку импорта. Только изменение исходного адреса подписки (например, осознанная ротация токена или изменение домена) требует нового шифрования.

Таблица happ_import_links хранит user_id, access_tier, SHA-256 исходного адреса и зашифрованную ссылку. Первое создание сериализуется блокировкой аккаунта в PostgreSQL, чтобы одновременные обращения бота и Mini App не получили разные строки. При сбое шифрования некорректная ссылка не сохраняется и открытая ссылка не выдаётся.

## Windows: распаковка и тесты

```powershell
$ErrorActionPreference = "Stop"
Expand-Archive -LiteralPath .\WorkPlayVPN-stable-happ-keys-2026-10-05.zip -DestinationPath . -Force -ErrorAction Stop
$backendSource = Join-Path (Get-Location).Path "backend"
$opsSource = Join-Path (Get-Location).Path "ops"
docker compose --profile testing run --rm --pull never --volume "${backendSource}:/app:ro" --volume "${opsSource}:/ops:ro" tests
if ($LASTEXITCODE -ne 0) { throw "Тесты backend не прошли" }
git -c core.whitespace=cr-at-eol diff --check
if ($LASTEXITCODE -ne 0) { throw "Проверка изменений не прошла" }
```

Локально проверено 62 теста, 3 проверки конкурентной регистрации/генерации пропущены из-за отсутствия PostgreSQL. Полный набор и миграции проверяет ваш тестовый Docker-контейнер.

## Windows: коммит после тестов

```powershell
git add -- backend/alembic/env.py backend/alembic/versions/a310d5e8c742_stable_happ_import_links.py backend/app/models/happ_import_link.py backend/app/services/happ_import_link.py backend/app/api/mini_app.py backend/tests/test_mini_app_keys.py backend/tests/test_stable_happ_import_link.py docs/stable-happ-keys-2026-10-05.md
if ($LASTEXITCODE -ne 0) { throw "Не удалось добавить файлы" }
git -c core.whitespace=cr-at-eol diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Проверка изменений не прошла" }
git diff --cached --stat
git commit -m "Persist stable Happ crypt5 keys per account subscription tier"
if ($LASTEXITCODE -ne 0) { throw "Коммит не создан" }
git push origin main
if ($LASTEXITCODE -ne 0) { throw "Не удалось отправить коммит" }
```

## Сервер: миграция до запуска нового backend

В отличие от предыдущего исправления блокировки, здесь необходима новая таблица в базе. Действующие подписки и токены не изменяются.

```bash
cd /opt/workplayvpn
set -e
git pull --ff-only origin main
docker compose build backend
docker compose run --rm --no-deps --volume "${PWD}/backend:/app:ro" backend alembic upgrade head
docker compose up -d --no-deps backend
```

Миграция: f260ab91d803 -> a310d5e8c742. Команда использует настройки именно backend, включая серверный override с внешней БД и TLS. Workers и токены ботов не перенастраиваются.

```bash
docker compose exec -T backend python - <<'PY'
from sqlalchemy import text
from app.db.session import engine
print('DB host:', engine.url.host)
with engine.connect() as conn:
    print('Migration:', conn.scalar(text('SELECT version_num FROM alembic_version')))
    table = conn.scalar(text("SELECT to_regclass('public.happ_import_links')"))
    print('Stable links table:', table)
    assert table is not None
PY
docker compose ps backend
docker compose logs --tail=50 backend
```

## Проверка в Happ

1. После установки скопируйте Basic из Mini App и импортируйте в Happ.
2. Снова скопируйте Basic из Mini App и импортируйте: существующая новая карточка должна обновиться. Повторите трижды.
3. Скопируйте Basic из бота: это та же строка, он тоже должен обновить эту карточку.
4. Повторите с Mobile, затем с QR-кодом соответствующей подписки.
5. После перезапуска backend повторный запрос должен вернуть ту же строку.

Ранее выданные случайные шифротексты сервер не сохранял. Первая ссылка после этого обновления может создать ещё одну карточку; затем она остаётся постоянной. Старые дубли не удаляются автоматически. Уберите лишние карточки в Happ через меню самой карточки, сохранив один актуальный Basic и один Mobile. Устройства из личного кабинета ради удаления дублирующих карточек не удаляйте.

Поведение обновления при полностью идентичной строке подтверждено вашим тестом на текущей версии Happ. Другие версии приложения ещё не проверены.
