"""make subscription tokens reproducible

Revision ID: fa38e27c838c
Revises: 64bd1d94815d
Create Date: 2026-08-23 22:20:26.852652

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "fa38e27c838c"
down_revision: Union[str, Sequence[str], None] = "64bd1d94815d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscription_tokens",
        sa.Column(
            "version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )

    op.drop_index(
        op.f("ix_subscription_tokens_token_hash"),
        table_name="subscription_tokens",
    )

    op.drop_column(
        "subscription_tokens",
        "token_hash",
    )


def downgrade() -> None:
    # Старые raw-токены после upgrade восстановить невозможно.
    # Поэтому при rollback создаём новые случайные hash-значения
    # только для восстановления прежней структуры БД.
    op.add_column(
        "subscription_tokens",
        sa.Column(
            "token_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE subscription_tokens
            SET token_hash = encode(
                sha256(
                    (
                        id::text
                        || ':'
                        || user_id::text
                        || ':'
                        || clock_timestamp()::text
                        || ':'
                        || random()::text
                    )::bytea
                ),
                'hex'
            )
            """
        )
    )

    op.alter_column(
        "subscription_tokens",
        "token_hash",
        nullable=False,
    )

    op.create_index(
        op.f("ix_subscription_tokens_token_hash"),
        "subscription_tokens",
        ["token_hash"],
        unique=True,
    )

    op.drop_column(
        "subscription_tokens",
        "version",
    )