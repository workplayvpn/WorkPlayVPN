"""Seed a 30-day Mobile plan, unavailable until a controlled pilot.

Revision ID: c81e7094d352
Revises: f52c1bc88931
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c81e7094d352"
down_revision: Union[str, Sequence[str], None] = "f52c1bc88931"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.get_bind().execute(sa.text("""
        INSERT INTO plans (
            code, name, duration_days, price_amount, currency,
            access_tier, device_limit, is_active
        ) VALUES (
            'mobile_1m', 'VPN Mobile — 30 дней', 30, 249.00, 'RUB',
            'mobile', 3, false
        ) ON CONFLICT (code) DO NOTHING
    """))


def downgrade() -> None:
    op.get_bind().execute(sa.text("""
        DELETE FROM plans WHERE code = 'mobile_1m'
        AND NOT EXISTS (
            SELECT 1 FROM subscriptions WHERE subscriptions.plan_id = plans.id
        )
    """))
