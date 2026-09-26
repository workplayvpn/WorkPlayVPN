from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.models.vpn_node_profile import VpnNodeProfile
from app.services.vpn_profile_link_builder import (
    vpn_profile_link_builder,
)

from .base import ClientProfile


class HappProfile(ClientProfile):

    ACCESS_MODE_KEY = "happ_access_mode"
    SERVER_ADDRESS_KEY = "happ_server_address"
    DISPLAY_NAME_KEY = "happ_display_name"

    @classmethod
    def _access_mode(
        cls,
        profile: VpnNodeProfile,
    ) -> str | None:
        settings = profile.settings or {}
        access_mode = settings.get(
            cls.ACCESS_MODE_KEY
        )

        if not isinstance(access_mode, str):
            return None

        normalized = access_mode.strip().lower()

        if normalized not in {"wifi", "mobile"}:
            return None

        return normalized

    @classmethod
    def _is_mobile_profile_ready(
        cls,
        profile: VpnNodeProfile,
    ) -> bool:
        if profile.protocol != "vless":
            return False

        if cls._access_mode(profile) != "mobile":
            return False

        if profile.security != "tls":
            return False

        if profile.network not in {"xhttp", "ws"}:
            return False

        if (
            not isinstance(profile.port, int)
            or not 1 <= profile.port <= 65535
        ):
            return False

        settings = profile.settings or {}

        server_address = settings.get(
            cls.SERVER_ADDRESS_KEY
        )

        if not isinstance(server_address, str):
            return False

        server_address = server_address.strip()

        if not server_address:
            return False

        if "://" in server_address:
            return False

        if "/" in server_address:
            return False

        if any(
            character.isspace()
            for character in server_address
        ):
            return False

        path = settings.get("path")

        if not isinstance(path, str):
            return False

        path = path.strip()

        if not path.startswith("/"):
            return False

        return True

    @classmethod
    def _build_link(
        cls,
        *,
        device: VpnDevice,
        node: VpnNode,
        profile: VpnNodeProfile,
        access_mode: str | None,
        label_access_mode: bool = True,
        credential_uuid: str | None = None,
    ) -> str:
        settings = profile.settings or {}

        server_address = settings.get(
            cls.SERVER_ADDRESS_KEY
        )

        if not isinstance(server_address, str):
            server_address = None
        elif not server_address.strip():
            server_address = None
        else:
            server_address = server_address.strip()

        display_name = settings.get(
            cls.DISPLAY_NAME_KEY
        )

        if not isinstance(display_name, str):
            display_name = None
        elif not display_name.strip():
            display_name = None
        else:
            display_name = display_name.strip()

        if not label_access_mode:
            # Basic uses the same country name as the Mobile Wi-Fi profile,
            # without suggesting that it includes a separate Mobile route.
            display_name = (
                display_name.removesuffix(" — Wi-Fi")
                if display_name is not None
                else node.name
            )
        elif display_name is None and access_mode is not None:
            suffix = (
                "Wi-Fi"
                if access_mode == "wifi"
                else "Mobile"
            )
            display_name = f"{node.name} — {suffix}"

        return vpn_profile_link_builder.build_vless_link(
            device=device,
            node=node,
            profile=profile,
            server_address=server_address,
            display_name=display_name,
            credential_uuid=credential_uuid,
        )

    def build_links(
        self,
        device: VpnDevice,
        nodes: list[VpnNode],
        profiles: list[VpnNodeProfile],
        include_happ_mobile: bool = False,
    ) -> list[str]:
        links: list[str] = []

        profiles_by_node: dict[
            int,
            list[VpnNodeProfile],
        ] = {}

        for profile in profiles:
            if not profile.is_active:
                continue

            profiles_by_node.setdefault(
                profile.node_id,
                [],
            ).append(profile)

        for node in nodes:
            node_profiles = profiles_by_node.get(
                node.id,
                [],
            )

            wifi_profile = next(
                (
                    profile
                    for profile in node_profiles
                    if profile.protocol == "vless"
                    and profile.network == "tcp"
                    and profile.security == "reality"
                    and self._access_mode(profile) != "mobile"
                ),
                None,
            )

            if wifi_profile is None:
                wifi_profile = next(
                    (
                        profile
                        for profile in node_profiles
                        if profile.protocol == "vless"
                        and self._access_mode(profile) == "wifi"
                    ),
                    None,
                )

            wifi_access_mode: str | None = (
                "wifi" if wifi_profile is not None
                and self._access_mode(wifi_profile) == "wifi"
                else None
            )

            if wifi_profile is None:
                wifi_profile = next(
                    (
                        profile
                        for profile in node_profiles
                        if profile.protocol == "vless"
                        and profile.network == "xhttp"
                        and profile.security == "tls"
                        and self._access_mode(profile) is None
                    ),
                    None,
                )
                wifi_access_mode = None

            if wifi_profile is None:
                continue

            links.append(
                self._build_link(
                    device=device,
                    node=node,
                    profile=wifi_profile,
                    access_mode=wifi_access_mode,
                    label_access_mode=include_happ_mobile,
                )
            )

            if not include_happ_mobile:
                continue

            mobile_profile = next(
                (
                    profile
                    for profile in node_profiles
                    if self._is_mobile_profile_ready(profile)
                ),
                None,
            )

            if mobile_profile is None:
                continue

            links.append(
                self._build_link(
                    device=device,
                    node=node,
                    profile=mobile_profile,
                    access_mode="mobile",
                    credential_uuid=device.mobile_xray_uuid,
                )
            )

        return links
