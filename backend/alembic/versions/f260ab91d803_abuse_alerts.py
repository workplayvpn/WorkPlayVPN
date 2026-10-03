"""Owner-only observation alerts; no automatic restrictions."""
from alembic import op
import sqlalchemy as sa

revision = "f260ab91d803"
down_revision = "e190ad62bc41"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("abuse_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule", sa.String(32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_abuse_pending", "abuse_alerts", ["sent_at", "next_attempt_at"])
    op.create_index("ix_abuse_cooldown", "abuse_alerts", ["user_id", "rule", "created_at"])


def downgrade():
    op.drop_table("abuse_alerts")
