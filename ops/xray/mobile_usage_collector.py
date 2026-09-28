"""Poll local Xray counters and persist Mobile usage in a private SQLite file.

Run once per minute via a systemd timer. This is operational telemetry, not an
enforcement counter or a substitute for the CDN provider's billing figures.
"""

import argparse
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess


XRAY = "/usr/local/bin/xray"
API = "127.0.0.1:10086"
SERVICE = "xray-yandex-cdn-test.service"
DEFAULT_DATABASE = Path("/var/lib/workplayvpn/mobile-usage.sqlite")


def parse_counters(payload: dict) -> dict[str, int]:
    result = {}
    for stat in payload.get("stat", []):
        name = stat["name"]
        parts = name.split(">>>")
        if (
            len(parts) != 4
            or parts[0] != "user"
            or not parts[1].startswith("mobile_")
            or not parts[1].endswith("@workplayvpn")
            or parts[2] != "traffic"
            or parts[3] not in ("uplink", "downlink")
        ):
            continue
        value = int(stat["value"])
        if value < 0:
            raise ValueError("Negative Xray counter")
        result[name] = value
    return result


def record_snapshot(connection: sqlite3.Connection, pid: int,
                    counters: dict[str, int], *, at: datetime | None = None) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS counters (
        name TEXT PRIMARY KEY, pid INTEGER NOT NULL,
        last_value INTEGER NOT NULL, total INTEGER NOT NULL,
        last_seen TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS daily_counters (
        day TEXT NOT NULL, name TEXT NOT NULL, total INTEGER NOT NULL,
        PRIMARY KEY (day, name))""")
    moment = (at or datetime.now(UTC)).astimezone(UTC)
    now = moment.isoformat()
    with connection:
        for name, value in counters.items():
            previous = connection.execute(
                "SELECT pid, last_value FROM counters WHERE name = ?", (name,)
            ).fetchone()
            increment = (value - previous[1]) if (
                previous and previous[0] == pid and value >= previous[1]
            ) else value
            connection.execute("""INSERT INTO counters
                (name, pid, last_value, total, last_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                pid=excluded.pid, last_value=excluded.last_value,
                total=counters.total + excluded.total,
                last_seen=excluded.last_seen""",
                (name, pid, value, increment, now),
            )
            if increment:
                connection.execute("""INSERT INTO daily_counters (day, name, total)
                    VALUES (?, ?, ?) ON CONFLICT(day, name) DO UPDATE SET
                    total=daily_counters.total + excluded.total""",
                    (moment.date().isoformat(), name, increment),
                )


def daily_report(connection: sqlite3.Connection, *, days: int = 7,
                 as_of: date | None = None) -> list[tuple]:
    """Return UTC day, pseudonymous client ID and counted upload/download bytes."""
    if days < 1:
        raise ValueError("days must be positive")
    today = as_of or datetime.now(UTC).date()
    rows = connection.execute("""SELECT day, name, total FROM daily_counters
        WHERE day BETWEEN ? AND ?
        ORDER BY day DESC, name""",
        ((today - timedelta(days=days - 1)).isoformat(), today.isoformat()))
    grouped = {}
    for day, name, value in rows:
        # Never print an Xray email or credential in a CLI report.
        opaque_id = hashlib.sha256(name.split(">>>", 3)[1].encode()).hexdigest()[:12]
        key = (day, opaque_id)
        entry = grouped.setdefault(key, [0, 0])
        entry[0 if name.endswith(">>>uplink") else 1] += value
    return [(day, opaque_id, *values)
            for (day, opaque_id), values in sorted(grouped.items(), reverse=True)]


def query_xray() -> tuple[int, dict[str, int]]:
    pid_output = subprocess.run(
        ["systemctl", "show", "-p", "MainPID", "--value", SERVICE],
        text=True, capture_output=True, check=True, timeout=5,
    ).stdout.strip()
    pid = int(pid_output)
    if pid <= 0:
        raise RuntimeError("Mobile Xray service is not running")
    output = subprocess.run(
        [XRAY, "api", "statsquery", f"--server={API}", "-pattern", "user>>>"],
        text=True, capture_output=True, check=True, timeout=10,
    ).stdout
    return pid, parse_counters(json.loads(output))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--daily", action="store_true",
                        help="Show the last seven UTC days, split by anonymous Mobile key")
    args = parser.parse_args()
    if not args.database.parent.is_dir():
        parser.error("Database parent directory missing")
    previous_umask = os.umask(0o077)
    try:
        connection = sqlite3.connect(args.database, timeout=10)
    finally:
        os.umask(previous_umask)
    try:
        pid, counters = query_xray()
        record_snapshot(connection, pid, counters)
        if args.report:
            uplink, downlink = 0, 0
            for name, total in connection.execute("SELECT name, total FROM counters"):
                if name.endswith(">>>uplink"):
                    uplink += total
                else:
                    downlink += total
            print(f"MOBILE_UPLINK_BYTES={uplink}")
            print(f"MOBILE_DOWNLINK_BYTES={downlink}")
            print(f"MOBILE_COUNTERS={len(counters)}")
        if args.daily:
            print("UTC_DATE MOBILE_KEY_ID UPLINK_BYTES DOWNLINK_BYTES")
            for day, opaque_id, uplink, downlink in daily_report(connection):
                print(day, opaque_id, uplink, downlink)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
