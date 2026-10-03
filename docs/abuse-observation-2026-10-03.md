# Work&PlayVPN: наблюдение за злоупотреблениями

Патч поверх b150ca0 (исправленный личный информатор). Он добавляет предупреждения
в @WorkPlayVPNInformerBot только владельцу INFORMER_OWNER_TELEGRAM_ID.
Никаких автоматических блокировок, списаний, смены ключей или урезания подписок.

## Сигналы первой версии

| Правило | Условие |
|---|---|
| payment_burst | 8 и более созданных платежей за 10 минут |
| activation_burst | 10 и более созданных ссылок активации за 10 минут |
| support_burst | 5 и более созданных обращений за 10 минут |
| duplicate_trial | Более одного выданного триала одному аккаунту, последний создан за 10 минут |

Проверка раз в минуту; повтор одного правила для одного пользователя — не чаще
раза в час. Пороги предварительные и требуют оценки на реальной активности.
Тестовые и реальные сохранённые события учитываются одинаково.

Ссылки активации — не количество подключённых VPN-устройств. Созданные платежи —
не неуспешные попытки банковской оплаты. Отклонённые HTTP-запросы и отказы в повторном
триале не сохраняются текущим проектом и здесь не подсчитываются. Защита от повторной
выдачи триала одному профилю уже существует и сохраняется.
Связать несколько Telegram-аккаунтов одного человека по этим данным нельзя.
Эта версия — наблюдение, а не полноценная антифрод-система.

Сообщение содержит Telegram ID, @username, ссылку на профиль, причину и время.
Индивидуальный ключ в предупреждения не добавляется. Доставка предупреждений имеет
свою очередь PostgreSQL, не подменяет очередь покупок. Ошибка наблюдения не мешает
попытке отправить покупку. Внешние сбои Telegram могут задерживать оба вида отправки.

При ошибке сохранения после принятия сообщения Telegram работает защита от повтора
в текущем процессе. После аварийного перезапуска остаётся редкая возможность повтора,
поскольку Telegram sendMessage не поддерживает идемпотентность.

## Проверки в PowerShell

Сохранить ZIP в корень проекта и выполнить:

```powershell
Expand-Archive .\WorkPlayVPN-abuse-observation-2026-10-03.zip -DestinationPath . -Force -ErrorAction Stop
$backendSource = Join-Path (Get-Location).Path "backend"
$opsSource = Join-Path (Get-Location).Path "ops"
docker compose --profile testing run --rm --pull never --volume "${backendSource}:/app:ro" --volume "${opsSource}:/ops:ro" tests
if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }
git -c core.whitespace=cr-at-eol diff --check
if ($LASTEXITCODE -ne 0) { throw "Diff check failed" }
```

Используется уже собранный образ tests с зависимостями и новая исходная папка.
Тестовый Compose очищает только workplayvpn_test. Не заменять его production URL.
После тестов добавить только файлы ZIP, проверить diff, создать коммит и push.

## Сервер после коммита

Используется существующий informer-worker; отдельный бот/токен/контейнер не нужны.
Настройки Timeweb и TLS из исправленного docker-compose.override.yml сохраняются.
Скрипт включения дополнительно проверяет совпадение эффективной DATABASE_URL
backend и informer-worker без вывода паролей.

```bash
cd /opt/workplayvpn
git pull --ff-only &&
docker compose build backend informer-worker &&
docker compose run --rm --no-deps backend alembic upgrade head &&
python3 ops/configure_abuse_observation.py &&
docker compose config --quiet &&
docker compose up -d --no-deps backend informer-worker
```

При ошибке остановиться. Миграция f260ab91d803 создаёт только abuse_alerts.
Наблюдение по умолчанию отключено; скрипт включает его в приватном override.
Не запускать configure_informer_compose.py повторно ради этого патча.
Не коммитить серверные override, .env и их резервные копии.

Проверки:

```bash
docker compose ps backend informer-worker
docker compose logs --since=2m --tail=40 informer-worker
docker compose exec -T informer-worker python - <<'PY'
from sqlalchemy import text
from app.core.config import settings
from app.db.session import engine
print("Observation enabled:", settings.antifraud_observe_enabled)
print("Host:", engine.url.host)
with engine.connect() as connection:
    print("Migration:", connection.scalar(text("SELECT version_num FROM alembic_version")))
    print("Alerts table:", connection.scalar(text("SELECT to_regclass('public.abuse_alerts')")))
PY
```

Не создавать реальные оплаты/лишние устройства для имитации злоупотреблений.
Обычная покупка должна по-прежнему присылать одно уведомление.
При включении рассматривается только недавняя активность (10 минут), а не вся история.

Отключить только наблюдение, сохранив информатор покупок:

```bash
python3 ops/configure_abuse_observation.py --disable &&
docker compose up -d --no-deps informer-worker
```

Очередь предупреждений остаётся в БД. После повторного включения накопленные
неотправленные предупреждения будут отправлены.

## Проверено при подготовке

37 локальных тестов информатора и наблюдения, включая отдельный процесс,
отсутствие повторной отправки после сбоя commit, пороги, cooldown, rollback,
сохранение настроек DB/TLS/токена и отключение наблюдения.
22 новых теста. Одна Alembic head f260ab91d803; diff --check.
Полный PostgreSQL suite и реальная доставка новой очереди на сервере ещё не проверены.
