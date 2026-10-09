"""Rename the public subscription brand; keep all existing plan identifiers."""

from alembic import op
import sqlalchemy as sa

revision = "c10509ab7e31"
down_revision = "b420e6f9d853"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "UPDATE plans SET name = replace(name, 'Mobile', 'Pro') "
        "WHERE access_tier = 'mobile' AND name LIKE '%Mobile%'"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "UPDATE plans SET name = replace(name, 'VPN Pro', 'VPN Mobile') "
        "WHERE access_tier = 'mobile' AND name LIKE 'VPN Pro%'"
    ))
