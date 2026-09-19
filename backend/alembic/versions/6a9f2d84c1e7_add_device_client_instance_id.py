"""add device client instance id

Revision ID: 6a9f2d84c1e7
Revises: c9488b07f22e
Create Date: 2026-09-19 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6a9f2d84c1e7"
down_revision: Union[str, Sequence[str], None] = "c9488b07f22e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vpn_devices",
        sa.Column(
            "client_instance_id",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.create_index(
        "uq_vpn_devices_user_client_instance_active",
        "vpn_devices",
        ["user_id", "client_instance_id"],
        unique=True,
        postgresql_where=sa.text(
            "client_instance_id IS NOT NULL AND is_active IS TRUE"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_vpn_devices_user_client_instance_active",
        table_name="vpn_devices",
    )
    op.drop_column("vpn_devices", "client_instance_id")
