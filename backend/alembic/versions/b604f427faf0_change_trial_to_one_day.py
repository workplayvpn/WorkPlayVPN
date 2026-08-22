"""change trial to one day

Revision ID: b604f427faf0
Revises: 23a8f2de31d2
Create Date: 2026-08-22 16:02:21.916344

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b604f427faf0'
down_revision: Union[str, Sequence[str], None] = '23a8f2de31d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE plans
        SET
            code = 'trial_1d',
            duration_days = 1
        WHERE code = 'trial_3d'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE plans
        SET
            code = 'trial_3d',
            duration_days = 3
        WHERE code = 'trial_1d'
        """
    )