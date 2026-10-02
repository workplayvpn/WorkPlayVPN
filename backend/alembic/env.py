from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.session import Base
from app.models.referral import ReferralAccount, ReferralInvite, ReferralCommission, ReferralWithdrawal  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.plan import Plan  # noqa: F401
from app.models.subscription import Subscription  # noqa: F401
from app.models.payment_fulfillment import PaymentFulfillment  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.location import Location  # noqa: F401
from app.models.vpn_node import VpnNode  # noqa: F401
from app.models.vpn_device import VpnDevice  # noqa: F401
from app.models.device_activation import DeviceActivation  # noqa: F401
from app.models.subscription_token import SubscriptionToken  # noqa: F401
from app.models.vpn_node_profile import VpnNodeProfile  # noqa: F401



config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option(
    "sqlalchemy.url",
    settings.database_url.replace("%", "%%"),
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()