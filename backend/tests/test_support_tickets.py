"""Support ownership, idempotency, safe diagnostics and durable notifications."""
import importlib
import unittest
from types import SimpleNamespace
from datetime import UTC, datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from pydantic import ValidationError
from app.db.session import Base
from app.models.user import User
from app.models.support_ticket import SupportTicket
from app.api.support import router, TicketCreate, NotificationAck, ack
from app.api.telegram_webapp_auth import require_telegram_webapp_auth
from app.db.dependencies import get_db
from app.services import support

class SupportTests(unittest.TestCase):
    def setUp(self):
        for name in ("location","plan","subscription","payment","payment_fulfillment","vpn_node","vpn_node_profile","vpn_device","device_activation","subscription_token","referral"):
            importlib.import_module("app.models."+name)
        self.engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
        @event.listens_for(self.engine,"connect")
        def fk(conn,record): conn.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.db=Session(self.engine,autoflush=False)
        self.db.add_all([User(id=1,telegram_id=101,is_active=True),User(id=2,telegram_id=102,is_active=True)]);self.db.commit()
        self.app=FastAPI();self.app.include_router(router)
        self.app.dependency_overrides[get_db]=lambda:self.db
        self.app.dependency_overrides[require_telegram_webapp_auth]=lambda:SimpleNamespace(user=SimpleNamespace(id=101))
        self.client=TestClient(self.app)
    def tearDown(self):self.db.close();self.engine.dispose()
    def payload(self,key="support-test-key-001",**kwargs):
        return TicketCreate(category="connection",description="Не подключается через Wi-Fi после обновления Happ",idempotency_key=key,**kwargs)
    def create(self,key="support-test-key-001",uid=1,**kwargs):
        row=support.create(self.db,self.db.get(User,uid),self.payload(key,**kwargs));self.db.commit();return row
    def test_idempotency_and_conflicting_body(self):
        first=self.create();self.assertEqual(self.create().id,first.id)
        x=self.payload();x.description="Совсем другая проблема при подключении VPN"
        with self.assertRaises(HTTPException) as err:support.create(self.db,self.db.get(User,1),x)
        self.assertEqual(err.exception.status_code,409)
        self.assertEqual(len(self.db.scalars(select(SupportTicket)).all()),1)
    def test_foreign_device_cannot_be_included(self):
        from app.models.location import Location
        from app.models.vpn_node import VpnNode
        from app.models.vpn_device import VpnDevice
        self.db.add(Location(id=1,code="NL",name="Нидерланды",is_active=True));self.db.commit()
        self.db.add(VpnNode(id=1,location_id=1,code="unit",name="Unit",host="example.invalid",ssh_user="unit"));self.db.commit()
        self.db.add(VpnDevice(id=987,user_id=2,node_id=1,device_name="iPhone",xray_uuid="secret-uuid",xray_email="secret-email"));self.db.commit()
        with self.assertRaises(HTTPException) as err:self.create(device_id=987)
        self.assertEqual(err.exception.status_code,404)
        self.db.rollback()
        row=self.create(uid=2,device_id=987)
        self.assertEqual(set(row.diagnostics["device"]),{"id","name"})
        self.assertNotIn("secret",str(row.diagnostics))
    def test_safe_diagnostic_allowlist(self):
        ticket=self.create(platform="ios")
        self.assertEqual(ticket.diagnostics,{"app_version":"20261003-2","platform":"ios"})
        with self.assertRaises(ValidationError):TicketCreate(**dict(self.payload().model_dump(),subscription_key="secret"))
        with self.assertRaises(ValidationError):TicketCreate(category="other",description=" "*25,idempotency_key="support-test-key-001")
    def test_rate_limit_and_replay_still_allowed(self):
        first=self.create()
        self.create("support-test-key-002");self.create("support-test-key-003")
        with self.assertRaises(HTTPException) as err:self.create("support-test-key-004")
        self.assertEqual(err.exception.status_code,429)
        self.assertEqual(self.create().id,first.id)
    def test_open_request_limit(self):
        for n in range(5):
            row=self.create(f"support-test-key-{n:03}");row.created_at=datetime.now(UTC)-timedelta(days=1);self.db.commit()
        with self.assertRaises(HTTPException) as err:self.create("support-test-key-999")
        self.assertEqual(err.exception.status_code,429)
    def test_history_only_own_and_internal_routes_require_secret(self):
        own=self.create();other=self.create(uid=2)
        result=self.client.get("/mini-app/support/tickets");self.assertEqual(result.status_code,200)
        self.assertEqual([x["id"] for x in result.json()],[own.id])
        for path in ("/internal/support/tickets","/internal/support/notifications",f"/internal/support/tickets/{other.id}"):
            self.assertEqual(self.client.get(path).status_code,401)
        self.assertEqual(self.client.post(f"/internal/support/tickets/{own.id}",json={"status":"resolved"}).status_code,401)
    def test_create_api_and_anonymous_rejection(self):
        payload=self.payload().model_dump();result=self.client.post("/mini-app/support/tickets",json=payload)
        self.assertEqual(result.status_code,201)
        self.assertEqual(self.client.post("/mini-app/support/tickets",json=payload).json()["id"],result.json()["id"])
        self.app.dependency_overrides.pop(require_telegram_webapp_auth)
        self.assertNotEqual(self.client.get("/mini-app/support/tickets").status_code,200)
    def test_status_only_update_preserves_existing_answer(self):
        from app.api.internal_auth import require_internal_api_secret
        row=self.create();support.update(self.db,row.id,"in_progress","Проверяем подключение");self.db.commit()
        self.app.dependency_overrides[require_internal_api_secret]=lambda:None
        result=self.client.post(f"/internal/support/tickets/{row.id}",json={"status":"resolved"})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()["response"],"Проверяем подключение")
    def test_notification_ack_does_not_lose_newer_reply(self):
        row=self.create();support.update(self.db,row.id,"in_progress","Проверяем подключение");self.db.commit()
        support.update(self.db,row.id,"resolved","Подключение восстановлено");self.db.commit()
        ack(row.id,NotificationAck(kind="user",revision=1),self.db)
        self.assertEqual(row.revision,2);self.assertEqual(row.user_notified_revision,1)
        ack(row.id,NotificationAck(kind="admin",revision=0),self.db)
        self.assertIsNotNone(row.admin_notified_at)
        support.update(self.db,row.id,"resolved","Подключение восстановлено");self.db.commit();self.assertEqual(row.revision,2)
        self.assertNotIn("telegram_id",support.public(row))
