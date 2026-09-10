"""add weekly plan

Revision ID: c9488b07f22e
Revises: b46e40a39478
Create Date: 2026-09-09 20:10:45.833907
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9488b07f22e"
down_revision: Union[str, Sequence[str], None] = "b46e40a39478"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            INSERT INTO plans (
                code,
                name,
                duration_days,
                price_amount,
                currency,
                device_limit,
                is_active
            )
            VALUES (
                :code,
                :name,
                :duration_days,
                :price_amount,
                :currency,
                :device_limit,
                true
            )
            ON CONFLICT (code) DO NOTHING
            """
        ),
        {
            "code": "standard_7d",
            "name": "7 дней",
            "duration_days": 7,
            "price_amount": 99,
            "currency": "RUB",
            "device_limit": 3,
        },
    )


def downgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            DELETE FROM plans
            WHERE code = :code
            """
        ),
        {
            "code": "standard_7d",
        },
    )
