"""Offer all five Mobile durations within the existing closed pilot.

Revision ID: e7c1f8a4d902
Revises: d4a72c9b8e10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7c1f8a4d902"
down_revision: Union[str, Sequence[str], None] = "d4a72c9b8e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The pilot user gate remains enforced by the catalog and payment service.
    result = op.get_bind().execute(sa.text("""
        UPDATE plans SET is_active = true
        WHERE access_tier = 'mobile' AND is_active = false
          AND (code, duration_days, price_amount, currency) IN (
            ('mobile_7d', 7, 99.00, 'RUB'),
            ('mobile_3m', 90, 699.00, 'RUB'),
            ('mobile_6m', 180, 1299.00, 'RUB'),
            ('mobile_12m', 365, 2290.00, 'RUB')
          )
    """))
    if result.rowcount != 4:
        raise RuntimeError(
            "Expected four inactive Mobile plans at pilot prices; "
            "review existing rows before enabling the pilot durations"
        )


def downgrade() -> None:
    op.get_bind().execute(sa.text("""
        UPDATE plans SET is_active = false
        WHERE access_tier = 'mobile'
          AND code IN ('mobile_7d', 'mobile_3m', 'mobile_6m', 'mobile_12m')
    """))
