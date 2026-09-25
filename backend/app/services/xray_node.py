import json
import subprocess
import uuid

from app.core.config import settings
from app.models.vpn_node import VpnNode
from app.models.vpn_device import VpnDevice


class XrayNodeService:
    def __init__(self) -> None:
        self.key_path = settings.vpn_node_ssh_key_path

    def _run(
        self,
        node: VpnNode,
        command: str,
    ) -> str:
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
                str(node.ssh_port),
                f"{node.ssh_user}@{node.host}",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )

        return result.stdout.strip()

    def list_users(
        self,
        node: VpnNode,
    ) -> dict:
        output = self._run(
            node=node,
            command="list-users",
        )

        return json.loads(output)

    def add_user(
        self,
        node: VpnNode,
        email: str,
        user_uuid: str | None = None,
    ) -> str:
        if user_uuid is None:
            user_uuid = str(uuid.uuid4())

        self._run(
            node=node,
            command=f"add-user {user_uuid} {email}",
        )

        return user_uuid

    def remove_user(
        self,
        node: VpnNode,
        email: str,
    ) -> None:
        self._run(
            node=node,
            command=f"remove-user {email}",
        )

    def add_mobile_user(
        self,
        node: VpnNode,
        email: str,
        user_uuid: str,
    ) -> None:
        self._run(
            node=node,
            command=f"add-mobile-user {user_uuid} {email}",
        )

    def remove_mobile_user(
        self,
        node: VpnNode,
        email: str,
    ) -> None:
        self._run(
            node=node,
            command=f"remove-mobile-user {email}",
        )

    def add_device(self, node: VpnNode, device: VpnDevice) -> None:
        self.add_user(node=node, email=device.xray_email, user_uuid=device.xray_uuid)
        if device.mobile_xray_uuid and device.mobile_xray_email:
            try:
                self.add_mobile_user(
                    node=node,
                    email=device.mobile_xray_email,
                    user_uuid=device.mobile_xray_uuid,
                )
            except Exception:
                try:
                    self.remove_user(node=node, email=device.xray_email)
                except Exception:
                    pass
                raise

    def remove_device(self, node: VpnNode, device: VpnDevice) -> None:
        if device.mobile_xray_email:
            self.remove_mobile_user(node=node, email=device.mobile_xray_email)
        try:
            self.remove_user(node=node, email=device.xray_email)
        except Exception:
            if device.mobile_xray_uuid and device.mobile_xray_email:
                try:
                    self.add_mobile_user(
                        node=node,
                        email=device.mobile_xray_email,
                        user_uuid=device.mobile_xray_uuid,
                    )
                except Exception:
                    pass
            raise


xray_node_service = XrayNodeService()
