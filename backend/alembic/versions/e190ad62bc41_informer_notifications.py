"""Durable private informer purchase notifications."""
from alembic import op
import sqlalchemy as sa
revision = "e190ad62bc41"
down_revision = "d07a63e8b291"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("informer_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payment_id", sa.BigInteger(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_informer_pending", "informer_notifications", ["sent_at", "next_attempt_at"])


def downgrade():
    op.drop_table("informer_notifications")
