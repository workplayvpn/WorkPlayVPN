"""Store separate CDN credentials per device.

Revision ID: f52c1bc88931
Revises: a74eaf519c32
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f52c1bc88931"
down_revision: Union[str, Sequence[str], None] = "a74eaf519c32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("vpn_devices", sa.Column("mobile_xray_uuid", sa.String(36), nullable=True))
    op.add_column("vpn_devices", sa.Column("mobile_xray_email", sa.String(255), nullable=True))
    op.create_index("ix_vpn_devices_mobile_xray_uuid", "vpn_devices", ["mobile_xray_uuid"], unique=True)
    op.create_index("ix_vpn_devices_mobile_xray_email", "vpn_devices", ["mobile_xray_email"], unique=True)
    op.create_check_constraint(
        "ck_vpn_devices_mobile_credential_pair",
        "vpn_devices",
        "(mobile_xray_uuid IS NULL AND mobile_xray_email IS NULL) OR "
        "(mobile_xray_uuid IS NOT NULL AND mobile_xray_email IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_vpn_devices_mobile_credential_pair", "vpn_devices", type_="check")
    op.drop_index("ix_vpn_devices_mobile_xray_email", table_name="vpn_devices")
    op.drop_index("ix_vpn_devices_mobile_xray_uuid", table_name="vpn_devices")
    op.drop_column("vpn_devices", "mobile_xray_email")
    op.drop_column("vpn_devices", "mobile_xray_uuid")
