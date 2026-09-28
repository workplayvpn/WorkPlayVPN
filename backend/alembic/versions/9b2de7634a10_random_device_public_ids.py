"""Add opaque, stable public device IDs.

Revision ID: 9b2de7634a10
Revises: e7c1f8a4d902
"""

import secrets
from alembic import op
import sqlalchemy as sa


revision = "9b2de7634a10"
down_revision = "e7c1f8a4d902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vpn_devices", sa.Column("public_id", sa.String(24), nullable=True))
    connection = op.get_bind()
    device_ids = connection.execute(sa.text("SELECT id FROM vpn_devices")).scalars().all()
    for device_id in device_ids:
        connection.execute(
            sa.text("UPDATE vpn_devices SET public_id = :public_id WHERE id = :id"),
            {"id": device_id, "public_id": "WP-" + secrets.token_hex(8).upper()},
        )
    op.alter_column("vpn_devices", "public_id", nullable=False)
    op.create_unique_constraint("uq_vpn_devices_public_id", "vpn_devices", ["public_id"])


def downgrade() -> None:
    op.drop_constraint("uq_vpn_devices_public_id", "vpn_devices", type_="unique")
    op.drop_column("vpn_devices", "public_id")
