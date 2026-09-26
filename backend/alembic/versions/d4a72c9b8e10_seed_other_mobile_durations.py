"""Add inactive weekly, quarterly, half-year, and annual Mobile plans.

Revision ID: d4a72c9b8e10
Revises: c81e7094d352
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4a72c9b8e10"
down_revision: Union[str, Sequence[str], None] = "c81e7094d352"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.get_bind().execute(sa.text("""
        INSERT INTO plans (
            code, name, duration_days, price_amount, currency,
            access_tier, device_limit, is_active
        ) VALUES
            ('mobile_7d', 'VPN Mobile — 7 дней', 7, 99.00, 'RUB', 'mobile', 3, false),
            ('mobile_3m', 'VPN Mobile — 3 месяца', 90, 699.00, 'RUB', 'mobile', 3, false),
            ('mobile_6m', 'VPN Mobile — 6 месяцев', 180, 1299.00, 'RUB', 'mobile', 3, false),
            ('mobile_12m', 'VPN Mobile — 12 месяцев', 365, 2290.00, 'RUB', 'mobile', 3, false)
        ON CONFLICT (code) DO NOTHING
    """))


def downgrade() -> None:
    op.get_bind().execute(sa.text("""
        DELETE FROM plans WHERE code IN (
            'mobile_7d', 'mobile_3m', 'mobile_6m', 'mobile_12m'
        ) AND NOT EXISTS (
            SELECT 1 FROM subscriptions WHERE subscriptions.plan_id = plans.id
        )
    """))
