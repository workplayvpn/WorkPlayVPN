import json
import subprocess
import uuid
from urllib.parse import quote

from app.core.config import settings


class XrayNodeService:
    def __init__(self) -> None:
        self.host = settings.vpn_node_host
        self.port = settings.vpn_node_ssh_port
        self.user = settings.vpn_node_ssh_user
        self.key_path = settings.vpn_node_ssh_key_path

    def _run(self, command: str) -> str:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-i",
                self.key_path,
                "-p",
                str(self.port),
                f"{self.user}@{self.host}",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )

        return result.stdout.strip()

    def list_users(self) -> dict:
        output = self._run("list-users")
        return json.loads(output)

    def add_user(self, email: str) -> str:
        user_uuid = str(uuid.uuid4())

        self._run(
            f"add-user {user_uuid} {email}"
        )

        return user_uuid

    def remove_user(self, email: str) -> None:
        self._run(
            f"remove-user {email}"
        )

    def build_vless_url(
        self,
        user_uuid: str,
        node_name: str,
    ) -> str:
        params = (
            "encryption=none"
            "&flow=xtls-rprx-vision"
            "&security=reality"
            f"&sni={settings.vpn_reality_sni}"
            f"&fp={settings.vpn_reality_fingerprint}"
            f"&pbk={settings.vpn_reality_public_key}"
            f"&sid={settings.vpn_reality_short_id}"
            "&type=tcp"
            "&headerType=none"
        )

        profile_name = quote(
            node_name,
            safe="",
        )

        return (
            f"vless://{user_uuid}"
            f"@{self.host}:{settings.vpn_reality_port}"
            f"?{params}"
            f"#{profile_name}"
        )


xray_node_service = XrayNodeService()