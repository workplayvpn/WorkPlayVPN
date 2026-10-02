"""PostgreSQL account lock protects concurrent support submissions."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlalchemy import select, delete
from app.db.session import SessionLocal
from app.models.user import User
from app.models.support_ticket import SupportTicket
from app.api.support import TicketCreate
from app.services.support import create

def test_concurrent_support_retry_creates_one_ticket():
    with SessionLocal() as db:
        db.execute(delete(User).where(User.telegram_id == 990923001));db.commit()
        user=User(telegram_id=990923001,is_active=True);db.add(user);db.commit();uid=user.id
    barrier=Barrier(2)
    def submit():
        with SessionLocal() as db:
            user=db.get(User,uid)
            payload=TicketCreate(category='connection',description='VPN не подключается через мобильную сеть',idempotency_key='concurrent-support-key-001')
            barrier.wait(timeout=10)
            row=create(db,user,payload);db.commit();return row.id
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:submit(),range(2)))
        assert results[0] == results[1]
        with SessionLocal() as db:
            assert len(db.scalars(select(SupportTicket).where(SupportTicket.user_id==uid)).all())==1
    finally:
        with SessionLocal() as db:
            db.execute(delete(User).where(User.id==uid));db.commit()
