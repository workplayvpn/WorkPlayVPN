# Work&PlayVPN — синхронизация ключей бота и QR с WP

Обновление поверх 89106ba. В архиве только изменённые и новые файлы этой доработки.

## Изменения

- Бот: «Показать ключ» и «Показать QR-код» сначала предлагают выбрать собственное подключённое устройство. Указанная подписка должна быть активна.
- Бот получает crypt5 через новый внутренний endpoint backend, защищённый INTERNAL_API_SECRET. Используется тот же проверенный выбор ссылки, что и в Mini App. Telegram ID берётся из отправителя callback, а не из данных кнопки.
- Для Basic и автоматического Mobile выдаётся ключ выбранного устройства. Для прежнего Mobile сохранён общий ключ после проверки принадлежности выбранного устройства.
- В группах бот не выдаёт эти ключи и QR. При ошибке шифрования исходная ссылка не раскрывается.
- Telegram CopyTextButton допускает максимум 256 символов. Более длинный crypt5 отображается отдельным полным блоком кода для копирования, а кнопка ведёт к подпискам Mini App, где есть полноценное копирование. Ключ никогда не обрезается. При длине более 3900 символов полный текст отправляется файлом happ-key.txt.
- В центре QR бота и Mini App появилась небольшая бирюзовая эмблема WP. Оба формата создаются общим сервисом backend: SVG для Mini App и PNG для Telegram.
- Коррекция ошибок H для обычных ключей, Q/M с меньшей эмблемой для более длинных. Белая внешняя рамка сохранена. Слишком длинный для QR ключ вызывает контролируемую ошибку.
- Новых зависимостей, настроек .env и миграций нет. Пересобрать backend и bot. Файлы caddy смонтированы с диска; версия frontend изменена на 20261004-2.

## Проверки

Локально прошли 30 изолированных backend-тестов и 49 тестов бота. Отдельно декодированы PNG с WP для синтетических ключей длиной примерно 150–2000 символов, включая уменьшение до 720×720 и JPEG quality 75; восстановлен полный исходный текст. Также декодирован SVG с WP после растеризации. Эти проверки не заменяют проверку реальным сканером Happ и камерой телефона. Полный PostgreSQL-набор нужно запустить ниже.

## Windows: распаковка и тесты

```powershell
$ErrorActionPreference = "Stop"
$archivePath = (Resolve-Path -LiteralPath .\WorkPlayVPN-bot-crypt5-wp-qr-2026-10-04.zip).Path
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

## Коммит после тестов

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
git commit -m "Sync bot Happ crypt5 keys and add WP QR branding"
if ($LASTEXITCODE -ne 0) { throw "Коммит не создан" }
git push origin main
if ($LASTEXITCODE -ne 0) { throw "Не удалось отправить коммит" }
git log -1 --oneline
```

## Сервер после успешной отправки

```bash
set -e
cd /opt/workplayvpn
git pull --ff-only origin main
docker compose build backend bot
docker compose up -d --no-deps --force-recreate backend bot
docker compose ps backend bot
docker compose logs --tail 40 backend bot
```

## Телефон

Полностью закрыть Mini App и открыть заново. Проверить Basic и Mobile: ключ и QR из бота, выбор другого устройства, импорт в Happ. QR должен показывать WP в центре и добавлять подписку, а не инструкцию. Проверить сканером Happ QR из Mini App. Существующие кнопки инструкции остаются инструкциями установки и подключения; действия «Показать ключ»/«Показать QR-код» выдают crypt5. Действующие ключи и QR не присылать в переписку.
