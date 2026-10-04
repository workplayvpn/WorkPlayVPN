# Автоматическое добавление устройств в Happ

Патч устанавливается поверх исправления регистрации устройств по HWID. Флаг HAPP_ACCOUNT_DEVICE_REGISTRATION_ENABLED должен оставаться включённым.

Общий ключ Basic и общий ключ Mobile сохраняются. Импорт QR или ссылки и обновление профиля регистрируют Happ по X-HWID. Один HWID занимает один общий слот для обеих подписок. Повторное добавление после удаления создаёт новую запись и новые VPN-данные; старые данные отзываются при удалении.

Выбран режим автоматического возврата: фоновое обновление тоже может вернуть удалённое устройство в свободный слот. Удаление не является постоянным запретом устройства. При заполненном лимите новый HWID не получает VPN-данных; сервер отдаёт информационный профиль с текстом «Превышен лимит устройств. Либо удалите устройство из списка, либо докупите слоты. Затем обновите подписку в Happ». Профиль использует только blackhole, без чужих ключей и рабочего сервера. Зарегистрированные устройства продолжают работать при заполненном лимите. После освобождения/покупки слота обновление информационного профиля регистрирует устройство.

Удаление из личного кабинета НЕ удаляет локальный профиль из Happ. Публичная документация Happ не содержит команды удалённого удаления профиля. Здесь отзываются серверные VPN-данные; приложение сохраняет свою запись. Внешний вид уведомления и импорт информационного JSON-профиля требуют проверки на реальном Happ. Некоторые версии могут показать обычную ошибку импорта вместо информационного профиля: это нужно проверить, а не считать гарантированным.

## Windows: установка и тесты

В корне проекта:

```powershell
$ErrorActionPreference = "Stop"
Expand-Archive -LiteralPath .\WorkPlayVPN-happ-auto-enrollment-2026-10-04.zip -DestinationPath . -Force -ErrorAction Stop
$backendSource = Join-Path (Get-Location).Path "backend"
$opsSource = Join-Path (Get-Location).Path "ops"
docker compose --profile testing run --rm --pull never --volume "${backendSource}:/app:ro" --volume "${opsSource}:/ops:ro" tests
if ($LASTEXITCODE -ne 0) { throw "Тесты backend не прошли" }
git -c core.whitespace=cr-at-eol diff --check
if ($LASTEXITCODE -ne 0) { throw "Проверка изменений не прошла" }
```

Локально проверено: 48 тестов прошли, 2 PostgreSQL-теста конкурентного импорта пропущены из-за отсутствия PostgreSQL. Полный набор проверяет ваш Docker-контейнер.

После успешных тестов:

```powershell
git add -- backend/app/services/happ_account_device.py backend/app/services/happ_device_limit_response.py backend/app/api/subscription_feed.py backend/app/api/happ_auto_route.py backend/tests/test_happ_account_device.py docs/happ-auto-enrollment-2026-10-04.md
if ($LASTEXITCODE -ne 0) { throw "Не удалось добавить файлы" }
git -c core.whitespace=cr-at-eol diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Проверка изменений не прошла" }
git diff --cached --stat
git commit -m "Automatically reenroll Happ devices and explain device limit"
if ($LASTEXITCODE -ne 0) { throw "Коммит не создан" }
git push origin main
if ($LASTEXITCODE -ne 0) { throw "Не удалось отправить коммит" }
```

## Сервер: после тестов и отправки коммита

```bash
cd /opt/workplayvpn
git pull --ff-only origin main && docker compose build backend && docker compose up -d --no-deps backend
```

Миграция не требуется. Настройки базы, токены ботов и workers не изменяются.

```bash
docker compose exec -T backend python - <<'PY'
from app.core.config import settings
print('Automatic device registration:', settings.happ_account_device_registration_enabled)
assert settings.happ_account_device_registration_enabled
PY
docker compose ps backend
docker compose logs --tail=50 backend
```

## Проверка на телефоне

1. Импортировать общий ключ Basic на новом телефоне QR-кодом. Проверить одну новую запись в кабинете.
2. Импортировать Mobile на этом же телефоне. Количество устройств не увеличивается.
3. Удалить телефон из кабинета. Старые VPN-данные должны перестать работать; запись профиля в Happ останется.
4. Обновить/повторно импортировать общий ключ. При свободном слоте телефон добавляется с новым WP-ID. Также это возможно при фоновом обновлении.
5. Заполнить лимит только своими тестовыми устройствами и импортировать ключ на ещё одном устройстве. Проверить текст уведомления и отсутствие VPN-доступа; счётчик не растёт.
6. Освободить слот и обновить профиль с уведомлением. Появляется реальный профиль, устройство занимает слот. Проверить в Basic и Mobile.

Ограничения HWID сохраняются: это идентификатор, сообщаемый клиентом, а не аппаратная аттестация. Клиенты без X-HWID не поддерживают автоматическую регистрацию. Скрипт не делает удалённого управления Happ и не гарантирует мгновенного обновления клиентского кэша.
