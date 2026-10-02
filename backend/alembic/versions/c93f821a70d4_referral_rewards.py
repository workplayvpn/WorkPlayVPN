"""Referral attribution, 15% rewards and manual withdrawal requests."""
from alembic import op
import sqlalchemy as sa
revision="c93f821a70d4"
down_revision="b7e402d91a63"
branch_labels=None
depends_on=None

def uid(name,primary=False):
    return sa.Column(name,sa.BigInteger(),sa.ForeignKey("users.id",ondelete="CASCADE"),primary_key=primary,nullable=False)

def stamp(name):
    return sa.Column(name,sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False)

def upgrade():
    op.create_table("referral_accounts",uid("user_id",True),sa.Column("code",sa.String(32),nullable=False,unique=True),sa.Column("balance_kopecks",sa.BigInteger(),nullable=False,server_default="0"))
    op.create_table("referral_invites",uid("user_id",True),uid("referrer_id"),stamp("created_at"),sa.CheckConstraint("user_id <> referrer_id",name="ck_referral_no_self"))
    op.create_index("ix_referral_invites_referrer_id","referral_invites",["referrer_id"])
    op.create_table("referral_commissions",sa.Column("payment_id",sa.BigInteger(),sa.ForeignKey("payments.id",ondelete="CASCADE"),primary_key=True),uid("referrer_id"),sa.Column("gross_kopecks",sa.BigInteger(),nullable=False),sa.Column("amount_kopecks",sa.BigInteger(),nullable=False),sa.Column("refunded_kopecks",sa.BigInteger(),nullable=False,server_default="0"),sa.Column("reversed_kopecks",sa.BigInteger(),nullable=False,server_default="0"),stamp("created_at"),stamp("updated_at"),sa.CheckConstraint("gross_kopecks > 0 AND amount_kopecks > 0 AND refunded_kopecks BETWEEN 0 AND gross_kopecks AND reversed_kopecks BETWEEN 0 AND amount_kopecks",name="ck_referral_commission_amount"))
    op.create_index("ix_referral_commissions_referrer_id","referral_commissions",["referrer_id"])
    op.create_table("referral_withdrawals",sa.Column("id",sa.String(36),primary_key=True),uid("user_id"),sa.Column("amount_kopecks",sa.BigInteger(),nullable=False),sa.Column("status",sa.String(20),nullable=False,server_default="requested"),sa.Column("idempotency_key",sa.String(64),nullable=False),sa.Column("transfer_reference",sa.String(200),nullable=True,unique=True),sa.Column("note",sa.String(300),nullable=True),stamp("created_at"),stamp("updated_at"),sa.UniqueConstraint("user_id","idempotency_key",name="uq_referral_withdrawal_key"),sa.CheckConstraint("amount_kopecks >= 50000",name="ck_referral_withdrawal_minimum"),sa.CheckConstraint("status IN ('requested','processing','paid','rejected','canceled')",name="ck_referral_withdrawal_status"))
    op.create_index("ix_referral_withdrawals_user_id","referral_withdrawals",["user_id"])
    op.create_index("uq_referral_open_withdrawal","referral_withdrawals",["user_id"],unique=True,postgresql_where=sa.text("status IN ('requested','processing')"))

def downgrade():
    raise RuntimeError("Referral accounting contains financial history. Restore a verified backup instead of dropping it.")
