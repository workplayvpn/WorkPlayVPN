import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import Integer, MetaData, create_engine, delete, func, select, text
from sqlalchemy.orm import Session

from app.models.location import Location
from app.models.user import User
from app.models.happ_import_link import HappImportLink
from app.services.happ_import_link import stable_happ_import_link


@pytest.fixture
def cache_engine():
    metadata = MetaData()
    for model in (Location, User, HappImportLink):
        table = model.__table__.to_metadata(metadata)
        if "id" in table.c:
            table.c.id.type = Integer()
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(id=1, telegram_id=101), User(id=2, telegram_id=102)])
        db.commit()
    yield engine
    engine.dispose()


def test_link_survives_new_session_and_isolates_user_and_tier(cache_engine):
    calls = []
    def encrypt(url):
        calls.append(url)
        return f"happ://crypt5/uniqueCipher{len(calls)}"
    with Session(cache_engine) as db:
        basic = stable_happ_import_link(db, user_id=1, access_tier="basic", subscription_url="https://test/sub/one/basic", encrypt=encrypt)
        mobile = stable_happ_import_link(db, user_id=1, access_tier="mobile", subscription_url="https://test/sub/one/mobile", encrypt=encrypt)
        other = stable_happ_import_link(db, user_id=2, access_tier="basic", subscription_url="https://test/sub/two/basic", encrypt=encrypt)
    with Session(cache_engine) as db:
        def fail_if_called(url):
            raise AssertionError("A cached link must not need the crypto API")
        assert stable_happ_import_link(db, user_id=1, access_tier="basic", subscription_url="https://test/sub/one/basic", encrypt=fail_if_called) == basic
        assert stable_happ_import_link(db, user_id=1, access_tier="mobile", subscription_url="https://test/sub/one/mobile", encrypt=fail_if_called) == mobile
        assert stable_happ_import_link(db, user_id=2, access_tier="basic", subscription_url="https://test/sub/two/basic", encrypt=fail_if_called) == other
        assert len({basic, mobile, other}) == 3 and len(calls) == 3


def test_rotated_source_replaces_only_its_tier(cache_engine):
    calls = []
    def encrypt(url):
        calls.append(url)
        return f"happ://crypt5/key{len(calls)}"
    with Session(cache_engine) as db:
        first = stable_happ_import_link(db, user_id=1, access_tier="basic", subscription_url="https://test/sub/v1-basic", encrypt=encrypt)
        mobile = stable_happ_import_link(db, user_id=1, access_tier="mobile", subscription_url="https://test/sub/mobile", encrypt=encrypt)
        rotated = stable_happ_import_link(db, user_id=1, access_tier="basic", subscription_url="https://test/sub/v2-basic", encrypt=encrypt)
        assert first != rotated
        assert stable_happ_import_link(db, user_id=1, access_tier="basic", subscription_url="https://test/sub/v2-basic", encrypt=encrypt) == rotated
        assert stable_happ_import_link(db, user_id=1, access_tier="mobile", subscription_url="https://test/sub/mobile", encrypt=encrypt) == mobile
        assert db.scalar(select(func.count()).select_from(HappImportLink)) == 2
        assert len(calls) == 3


@pytest.mark.parametrize("invalid", ["https://plaintext.test", "happ://crypt5/bad value", ""])
def test_failed_encryption_does_not_save_or_poison_cache(cache_engine, invalid):
    with Session(cache_engine) as db:
        with pytest.raises(ValueError):
            stable_happ_import_link(db, user_id=1, access_tier="basic", subscription_url="https://test/sub/one", encrypt=lambda url: invalid)
        assert db.scalar(select(func.count()).select_from(HappImportLink)) == 0
        result = stable_happ_import_link(db, user_id=1, access_tier="basic", subscription_url="https://test/sub/one", encrypt=lambda url: "happ://crypt5/validCipher")
        assert result == "happ://crypt5/validCipher"


def test_postgres_simultaneous_first_requests_return_one_cipher():
    from app.db.session import SessionLocal, engine
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL needed to verify cross-process row locking")
    with SessionLocal() as db:
        assert db.scalar(text("SELECT current_database()")) == "workplayvpn_test"
        user = User(telegram_id=800000000000 + int(uuid.uuid4().hex[:8], 16))
        db.add(user)
        db.commit()
        user_id = user.id
    barrier = Barrier(2)
    def get_key():
        with SessionLocal() as db:
            barrier.wait(timeout=10)
            return stable_happ_import_link(db, user_id=user_id, access_tier="basic", subscription_url="https://test/sub/race", encrypt=lambda url: "happ://crypt5/" + uuid.uuid4().hex)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: get_key(), range(2)))
        assert results[0] == results[1]
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(HappImportLink).where(HappImportLink.user_id == user_id)) == 1
    finally:
        with SessionLocal() as db:
            db.execute(delete(HappImportLink).where(HappImportLink.user_id == user_id))
            db.execute(delete(User).where(User.id == user_id))
            db.commit()
