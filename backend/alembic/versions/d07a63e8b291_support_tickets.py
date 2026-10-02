"""Knowledge base support tickets and notification outbox."""
from alembic import op
import sqlalchemy as sa
revision = "d07a63e8b291"
down_revision = "c93f821a70d4"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("support_tickets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(24), nullable=False), sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("network", sa.String(16), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("diagnostics", sa.JSON(), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("response", sa.Text(), nullable=True), sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_notified_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("admin_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_support_request"),
        sa.CheckConstraint("status IN ('new','in_progress','resolved','closed')", name="ck_support_status"))
    op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"])

def downgrade():
    raise RuntimeError("Support history must be backed up before a deliberate removal")
