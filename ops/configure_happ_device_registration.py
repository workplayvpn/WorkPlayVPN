"""Enable HWID registration in backend only; preserve server DB/TLS settings."""
import argparse
import os
from pathlib import Path
import tempfile


def configure(data, enabled=True):
    if not isinstance(data, dict):
        raise ValueError("Compose mapping required")
    services = data.setdefault("services", {})
    backend = services.setdefault("backend", {})
    environment = backend.setdefault("environment", {})
    if isinstance(environment, list):
        environment = dict(item.split("=", 1) if "=" in item else (item, None)
                           for item in environment)
        backend["environment"] = environment
    if not isinstance(environment, dict):
        raise ValueError("Unexpected backend environment format")
    environment["HAPP_ACCOUNT_DEVICE_REGISTRATION_ENABLED"] = "true" if enabled else "false"
    return data


def main():
    import yaml
    parser = argparse.ArgumentParser()
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args()
    path = Path("docker-compose.override.yml")
    original = path.read_text() if path.exists() else "services: {}\n"
    updated = yaml.safe_dump(configure(yaml.safe_load(original), not args.disable),
                             allow_unicode=True, sort_keys=False)
    backup = path.with_name(path.name + ".before-happ-device-registration")
    if path.exists() and not backup.exists():
        descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(original)
    descriptor, temporary = tempfile.mkstemp(prefix=".compose-hwid-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(updated)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print("Happ account device registration " + ("disabled" if args.disable else "enabled")
          + "; existing database, TLS and tokens preserved")


if __name__ == "__main__":
    main()
