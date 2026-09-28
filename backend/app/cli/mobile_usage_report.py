"""Join an NL node daily report with current device ownership, without writes.

Run only on the backend host/container. The input contains short opaque
credential hashes, never the Xray emails or UUIDs.
"""

import hashlib
import re
import sys
from datetime import date
from typing import Iterable, NamedTuple


class UsageRow(NamedTuple):
    day: str
    key_id: str
    uplink: int
    downlink: int


class DeviceKey(NamedTuple):
    id: int
    user_id: int
    mobile_xray_email: str | None
    public_id: str


def parse_daily_report(lines: Iterable[str]) -> list[UsageRow]:
    iterator = iter(lines)
    if next(iterator, "").strip() != "UTC_DATE MOBILE_KEY_ID UPLINK_BYTES DOWNLINK_BYTES":
        raise ValueError("Expected the --daily report header")
    rows = []
    seen = set()
    for line in iterator:
        parts = line.split()
        if len(parts) != 4:
            raise ValueError("Invalid daily report row")
        day, key_id, up, down = parts
        try:
            if date.fromisoformat(day).isoformat() != day:
                raise ValueError("Invalid day")
            if not re.fullmatch(r"[0-9a-f]{12}", key_id):
                raise ValueError("Invalid Mobile key ID")
            if not up.isascii() or not up.isdecimal() or not down.isascii() or not down.isdecimal():
                raise ValueError("Invalid byte count")
            row = UsageRow(day, key_id, int(up), int(down))
        except ValueError as exc:
            raise ValueError("Invalid daily report row") from exc
        if (day, key_id) in seen:
            raise ValueError("Duplicate Mobile key/day in report")
        seen.add((day, key_id))
        rows.append(row)
    return rows


def join_devices(rows: Iterable[UsageRow], devices: Iterable[DeviceKey]) -> list[tuple]:
    by_key = {}
    ambiguous = set()
    for device in devices:
        if not device.mobile_xray_email:
            continue
        key_id = hashlib.sha256(device.mobile_xray_email.encode()).hexdigest()[:12]
        if key_id in by_key:
            ambiguous.add(key_id)
        by_key[key_id] = device
    result = []
    for row in rows:
        device = by_key.get(row.key_id) if row.key_id not in ambiguous else None
        result.append((row.day, device.public_id if device else "UNMATCHED",
                       str(device.user_id) if device else "-", row.uplink, row.downlink))
    return result


def main() -> int:
    try:
        rows = parse_daily_report(sys.stdin)
    except ValueError as exc:
        print(f"Invalid input: {exc}", file=sys.stderr)
        return 2

    # Import the database only after input validation. No SQL writes occur.
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.vpn_device import VpnDevice

    with SessionLocal() as database:
        devices = [DeviceKey(*values) for values in database.execute(
            select(VpnDevice.id, VpnDevice.user_id, VpnDevice.mobile_xray_email,
                   VpnDevice.public_id)
        ).all()]
    print("UTC_DATE DEVICE USER_ID UPLINK_BYTES DOWNLINK_BYTES")
    for row in join_devices(rows, devices):
        print(*row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
