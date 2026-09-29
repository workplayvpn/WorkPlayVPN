from types import SimpleNamespace

from app.services.happ_device_metadata import (
    hwid_digest, record_happ_device_metadata,
)


class Database:
    commits = 0

    def commit(self):
        self.commits += 1


def device():
    return SimpleNamespace(happ_device_model=None, happ_device_os=None,
                           happ_hwid_digest=None)


def test_per_device_happ_request_saves_model_and_os_without_raw_hwid():
    db = Database()
    one, two = device(), device()
    headers = {"user-agent": "Happ/5.9.0/ios", "x-device-model": "iPhone 14 Pro Max",
               "x-device-os": "iOS", "x-ver-os": "26.0", "x-hwid": "private-hwid"}
    record_happ_device_metadata(db, [one, two], headers, selected_device=two)
    assert db.commits == 1
    assert one.happ_device_model is None
    assert two.happ_device_model == "iPhone 14 Pro Max"
    assert two.happ_device_os == "iOS 26.0"
    assert two.happ_hwid_digest == hwid_digest("private-hwid")
    assert "private-hwid" not in vars(two).values()
    record_happ_device_metadata(db, [one, two], headers, selected_device=two)
    assert db.commits == 1


def test_shared_link_updates_only_unambiguous_device():
    db = Database()
    one, two = device(), device()
    headers = {"user-agent": "Happ/5.9.0/ios", "x-device-model": "iPad Pro",
               "x-device-os": "iPadOS", "x-hwid": "second-hwid"}
    record_happ_device_metadata(db, [one, two], headers)
    assert db.commits == 0
    two.happ_hwid_digest = hwid_digest("second-hwid")
    record_happ_device_metadata(db, [one, two], headers)
    assert db.commits == 1
    assert two.happ_device_model == "iPad Pro"
    assert one.happ_device_model is None


def test_non_happ_and_invalid_values_are_ignored():
    db = Database()
    one = device()
    for headers in (
        {"user-agent": "Browser", "x-device-model": "iPhone", "x-device-os": "iOS"},
        {"user-agent": "Happ/5.9", "x-device-model": "iPhone"},
        {"user-agent": "Happ/5.9", "x-device-model": "x" * 101,
         "x-device-os": "iOS"},
    ):
        record_happ_device_metadata(db, [one], headers)
    assert db.commits == 0
