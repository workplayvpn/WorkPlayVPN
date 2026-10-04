# Work&PlayVPN — прямой импорт ключей в Happ и crypt5

Архив WorkPlayVPN-miniapp-crypt5-fix-2026-10-04.zip содержит все изменения предыдущего обновления ключей и устройств плюс исправление. Можно применять после main 9c1d1f7 или поверх предыдущего архива оформления ключей. Перед заменой сохраните собственные незакоммиченные изменения, если они затрагивают эти файлы.

## Исправление

Ранее копировался адрес HTML-инструкции `/connect/happ/...`, который Happ не может импортировать как подписку. Теперь backend получает соответствующий адрес подписки `/sub/...` и шифрует его через существующую интеграцию с официальным API Happ: https://crypto.happ.su/api-v2.php.

- «Скопировать ключ», «Показать полный ключ» и QR используют одинаковый `happ://crypt5/...`.
- «Добавить в Happ» открывает этот ключ напрямую, без страницы инструкции.
- Для Basic и автоматического Mobile сохраняется выбранное устройство. Для прежнего Mobile без автомаршрутизации используется общий ключ подписки.
- Чужое, удалённое устройство и неактивная подписка не дают получить ключ. Запрос требует проверенную авторизацию Telegram Mini App.
- Если API шифрования недоступен, возвращается ошибка. Незашифрованная ссылка или страница инструкции не подставляется.
- QR генерируется нашим backend; сторонний сервис QR не используется.
- Иллюстрации устройств, оформление и управление окнами из предыдущего обновления сохранены.

Для этих действий Mini App crypt5 включён независимо от списка HAPP_CRYPT5_USER_IDS. Прежний механизм запуска инструкции и его настройки не изменены. Новые миграции и изменения .env не нужны. Требуется исходящий доступ backend к API Happ и зависимость qrcode==8.2 (включена в архив).

crypt5 скрывает исходный адрес подписки, но не предотвращает передачу самого ключа другим людям. Не публикуйте действующие ключи и QR.

## 1. Распаковка и тесты на Windows

Положите ZIP в корень проекта, рядом с docker-compose.yml.

```powershell
$ErrorActionPreference = "Stop"
$archivePath = (Resolve-Path -LiteralPath .\WorkPlayVPN-miniapp-crypt5-fix-2026-10-04.zip).Path
Expand-Archive -LiteralPath $archivePath -DestinationPath . -Force -ErrorAction Stop

$backendSource = Join-Path (Get-Location).Path "backend"
$opsSource = Join-Path (Get-Location).Path "ops"
docker compose --profile testing run --build --rm --volume "${backendSource}:/app:ro" --volume "${opsSource}:/ops:ro" tests
if ($LASTEXITCODE -ne 0) { throw "Тесты backend не прошли" }

git -c core.whitespace=cr-at-eol diff --check
if ($LASTEXITCODE -ne 0) { throw "Проверка изменений не прошла" }
```

Если сборка остановилась из-за Docker Hub TLS timeout, тесты не запускались: восстановите доступ к Docker Hub и повторите команду. Не переходите к коммиту при ошибке.

## 2. Коммит после успешных тестов

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($archivePath)
try {
    $patchFiles = @($archive.Entries | Where-Object { $_.Name -ne "" } | ForEach-Object { $_.FullName })
} finally {
    $archive.Dispose()
}
git add -- $patchFiles
if ($LASTEXITCODE -ne 0) { throw "Не удалось добавить файлы" }
git -c core.whitespace=cr-at-eol diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Проверка изменений не прошла" }
git diff --cached --stat
git commit -m "Fix Mini App Happ keys and crypt5 QR import"
if ($LASTEXITCODE -ne 0) { throw "Коммит не создан" }
git push origin main
if ($LASTEXITCODE -ne 0) { throw "Не удалось отправить коммит" }
git log -1 --oneline
```

ZIP, .env, test.db и прочие посторонние файлы не добавляются.

## 3. Обновление сервера

```bash
set -e
cd /opt/workplayvpn
git pull --ff-only origin main
docker compose build backend
docker compose up -d --no-deps --force-recreate backend
docker compose ps backend
docker compose logs --tail 40 backend
```

В текущем развёртывании файлы caddy смонтированы с диска, поэтому перезапуск Caddy не нужен. Версия JS/CSS изменена на 20261004-1. Полностью закройте и снова откройте Mini App.

## 4. Проверка на телефоне

1. Basic → копирование ключа → выбрать устройство. Скопированная строка начинается с `happ://crypt5/`, а не https://.../connect/happ/.
2. Вставить в Happ и проверить успешный импорт нужной подписки.
3. «Показать полный ключ» показывает тот же ключ; «Добавить в Happ» открывает Happ напрямую, если он установлен.
4. QR содержит ключ Happ, а не адрес инструкции. Сканирование проверить встроенным сканером Happ; камера ОС может иначе обрабатывать нестандартную схему.
5. Повторить для Mobile и другого устройства. Проверить закрытие окна и возврат назад.
6. При ошибке шифрования проверить исходящий доступ backend к API Happ; не публиковать ключи и токены в логах или сообщениях.

## Выполненные проверки

Локально: 20 изолированных тестов endpoint/интеграции шифрования прошли; проверки сценариев JavaScript и синтаксиса прошли. Полный набор с PostgreSQL нужно запустить командой выше. Реальный запрос к API Happ из среды сборки завершился тайм-аутом; успешный живой импорт и сканирование здесь не подтверждены, их нужно проверить после развёртывания.
