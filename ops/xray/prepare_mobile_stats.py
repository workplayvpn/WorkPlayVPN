"""Write a separate Xray candidate enabling per-user Mobile traffic counters.

The source and running service are never modified by this command.
"""

import argparse
import copy
import json
import os
from pathlib import Path


def with_mobile_stats(config: dict) -> dict:
    result = copy.deepcopy(config)
    api = result.get("api")
    if not isinstance(api, dict) or api.get("listen") != "127.0.0.1:10086":
        raise ValueError("Expected the existing loopback-only Mobile API")

    services = api.get("services")
    if not isinstance(services, list) or "HandlerService" not in services:
        raise ValueError("Expected the existing Mobile HandlerService")
    if "StatsService" not in services:
        services.append("StatsService")

    if "stats" in result and not isinstance(result["stats"], dict):
        raise ValueError("Existing stats settings are invalid")
    result.setdefault("stats", {})

    policy = result.setdefault("policy", {})
    if not isinstance(policy, dict):
        raise ValueError("Existing policy settings are invalid")
    levels = policy.setdefault("levels", {})
    if not isinstance(levels, dict):
        raise ValueError("Existing policy levels are invalid")
    default = levels.setdefault("0", {})
    if not isinstance(default, dict):
        raise ValueError("Existing policy level 0 is invalid")
    default["statsUserUplink"] = True
    default["statsUserDownlink"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.candidate.resolve():
        parser.error("Source and candidate must differ")
    with args.source.open(encoding="utf-8") as source:
        candidate = with_mobile_stats(json.load(source))
    fd = os.open(args.candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(candidate, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print("Mobile stats candidate ready; running service unchanged")


if __name__ == "__main__":
    main()
