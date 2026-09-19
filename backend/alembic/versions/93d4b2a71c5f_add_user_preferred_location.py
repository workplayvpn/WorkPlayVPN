"""add user preferred location

Revision ID: 93d4b2a71c5f
Revises: 6a9f2d84c1e7
Create Date: 2026-09-19 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "93d4b2a71c5f"
down_revision: Union[str, Sequence[str], None] = "6a9f2d84c1e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferred_location_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_users_preferred_location_id_locations",
        "users",
        "locations",
        ["preferred_location_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_users_preferred_location_id",
        "users",
        ["preferred_location_id"],
        unique=False,
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE users AS target_user
            SET preferred_location_id = (
                SELECT vpn_nodes.location_id
                FROM vpn_devices
                JOIN vpn_nodes
                  ON vpn_nodes.id = vpn_devices.node_id
                WHERE vpn_devices.user_id = target_user.id
                  AND vpn_devices.is_active IS TRUE
                ORDER BY vpn_devices.created_at, vpn_devices.id
                LIMIT 1
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_users_preferred_location_id",
        table_name="users",
    )
    op.drop_constraint(
        "fk_users_preferred_location_id_locations",
        "users",
        type_="foreignkey",
    )
    op.drop_column("users", "preferred_location_id")
