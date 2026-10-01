import os


telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
internal_api_secret = os.environ["INTERNAL_API_SECRET"]

backend_url = os.getenv(
    "BACKEND_URL",
    "http://backend:8000",
)

telegram_proxy_url = os.getenv(
    "TELEGRAM_PROXY_URL",
)

mini_app_url = os.getenv(
    "MINI_APP_URL",
    "https://connect.workplayvpn.ru/app/",
)

mini_app_referrals_url = (
    f"{mini_app_url}{'&' if '?' in mini_app_url else '?'}view=referrals"
)

mini_app_devices_url = (
    f"{mini_app_url}"
    f"{'&' if '?' in mini_app_url else '?'}view=devices"
)
