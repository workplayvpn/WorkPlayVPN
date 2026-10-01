# Work&PlayVPN: публичный Mobile и оформление Telegram

База: fbb7a55. Миграции не нужны. Пустые настройки по-прежнему отключают функцию, отдельные ID включают пилот, * включает для всех. Покупка и каталог используют общую проверку. Ссылки и конфигурации продолжают проверять активную подписку соответствующего тарифа, владельца и активность устройства.

Поддержка * унифицирована для MOBILE_PILOT_USER_IDS, HAPP_AUTO_ROUTE_USER_IDS, HAPP_SMART_ROUTING_USER_IDS, HAPP_MOBILE_NETWORK_HINT_USER_IDS, HAPP_HIDDEN_SETTINGS_USER_IDS и HAPP_CRYPT5_USER_IDS. HAPP_MOBILE_PROFILE_USER_IDS больше не управляет выдачей Mobile: она определяется entitlement.

## Тексты

Короткое описание (119 символов):

Work&PlayVPN • Для работы и отдыха. Basic и Mobile, до 3 устройств, подключение через Happ. Поддержка: @workplayvpnteam

Описание первого входа (482 символа):

Твой мир на связи — с Work&PlayVPN.

💻 Работа, игры, видео и общение — на телефоне, планшете и компьютере.

🔹 Basic — для повседневных задач.
🔸 Mobile — Wi-Fi и мобильная сеть с резервным маршрутом.

📱 До 3 устройств, общий лимит для двух подписок.
🔑 Подключение через Happ: инструкция, ссылка или QR-код.
🌍 Смена доступного региона в Mini App.
💳 Независимые сроки Basic и Mobile, продление без автосписаний.

Открой приложение и выбери своё подключение.
Поддержка: @workplayvpnteam

Тексты задаются ботом при старте из texts/description.py. Если менять их вручную через BotFather, следующая перезагрузка вернёт значения из кода.

## Фотографии

Новые файлы включены в предыдущий релиз fbb7a55 и повторно приложены к архиву для удобства:

- bot/assets/avatar.png — аватар: BotFather → /setuserpic → workplayvpn_bot → отправить фотографию.
- bot/assets/description.png — первый вход: BotFather → /mybots → workplayvpn_bot → Edit Bot → Edit Description Picture → отправить фотографию 640×360.

Файлы не заменяются на стороне Telegram при пересборке контейнера. Приветствие после /start уже использует новую обложку из предыдущего релиза.

## Локальные проверки

```powershell
docker compose --profile testing run --rm tests
if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }
docker compose run --build --rm --no-deps --entrypoint python bot -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Bot tests failed" }
git -c core.whitespace=cr-at-eol diff --check
```

Локально в рабочем окружении проверено: 14 тестов бота, 12 тестов wildcard/пилотного доступа, сохранение остальных параметров .env. PostgreSQL suite требуется запустить перед коммитом.

## Включение на сервере после обновления кода

Сначала git pull --ff-only и сборка/запуск backend и bot, чтобы новые методы проверки * и тексты были установлены.

Затем из /opt/workplayvpn:

```bash
python3 ops/enable_public_mobile.py --apply &&
docker compose up -d --no-deps --wait --force-recreate backend
```

Скрипт сначала проверяет internal/happ/mobile-readiness, наличие provider ID и доступность сервиса crypt5 по безопасной тестовой ссылке без пользовательского токена. При неуспехе .env не изменяется. Затем создаётся .env.before-public-mobile-<UTC timestamp> с правами 0600, а перечисленные настройки получают *. Тарифы, цены, сроки, платёжный режим и секреты сохраняются.

Готовность конфигурации не измеряет пропускную способность CDN/ноды и фактическую скорость у пользователей. Это включение доступности тарифа, а не выдача бесплатного Mobile существующим клиентам. Проверить каталог вторым Telegram-аккаунтом и работу оплаченной Mobile-подписки на Wi-Fi/LTE.

Откат: восстановить созданную копию .env и пересоздать backend. Действующие оплаченные подписки не удаляются откатом настроек каталога.
