# Исправление покупки подарков — 05.10.2026

## Что изменено

- «Купить подарок» открывает выбор Basic/Mobile с краткими описаниями, затем список сроков.
- Выбор срока создаёт заказ и показывает его экран. Браузер сам не открывается.
- «Перейти к оплате» сначала запрашивает подтверждение, затем открывает Robokassa.
- «Продолжить оплату» из истории тоже открывает сначала экран заказа.
- «Проверить оплату» сообщает, если подтверждение Robokassa ещё не получено. При ошибке запроса показывается ошибка; успешная проверка не имитируется.
- Не используются старые pending-счета Robokassa, если магазин, подпись, сумма, режим тестирования или реквизиты отличаются от текущих. Их история и статус в БД сохранены; деньги и подарки вручную не начисляются.
- Добавлен адрес возврата /pay/return: возвращает в Telegram-бот с кнопкой «Мои подарки». Возврат из браузера не подтверждает оплату.
- Новых зависимостей и миграций нет. Светлая и тёмная темы сохраняются.

## Почему Basic на 30 дней остался в ожидании

Письмо содержит inv_id=25, сумму 199.00. Это ранее созданный заказ, который интерфейс повторно предлагал при выборе такого же срока. Нельзя считать письмо подтверждением приёма webhook нашим сервером. Если старый счёт подписан для другого магазина/пароля, исправление пометит его как счёт со старыми реквизитами и позволит создать новый заказ Basic на 30 дней. История старого заказа остаётся; для его подтверждения требуется корректное уведомление и проверка реквизитов соответствующего магазина, а не автоматическое начисление по письму.

## 1. Распаковка и тесты на ноутбуке — PowerShell

Из корня проекта:

```powershell
$ErrorActionPreference = "Stop"
Expand-Archive -LiteralPath .\WorkPlayVPN-gifts-checkout-fix-2026-10-05.zip -DestinationPath . -Force
$backendSource = Join-Path (Get-Location).Path "backend"
$opsSource = Join-Path (Get-Location).Path "ops"
docker compose --profile testing run --rm --pull never --volume "${backendSource}:/app:ro" --volume "${opsSource}:/ops:ro" tests
if ($LASTEXITCODE -ne 0) { throw "Тесты backend не прошли" }
$botSource = Join-Path (Get-Location).Path "bot"
docker compose run --rm --no-deps --pull never --volume "${botSource}:/app:ro" --entrypoint python bot -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Тесты бота не прошли" }
git -c core.whitespace=cr-at-eol diff --check
if ($LASTEXITCODE -ne 0) { throw "Проверка изменений не прошла" }
```

Если образ tests отсутствует, потребуется сборка при доступном Docker Hub. Если установлен Node.js, отдельно можно выполнить `node ops/tests/test_gift_checkout_ui.cjs`.

## 2. Коммит после успешных тестов

```powershell
git add -- backend/app/api/gifts.py backend/app/api/payment_redirects.py backend/app/services/gift_checkout.py backend/tests/test_gift_checkout.py backend/tests/test_gifts.py bot/handlers/start.py bot/tests/test_gifts.py caddy/mini-app/assets/gifts.js caddy/mini-app/index.html ops/tests/test_gift_checkout_ui.cjs docs/gifts-checkout-fix-2026-10-05.md
if ($LASTEXITCODE -ne 0) { throw "Не удалось добавить файлы" }
git -c core.whitespace=cr-at-eol diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Проверка изменений не прошла" }
git diff --cached --stat
git commit -m "Fix gift checkout navigation and stale Robokassa invoices"
if ($LASTEXITCODE -ne 0) { throw "Коммит не создан; проверьте git log -1 и git status" }
git push origin main
if ($LASTEXITCODE -ne 0) { throw "Не удалось отправить коммит" }
```

Архивы, .env, test.db и другие посторонние файлы в коммит не добавлять.

## 3. Обновление основного сервера проекта

Это workplayvpn-core-fra-01, /opt/workplayvpn, а не VPN-нода в Нидерландах.

```bash
cd /opt/workplayvpn
set -e
git pull --ff-only origin main
docker compose build backend bot
docker compose up -d --no-deps --force-recreate backend bot payment-fulfillment-worker
docker compose ps
curl -sS --max-time 15 -D - -o /dev/null https://connect.workplayvpn.ru/pay/return
```

Последняя команда должна вернуть 302 и Location: https://t.me/workplayvpn_bot?start=payment_return. Не добавляйте curl -L: это проверка нашего адреса, без перехода в Telegram.

## 4. Настройки НОВОГО магазина Robokassa

После установки обновления задайте и сохраните:

| Поле | Значение | Метод |
|---|---|---|
| Result URL | https://connect.workplayvpn.ru/webhooks/robokassa | POST |
| Success URL | https://connect.workplayvpn.ru/pay/return | GET |
| Fail URL | https://connect.workplayvpn.ru/pay/return | GET |

Result URL подтверждает оплату. Success/Fail URL только возвращают пользователя в Telegram. На iOS открытие Telegram может потребовать системного подтверждения. Автоматическое открытие Mini App из Safari не обещается: бот предлагает кнопку «Мои подарки».

В тестовых настройках — MD5, тестовые пароли №1 и №2 нового магазина. В серверном .env сохраняется PAYMENT_MODE=test, ROBOKASSA_IS_TEST=true, ROBOKASSA_MERCHANT_LOGIN=workplayvpn_ip. Пароли из кабинета должны соответствовать серверным, их не нужно присылать в чат. Изменение только PAYMENT_SUCCESS_URL в .env не заменяет Success URL в кабинете: текущая интеграция Robokassa использует настройки магазина.

## 5. Ручная проверка

1. Полностью закройте и заново откройте Mini App.
2. Подарки → Купить подарок: видны Basic/Mobile с описаниями.
3. Basic → 30 дней → Купить подарок: открыт экран заказа, браузер не открывается.
4. Проверьте новый номер заказа вместо старого №25. Если №25 подписан старыми реквизитами, он останется в истории с соответствующей пометкой.
5. Перейти к оплате → Отмена: браузер не открывается. Повторите → подтвердите переход.
6. После тестовой оплаты «Вернуться в магазин» возвращает в Telegram. Нажмите кнопку «Мои подарки».
7. Должен появиться тестовый подарочный код. Повторное уведомление не выпускает второй подарок.
8. Проверьте Mobile, светлую и тёмную темы.

Если НОВЫЙ счёт остаётся pending после оплаты, снимите логи сразу после попытки:

```bash
cd /opt/workplayvpn
docker compose logs --since=10m --tail=200 backend
```

## Выполненная локальная проверка

33 backend-теста прошли; 1 проверка конкурентной активации на PostgreSQL пропущена в локальном SQLite-окружении. Проверены реальная генерация ссылки нового магазина и подписанный callback Basic на 30 дней, повтор callback, защита от старых реквизитов, сохранение истории и маршрут возврата. 5 тестов бота прошли. Node-проверка покрывает выбор подписки/срока, новый счёт вместо старого, отсутствие автоматического перехода, подтверждение/отмену и результат проверки оплаты. Проверка синтаксиса JS и git diff --check пройдены. Реальная Robokassa и переход между Safari/Telegram проверяются после установки.
