from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    # -------------------------------------------------
    # VPN
    # -------------------------------------------------

    vpn_node_name: str
    vpn_node_host: str
    vpn_node_ssh_port: int = 22
    vpn_node_ssh_user: str
    vpn_node_ssh_key_path: str = "/root/.ssh/workplayvpn_backend"

    vpn_reality_public_key: str
    vpn_reality_sni: str = "speed.cloudflare.com"
    vpn_reality_short_id: str
    vpn_reality_fingerprint: str = "chrome"
    vpn_reality_port: int = 443

    # -------------------------------------------------
    # Payments
    # -------------------------------------------------

    payment_default_provider: Literal[
        "test",
        "cloudpayments",
        "robokassa",
    ] = "test"

    payment_mode: Literal[
        "test",
        "live",
    ] = "test"

    payment_success_url: str | None = None
    payment_fail_url: str | None = None
    payment_webhook_base_url: str | None = None

    # -------------------------------------------------
    # CloudPayments
    # -------------------------------------------------

    cloudpayments_public_id: str | None = None
    cloudpayments_api_secret: str | None = None

    # -------------------------------------------------
    # Robokassa
    # -------------------------------------------------

    robokassa_merchant_login: str | None = None
    robokassa_password_1: str | None = None
    robokassa_password_2: str | None = None
    robokassa_hash_algorithm: str = "sha256"
    robokassa_is_test: bool = True

    # -------------------------------------------------
    # Telegram
    # -------------------------------------------------

    telegram_bot_token: str | None = None
    telegram_proxy_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    # -------------------------------------------------
    # Subscription tokens
    # -------------------------------------------------

    subscription_token_secret: str
    subscription_base_url: str = (
        "https://sub.workplayvpn.local/sub"
    )
    connect_base_url: str = (
        "https://connect.workplayvpn.local/connect/happ"
    )


settings = Settings()