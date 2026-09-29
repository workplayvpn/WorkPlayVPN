"""Store device model and OS reported by Happ.

Revision ID: 6ac0e95b2d41
Revises: 9b2de7634a10
"""

from alembic import op
import sqlalchemy as sa


revision = "6ac0e95b2d41"
down_revision = "9b2de7634a10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vpn_devices", sa.Column("happ_device_model", sa.String(100)))
    op.add_column("vpn_devices", sa.Column("happ_device_os", sa.String(64)))
    op.add_column("vpn_devices", sa.Column("happ_hwid_digest", sa.String(64)))
    op.create_index("ix_vpn_devices_happ_hwid_digest", "vpn_devices", ["happ_hwid_digest"])


def downgrade() -> None:
    op.drop_index("ix_vpn_devices_happ_hwid_digest", table_name="vpn_devices")
    op.drop_column("vpn_devices", "happ_hwid_digest")
    op.drop_column("vpn_devices", "happ_device_os")
    op.drop_column("vpn_devices", "happ_device_model")
