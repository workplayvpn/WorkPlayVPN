"""Add an access tier without changing existing plan prices or availability.

Revision ID: a74eaf519c32
Revises: 93d4b2a71c5f
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a74eaf519c32"
down_revision: Union[str, Sequence[str], None] = "93d4b2a71c5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column(
            "access_tier",
            sa.String(length=16),
            nullable=False,
            server_default="basic",
        ),
    )
    op.create_check_constraint(
        "ck_plans_access_tier",
        "plans",
        "access_tier IN ('basic', 'mobile')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_plans_access_tier", "plans", type_="check")
    op.drop_column("plans", "access_tier")
