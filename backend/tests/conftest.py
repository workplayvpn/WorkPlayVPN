import pytest
from sqlalchemy import text

from app.db.session import SessionLocal


MUTABLE_TABLES = (
    "payment_fulfillments, "
    "payments, "
    "device_activations, "
    "vpn_devices, "
    "subscription_tokens, "
    "subscriptions, "
    "vpn_node_profiles, "
    "vpn_nodes, "
    "users"
)


def clean_test_database() -> None:
    with SessionLocal() as database:
        database_name = database.scalar(
            text("SELECT current_database()")
        )

        if database_name != "workplayvpn_test":
            raise RuntimeError(
                "Refusing to clean a non-test database"
            )

        database.execute(
            text(
                f"TRUNCATE TABLE {MUTABLE_TABLES} "
                "RESTART IDENTITY CASCADE"
            )
        )
        database.commit()


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    clean_test_database()

    yield

    clean_test_database()
