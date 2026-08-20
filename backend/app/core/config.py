from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

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

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()