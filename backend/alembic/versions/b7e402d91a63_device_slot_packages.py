"""Add shared device slot packages."""
from alembic import op
import sqlalchemy as sa
revision = "b7e402d91a63"
down_revision = "8e7a1c4b902d"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_plans_access_tier", "plans", type_="check")
    op.create_check_constraint(
        "ck_plans_access_tier", "plans",
        "access_tier IN ('basic', 'mobile', 'device_slots')",
    )
    for count, price in ((1, 249), (2, 449), (3, 649)):
        op.execute(sa.text("""INSERT INTO plans
            (code, name, duration_days, price_amount, currency, device_limit, is_active, access_tier)
            VALUES (:code, :name, 0, :price, 'RUB', 0, true, 'device_slots')
            ON CONFLICT (code) DO UPDATE SET is_active = true""").bindparams(
            code=f"device_slots_{count}", name=f"Дополнительные слоты: +{count}", price=price))


def downgrade():
    # Keep the expanded constraint: historical slot plans remain referenced by payments.
    # Preserve payment/subscription history and foreign keys.
    op.execute("UPDATE plans SET is_active = false WHERE code IN ('device_slots_1', 'device_slots_2', 'device_slots_3')")
