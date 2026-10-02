"""Financial invariants in isolation; PostgreSQL concurrency has separate tests."""
import unittest
from decimal import Decimal
from unittest.mock import patch
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.db.session import Base
from app.models.location import Location
from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.payment import Payment
from app.models.referral import ReferralInvite, ReferralCommission
from app.services import referrals as svc
from app.core.config import settings

class ReferralAccountingTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite:///:memory:')
        @event.listens_for(self.engine,'connect')
        def fk(conn,rec):conn.execute('PRAGMA foreign_keys=ON')
        Base.metadata.create_all(self.engine)
        self.db=Session(self.engine,autoflush=False)
        self.db.add_all([User(id=i,telegram_id=990920000+i,is_active=True) for i in range(1,5)])
        self.db.add(Plan(id=1,code='ref-unit',name='Basic',duration_days=30,price_amount=Decimal('199'),currency='RUB',access_tier='basic',device_limit=3,is_active=True));self.db.commit()
        self.plan=self.db.get(Plan,1)
        self.db.add(Subscription(id=1,user_id=2,plan_id=1,status='pending'));self.db.commit()
        self.mode=patch.object(settings,'payment_mode','live');self.mode.start()
        self.testmode=patch.object(settings,'robokassa_is_test',False);self.testmode.start()
        self.code=svc.account(self.db,1).code
        svc.bind_new_user(self.db,self.db.get(User,2),self.code);self.db.commit()
    def tearDown(self):
        self.db.close();self.engine.dispose();self.mode.stop();self.testmode.stop()
    def payment(self,id=1,amount='199',provider='robokassa',status='succeeded'):
        x=Payment(id=id,user_id=2,subscription_id=1,provider=provider,status=status,amount=Decimal(amount),currency='RUB',idempotency_key=f'unit-{id}')
        self.db.add(x);self.db.commit();return x
    def balance(self):return svc.account(self.db,1).balance_kopecks
    def credit(self,amount='4000'):
        p=self.payment(amount=amount);svc.credit_payment(self.db,p,self.plan);self.db.commit();return p
    def request(self):
        w=svc.request_withdrawal(self.db,1,50000,'request-key-0001');self.db.commit();return w
    def test_code_stable_and_self_invitation_ignored(self):
        self.assertEqual(svc.account(self.db,1).code,self.code)
        svc.bind_new_user(self.db,self.db.get(User,1),self.code)
        svc.bind_new_user(self.db,self.db.get(User,3),'a'*24);self.db.commit()
        self.assertIsNone(self.db.get(ReferralInvite,1));self.assertIsNone(self.db.get(ReferralInvite,3))
    def test_each_purchase_and_replay_credit_exact_kopecks(self):
        a=self.payment(1);b=self.payment(2,amount='249')
        for p in (a,a,b,b):svc.credit_payment(self.db,p,self.plan);self.db.commit()
        self.assertEqual(self.balance(),6720)
        self.assertEqual(len(self.db.scalars(select(ReferralCommission)).all()),2)
    def test_mobile_also_earns(self):
        self.plan.access_tier='mobile';self.credit('249');self.assertEqual(self.balance(),3735)
    def test_test_provider_and_test_mode_never_earn(self):
        p=self.payment(provider='test');svc.credit_payment(self.db,p,self.plan)
        p.provider='robokassa'
        with patch.object(settings,'payment_mode','test'):svc.credit_payment(self.db,p,self.plan)
        with patch.object(settings,'robokassa_is_test',True):svc.credit_payment(self.db,p,self.plan)
        self.db.commit();self.assertEqual(self.balance(),0)
    def test_pending_slots_and_non_rub_never_earn(self):
        p=self.payment(status='pending');svc.credit_payment(self.db,p,self.plan)
        p.status='succeeded';self.plan.access_tier='device_slots';svc.credit_payment(self.db,p,self.plan)
        self.plan.access_tier='basic';p.currency='USD';svc.credit_payment(self.db,p,self.plan)
        self.db.commit();self.assertEqual(self.balance(),0)
    def test_rollback_removes_reward(self):
        p=self.payment();svc.credit_payment(self.db,p,self.plan);self.db.rollback()
        self.assertEqual(self.balance(),0);self.assertIsNone(self.db.get(ReferralCommission,p.id))
    def test_minimum_reservation_replay_and_insufficient(self):
        self.credit();w=self.request()
        self.assertEqual(svc.summary(self.db,1)['available_kopecks'],10000)
        self.assertEqual(svc.request_withdrawal(self.db,1,50000,'request-key-0001').id,w.id)
        for amount in (49999,50000):
            with self.assertRaises(HTTPException):svc.request_withdrawal(self.db,1,amount,'request-key-0002')
        svc.cancel_withdrawal(self.db,1,w.id);self.db.commit();self.assertEqual(svc.reserved(self.db,1),0)
        with self.assertRaises(HTTPException):svc.request_withdrawal(self.db,1,60001,'request-key-0004')
    def test_payment_requires_processing_and_happens_once(self):
        self.credit();w=self.request()
        with self.assertRaises(HTTPException):svc.process_withdrawal(self.db,w.id,'paid','bank-proof')
        svc.process_withdrawal(self.db,w.id,'processing');self.db.commit()
        with self.assertRaises(HTTPException):svc.cancel_withdrawal(self.db,1,w.id)
        with self.assertRaises(HTTPException):svc.process_withdrawal(self.db,w.id,'paid')
        for _ in range(2):svc.process_withdrawal(self.db,w.id,'paid','bank-proof');self.db.commit()
        self.assertEqual(self.balance(),10000);self.assertEqual(svc.reserved(self.db,1),0)
    def test_partial_full_refund_and_replay(self):
        p=self.credit('199')
        for _ in range(2):svc.reverse_refund(self.db,p.id,10000);self.db.commit()
        self.assertEqual(self.balance(),1485)
        svc.reverse_refund(self.db,p.id,19900);self.db.commit();self.assertEqual(self.balance(),0)
        with self.assertRaises(HTTPException):svc.reverse_refund(self.db,p.id,20000)
    def test_refund_after_payment_creates_debt(self):
        p=self.credit();w=self.request()
        svc.process_withdrawal(self.db,w.id,'processing');svc.process_withdrawal(self.db,w.id,'paid','proof');self.db.commit()
        svc.reverse_refund(self.db,p.id,400000);self.db.commit()
        self.assertEqual(self.balance(),-50000);self.assertEqual(svc.summary(self.db,1)['available_kopecks'],0)
    def test_refund_blocks_reserved_payment(self):
        p=self.credit();w=self.request();svc.reverse_refund(self.db,p.id,400000);self.db.commit()
        with self.assertRaises(HTTPException):svc.process_withdrawal(self.db,w.id,'processing')
        svc.process_withdrawal(self.db,w.id,'rejected',note='Покупка возвращена');self.db.commit();self.assertEqual(svc.reserved(self.db,1),0)
    def test_other_user_cannot_cancel(self):
        self.credit();w=self.request()
        with self.assertRaises(HTTPException):svc.cancel_withdrawal(self.db,3,w.id)
