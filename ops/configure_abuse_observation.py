"""Enable observation in the private server override, preserving DB/TLS and bot token."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def configure(data, enabled):
    services = data.get("services", {})
    if "informer-worker" not in services:
        raise ValueError("Existing informer override required")
    environment = services["informer-worker"].setdefault("environment", {})
    if not isinstance(environment, dict):
        raise ValueError("Mapping environment required")
    environment["ANTIFRAUD_OBSERVE_ENABLED"] = "true" if enabled else "false"
    return data


def main():
    import yaml
    parser = argparse.ArgumentParser()
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args()
    path = Path("docker-compose.override.yml")
    original = path.read_text()
    data = yaml.safe_load(original)
    # Read effective configuration privately; never print secrets.
    resolved = json.loads(subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        check=True, capture_output=True, text=True).stdout)
    services = resolved["services"]
    backend_db = services["backend"].get("environment", {}).get("DATABASE_URL")
    informer_db = services["informer-worker"].get("environment", {}).get("DATABASE_URL")
    if not backend_db or informer_db != backend_db:
        raise ValueError("Informer must use the same DB as backend before enabling observation")
    updated = yaml.safe_dump(configure(data, not args.disable), allow_unicode=True, sort_keys=False)
    backup = path.with_name(path.name+".before-abuse-observation")
    if not backup.exists():
        descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(original)
    descriptor, temporary = tempfile.mkstemp(prefix=".compose-observation-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(updated)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print("Observation disabled" if args.disable else "Observation enabled; DB/TLS and informer token preserved")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit("Observation configuration failed: "+type(exc).__name__) from None
