import hashlib

import pytest

from app.cli.mobile_usage_report import DeviceKey, join_devices, parse_daily_report


def test_daily_report_matches_only_the_current_mobile_credential():
    email_a = "mobile_first@workplayvpn"
    email_b = "mobile_second@workplayvpn"
    key_a = hashlib.sha256(email_a.encode()).hexdigest()[:12]
    key_b = hashlib.sha256(email_b.encode()).hexdigest()[:12]
    report = [
        "UTC_DATE MOBILE_KEY_ID UPLINK_BYTES DOWNLINK_BYTES\n",
        f"2026-09-28 {key_a} 123 456\n",
        f"2026-09-28 {key_b} 0 777\n",
        "2026-09-27 000000000000 10 20\n",
    ]
    devices = [DeviceKey(21, 174, email_a), DeviceKey(22, 174, email_b)]
    assert join_devices(parse_daily_report(report), devices) == [
        ("2026-09-28", "WP-000021", "174", 123, 456),
        ("2026-09-28", "WP-000022", "174", 0, 777),
        ("2026-09-27", "UNMATCHED", "-", 10, 20),
    ]


def test_invalid_or_duplicated_report_is_rejected_before_database_access():
    header = "UTC_DATE MOBILE_KEY_ID UPLINK_BYTES DOWNLINK_BYTES\n"
    valid = "2026-09-28 123456789abc 1 2\n"
    for content in (
        "wrong header\n",
        header + valid + valid,
        header + "2026-02-30 123456789abc 1 2\n",
        header + "2026-09-28 123456789abc -1 2\n",
        header + "2026-09-28 mobile_a@workplayvpn 1 2\n",
    ):
        with pytest.raises(ValueError):
            parse_daily_report(content.splitlines(keepends=True))
