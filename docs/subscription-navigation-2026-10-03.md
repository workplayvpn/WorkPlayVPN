# Возвраты из подписки Basic/Mobile

Патч поверх d4b3f5b. Изменения только в боте.

Исправлено:
- «Добавить лимит устройств → Назад» возвращает в исходную Basic/Mobile.
- «Сменить регион → К подписке» возвращает в исходную Basic/Mobile.
- Контекст сохраняется после создания оплаты слотов, ошибки API, повторной
  загрузки регионов и успешной смены региона.
- Старые кнопки без указания подписки продолжают работать с прежним возвратом
  к списку подписок. Для проверки открыть карточку заново.
- На подтверждении тарифа уточнено количество включённых устройств и сохранение
  купленных дополнительных слотов.
- Смена региона по-прежнему применяется ко всем устройствам, лимит общий для
  Basic/Mobile. Контекст меняет только навигацию, а не область действия покупки.

Контекст в callback_data; не зависит от памяти процесса и переживает рестарт бота.
Telegram/API не вызываются в офлайн-тестах. Все 43 теста бота прошли локально
(12 новых проверок, Basic/Mobile, старые кнопки, ошибки, отсутствие оплаты при
показе подтверждения). diff --check пройден. Backend не изменён, миграций нет.

## PowerShell

```powershell
Expand-Archive .\WorkPlayVPN-subscription-navigation-2026-10-03.zip -DestinationPath . -Force -ErrorAction Stop
$botSource = Join-Path (Get-Location).Path "bot"
docker compose run --rm --no-deps --pull never --volume "${botSource}:/app:ro" --entrypoint python bot -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Тесты бота не прошли" }
git -c core.whitespace=cr-at-eol diff --check
if ($LASTEXITCODE -ne 0) { throw "Проверка изменений не прошла" }
```

После проверки добавить только файлы патча, создать коммит и push.

## Сервер

```bash
cd /opt/workplayvpn
git pull --ff-only &&
docker compose build bot &&
docker compose up -d --no-deps bot
docker compose ps bot
docker compose logs --since=2m --tail=30 bot
```

Вручную открыть «Мои подписки → Basic» и проверить оба возврата. Повторить для
Mobile. Для теста возврата достаточно открыть экран регионов, менять регион
не нужно. Оплату слотов для этой проверки выполнять не нужно.
