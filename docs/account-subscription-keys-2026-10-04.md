# Work&PlayVPN — один ключ на подписку

Обновление поверх 4146855. Этот документ заменяет инструкции выбора устройства для ключа из предыдущих доработок.

## Поведение

- Basic использует общую ссылку `/sub/<Basic token>`, Mobile — `/sub/<Mobile token>` этого Telegram-аккаунта. В пути ключа больше нет ID устройства. Эти ссылки уже поддерживает backend; для Mobile сохраняется существующая автоматическая маршрутизация по настройкам аккаунта.
- Обе ссылки шифруются официальным API Happ в crypt5. Копирование, полный ключ и QR относятся к выбранной подписке, независимо от списка устройств. Ключ помощи остаётся отдельным.
- Mini App заранее получает ключ выбранной подписки. После загрузки кнопка «Скопировать ключ» копирует его в буфер и меняется на «✓ Скопировано». QR и полный ключ открываются сразу без выбора устройства. Полученные значения хранятся только в памяти открытого приложения; при обновлении данных кэш сбрасывается.
- Бот больше не отправляет ключ отдельным сообщением или файлом. В меню подписки «Скопировать ключ» открывает окно Mini App сразу для нужной подписки. В этом окне нужно нажать кнопку копирования. Это ограничение Telegram: нативный CopyTextButton допускает максимум 256 символов, crypt5 длиннее. Длинная ссылка не обрезается и не заменяется незашифрованной.
- QR в боте выводится сразу. Старые кнопки с ID устройства также выдают общую ссылку подписки отправителя, а не ключ указанного устройства.
- Авторизация Telegram, внутренний API-секрет бота, проверка активной подписки и WP в центре QR сохранены. Неактивный тариф не выдаёт ключ. При недоступности шифрования возвращается ошибка.
- Выдача ссылки сама по себе не регистрирует устройство. После установки исправления `docs/happ-device-registration-2026-10-04.md` и включения регистрации устройство создаётся при первом запросе подписки из Happ с HWID. Управление устройствами и покупка лимита сохранены.
- Миграций, новых зависимостей и изменений .env нет. Файлы Caddy смонтированы с диска, версия JS обновлена на 20261004-3.

## Локальные проверки

Проверены изолированные backend-тесты ключей и QR, полный набор тестов бота и функциональные проверки JavaScript: одинаковый источник ключа/QR, разделение Basic и Mobile, копирование и подтверждение, отказ буфера обмена, сброс устаревшего ответа. PostgreSQL-набор и реальный импорт в Happ проверяются после распаковки и установки.

## Windows: распаковка и тесты

```powershell
$ErrorActionPreference = "Stop"
$archivePath = (Resolve-Path -LiteralPath .\WorkPlayVPN-account-subscription-keys-2026-10-04.zip).Path
Expand-Archive -LiteralPath $archivePath -DestinationPath . -Force -ErrorAction Stop
$backendSource = Join-Path (Get-Location).Path "backend"
$opsSource = Join-Path (Get-Location).Path "ops"
$botSource = Join-Path (Get-Location).Path "bot"
docker compose --profile testing run --rm --pull never --volume "${backendSource}:/app:ro" --volume "${opsSource}:/ops:ro" tests
if ($LASTEXITCODE -ne 0) { throw "Тесты backend не прошли" }
docker compose run --rm --no-deps --pull never --volume "${botSource}:/app:ro" --entrypoint python bot -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Тесты бота не прошли" }
git -c core.whitespace=cr-at-eol diff --check
if ($LASTEXITCODE -ne 0) { throw "Проверка изменений не прошла" }
```

Если установлен Node.js, дополнительно: `node caddy/mini-app/tests/account-keys.cjs`.

## Коммит после успешных тестов

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($archivePath)
try { $patchFiles = @($archive.Entries | Where-Object { $_.Name -ne "" } | ForEach-Object { $_.FullName }) }
finally { $archive.Dispose() }
git add -- $patchFiles
if ($LASTEXITCODE -ne 0) { throw "Не удалось добавить файлы" }
git -c core.whitespace=cr-at-eol diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Проверка изменений не прошла" }
git diff --cached --stat
git commit -m "Use one Happ key per subscription and remove device key selection"
if ($LASTEXITCODE -ne 0) { throw "Коммит не создан" }
git push origin main
if ($LASTEXITCODE -ne 0) { throw "Не удалось отправить коммит" }
git log -1 --oneline
```

## Сервер

```bash
set -e
cd /opt/workplayvpn
git pull --ff-only origin main
docker compose build backend bot
docker compose up -d --no-deps --force-recreate backend bot
docker compose ps backend bot
docker compose logs --tail 40 backend bot
```

## Проверка после установки

Полностью закрыть и заново открыть Mini App. Для Basic и Mobile проверить: копирование меняет подпись на «✓ Скопировано», полный ключ и QR открываются без выбора устройства, ключ импортируется в Happ. В боте открыть новое меню подписки: копирование ведёт прямо в окно ключа нужного тарифа, QR появляется сразу и содержит WP. Проверить импорт одного ключа на двух собственных зарегистрированных устройствах. Действующие ключи и QR в переписку не присылать.
