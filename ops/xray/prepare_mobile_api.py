"""Prepare a candidate Xray config with a loopback-only CDN management API.

This command never edits the running config or restarts Xray. The output
contains the original client credentials, so keep it private.
"""

import argparse
import json
import os
from pathlib import Path


API_TAG = "workplayvpn-mobile-api"
API_LISTEN = "127.0.0.1:10086"


def with_mobile_api(config: dict) -> dict:
    if "api" in config:
        raise ValueError("Config already has an API; inspect it manually")

    inbounds = config.get("inbounds")
    if not isinstance(inbounds, list) or not inbounds:
        raise ValueError("Expected at least one inbound")

    if any(inbound.get("tag") == API_TAG for inbound in inbounds):
        raise ValueError("Reserved API tag is already used")

    if any(inbound.get("port") == 10086 for inbound in inbounds):
        raise ValueError("Reserved API port is already used")

    outbounds = config.get("outbounds", [])
    if any(outbound.get("tag") == API_TAG for outbound in outbounds):
        raise ValueError("Reserved API tag is already used")

    result = dict(config)
    # Xray 1.8.12+ supports this API form without an extra inbound or
    # routing rule. It listens only on the loopback interface.
    result["api"] = {
        "tag": API_TAG,
        "listen": API_LISTEN,
        "services": ["HandlerService"],
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()

    if args.source.resolve() == args.candidate.resolve():
        parser.error("Source and candidate must be different paths")

    with args.source.open(encoding="utf-8") as source:
        config = json.load(source)
    candidate = with_mobile_api(config)

    # Exclusive creation avoids overwriting another deployment candidate.
    descriptor = os.open(
        args.candidate,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(candidate, output, ensure_ascii=False, indent=2)
        output.write("\n")

    print(f"Candidate prepared: {args.candidate}")
    print(f"API listen: {API_LISTEN}")
    print("The running service and original config were not changed")


if __name__ == "__main__":
    main()
