"""Retire Turkey from available locations without breaking historical references.

Revision ID: 8e7a1c4b902d
Revises: 6ac0e95b2d41
"""

from alembic import op
import sqlalchemy as sa


revision = "8e7a1c4b902d"
down_revision = "6ac0e95b2d41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        UPDATE vpn_nodes SET is_active = FALSE
        WHERE location_id IN (SELECT id FROM locations WHERE code = 'TR')
    """))
    op.execute(sa.text("""
        UPDATE locations SET is_active = FALSE WHERE code = 'TR'
    """))


def downgrade() -> None:
    # Do not reactivate retired nodes: their earlier state is unknown.
    op.execute(sa.text("""
        UPDATE locations SET is_active = TRUE WHERE code = 'TR'
    """))
