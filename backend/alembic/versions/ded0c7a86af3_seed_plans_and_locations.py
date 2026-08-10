"""seed plans and locations

Revision ID: ded0c7a86af3
Revises: 3efb567265a2
"""

from decimal import Decimal
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ded0c7a86af3"
down_revision: Union[str, Sequence[str], None] = "3efb567265a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    plans = sa.table(
        "plans",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("duration_days", sa.Integer),
        sa.column("price_amount", sa.Numeric),
        sa.column("currency", sa.String),
        sa.column("device_limit", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )

    locations = sa.table(
        "locations",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("is_active", sa.Boolean),
    )

    op.bulk_insert(
        plans,
        [
            {
                "code": "trial_3d",
                "name": "Пробный",
                "duration_days": 3,
                "price_amount": Decimal("0.00"),
                "currency": "RUB",
                "device_limit": 1,
                "is_active": True,
            },
            {
                "code": "standard_1m",
                "name": "1 месяц",
                "duration_days": 30,
                "price_amount": Decimal("199.00"),
                "currency": "RUB",
                "device_limit": 3,
                "is_active": True,
            },
            {
                "code": "standard_3m",
                "name": "3 месяца",
                "duration_days": 90,
                "price_amount": Decimal("499.00"),
                "currency": "RUB",
                "device_limit": 3,
                "is_active": True,
            },
            {
                "code": "standard_6m",
                "name": "6 месяцев",
                "duration_days": 180,
                "price_amount": Decimal("899.00"),
                "currency": "RUB",
                "device_limit": 3,
                "is_active": True,
            },
            {
                "code": "standard_12m",
                "name": "12 месяцев",
                "duration_days": 365,
                "price_amount": Decimal("1599.00"),
                "currency": "RUB",
                "device_limit": 3,
                "is_active": True,
            },
        ],
    )

    op.bulk_insert(
        locations,
        [
            {"code": "NL", "name": "Нидерланды", "is_active": True},
            {"code": "DE", "name": "Германия", "is_active": True},
            {"code": "FI", "name": "Финляндия", "is_active": True},
            {"code": "TR", "name": "Турция", "is_active": True},
            {"code": "RU", "name": "Россия", "is_active": True},
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM plans
            WHERE code IN (
                'trial_3d',
                'standard_1m',
                'standard_3m',
                'standard_6m',
                'standard_12m'
            )
            """
        )
    )

    op.execute(
        sa.text(
            """
            DELETE FROM locations
            WHERE code IN ('NL', 'DE', 'FI', 'TR', 'RU')
            """
        )
    )