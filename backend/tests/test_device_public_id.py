import re

from app.models.vpn_device import new_device_public_id


def test_device_ids_are_opaque_and_unique():
    ids = [new_device_public_id() for _ in range(100)]
    assert len(set(ids)) == len(ids)
    assert all(re.fullmatch(r"WP-[A-F0-9]{16}", item) for item in ids)
