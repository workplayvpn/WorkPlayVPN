import os


telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]

backend_url = os.getenv(
    "BACKEND_URL",
    "http://backend:8000",
)