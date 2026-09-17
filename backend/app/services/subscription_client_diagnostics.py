import hashlib
from collections.abc import Mapping


_SENSITIVE_HEADER_PARTS = (
    "authorization",
    "cookie",
    "token",
    "secret",
    "signature",
    "api-key",
    "apikey",
    "init-data",
)

_CLIENT_METADATA_HEADER_NAMES = {
    "user-agent",
    "sec-ch-ua",
    "sec-ch-ua-mobile",
    "sec-ch-ua-model",
    "sec-ch-ua-platform",
    "sec-ch-ua-platform-version",
    "x-app-version",
    "x-client-version",
    "x-device-model",
    "x-device-name",
    "x-device-os",
    "x-happ-device-model",
    "x-happ-device-name",
    "x-happ-os",
    "x-happ-os-version",
    "x-happ-platform",
    "x-operating-system",
    "x-os-name",
    "x-os-version",
    "x-platform",
    "x-platform-version",
}

_IDENTIFIER_HEADER_NAMES = {
    "device-id",
    "x-device-id",
    "x-client-id",
    "x-hwid",
    "hwid",
    "x-happ-device-id",
    "x-happ-hwid",
    "x-install-id",
    "x-installation-id",
}


def _is_sensitive_header(name: str) -> bool:
    return any(
        part in name.lower()
        for part in _SENSITIVE_HEADER_PARTS
    )


def _is_identifier_header(name: str) -> bool:
    normalized = name.lower()
    return (
        normalized in _IDENTIFIER_HEADER_NAMES
        or normalized.endswith("-device-id")
        or normalized.endswith("-installation-id")
        or normalized.endswith("-hwid")
    )


def _is_metadata_header(name: str) -> bool:
    normalized = name.lower()
    return (
        normalized in _CLIENT_METADATA_HEADER_NAMES
        or _is_identifier_header(normalized)
    )


def build_subscription_client_diagnostics(
    headers: Mapping[str, str],
) -> dict[str, object]:
    visible_header_names: list[str] = []
    metadata: dict[str, str] = {}
    identifier_hashes: dict[str, str] = {}

    for raw_name, raw_value in headers.items():
        name = raw_name.lower()

        if _is_sensitive_header(name):
            continue

        visible_header_names.append(name)

        if not _is_metadata_header(name):
            continue

        value = raw_value.strip()[:512]

        if not value:
            continue

        if _is_identifier_header(name):
            identifier_hashes[name] = hashlib.sha256(
                value.encode("utf-8")
            ).hexdigest()[:16]
            continue

        metadata[name] = value

    return {
        "header_names": sorted(set(visible_header_names)),
        "metadata": metadata,
        "identifier_hashes": identifier_hashes,
    }
