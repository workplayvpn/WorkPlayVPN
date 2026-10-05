"""Paid gifts, persistent attempt limits and activation notifications."""
from alembic import op
import sqlalchemy as sa

revision = "b420e6f9d853"
down_revision = "a310d5e8c742"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payments", sa.Column("purpose", sa.String(16), nullable=False, server_default="subscription"))
    op.add_column("payments", sa.Column("is_gift_test", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("informer_notifications", "payment_id", existing_type=sa.BigInteger(), nullable=True)
    op.add_column("informer_notifications", sa.Column("event_key", sa.String(80), nullable=True))
    op.create_unique_constraint("uq_informer_event_key", "informer_notifications", ["event_key"])
    op.create_table("gift_certificates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payment_id", sa.BigInteger(), sa.ForeignKey("payments.id", ondelete="RESTRICT"), unique=True, nullable=False),
        sa.Column("buyer_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_id", sa.BigInteger(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("access_tier", sa.String(16), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("device_limit", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("code_hash", sa.String(64), nullable=True, unique=True),
        sa.Column("recipient_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("redeemed_subscription_id", sa.BigInteger(), sa.ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("access_tier IN ('basic', 'mobile')", name="ck_gifts_tier"),
        sa.CheckConstraint("duration_days > 0 AND device_limit > 0", name="ck_gifts_terms"),
        sa.CheckConstraint("state IN ('pending', 'ready', 'redeemed')", name="ck_gifts_state"),
        sa.CheckConstraint("state = 'pending' OR (code_hash IS NOT NULL AND issued_at IS NOT NULL)", name="ck_gifts_issued"),
        sa.CheckConstraint("state != 'redeemed' OR (recipient_id IS NOT NULL AND redeemed_at IS NOT NULL AND redeemed_subscription_id IS NOT NULL)", name="ck_gifts_redeemed"))
    op.create_index("ix_gift_certificates_buyer_id", "gift_certificates", ["buyer_id"])
    op.create_index("ix_gift_certificates_recipient_id", "gift_certificates", ["recipient_id"])
    op.create_table("gift_attempt_windows",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False))


def downgrade():
    # Activated gifts are financial history. Require explicit operator handling
    # rather than deleting history or leaving nullable event rows orphaned.
    raise RuntimeError("Gift migration downgrade requires a reviewed data-preservation procedure")
