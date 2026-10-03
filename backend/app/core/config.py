from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    # -------------------------------------------------
    # Internal API security
    # -------------------------------------------------

    internal_api_secret: str = Field(min_length=32)

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
    payment_redirect_base_url: str = (
        "https://connect.workplayvpn.ru/pay"
    )

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
    informer_bot_token: str | None = None
    informer_owner_telegram_id: int = 2027613435
    antifraud_observe_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    # -------------------------------------------------
    # Subscription tokens
    # -------------------------------------------------

    subscription_token_secret: str
    subscription_base_url: str = (
        "https://connect.workplayvpn.ru/sub"
    )
    connect_base_url: str = (
        "https://connect.workplayvpn.ru/connect/happ"
    )
    activation_base_url: str = (
        "https://connect.workplayvpn.ru/activate"
    )
    subscription_client_diagnostics: bool = False
    happ_mobile_profile_user_ids: str = ""
    happ_smart_routing_user_ids: str = ""
    mobile_pilot_user_ids: str = ""
    happ_mobile_network_hint_user_ids: str = ""
    happ_auto_route_user_ids: str = ""
    happ_provider_id: str = ""
    happ_hidden_settings_user_ids: str = ""
    happ_crypt5_user_ids: str = ""


settings = Settings()
