"""Persist one encrypted Happ import link per user and subscription tier."""
from alembic import op
import sqlalchemy as sa

revision = "a310d5e8c742"
down_revision = "f260ab91d803"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("happ_import_links",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("access_tier", sa.String(16), primary_key=True),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("encrypted_url", sa.Text(), nullable=False))


def downgrade():
    op.drop_table("happ_import_links")
