# WorkPlayVPN

Backend для сервиса WorkPlayVPN.

## Текущий статус

Реализован минимальный API на FastAPI:

- запуск в Docker;
- корневой endpoint для проверки состояния;
- автоматическая документация Swagger.

## Технологии

- Python 3.13
- FastAPI
- Uvicorn
- Docker Compose
- SQLAlchemy
- PostgreSQL / Psycopg
- Alembic

## Запуск

Убедитесь, что Docker запущен, затем выполните:

```bash
docker compose up --build