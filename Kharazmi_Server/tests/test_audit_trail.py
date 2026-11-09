"""
Financial Audit Trail — tests (isolated, sqlite در /tmp — هرگز DB واقعی)

پوشش:
- خودکار بودن لاگ: create/update/delete روی Transaction و Installment از طریق listener ها
- صحت داده: PK در create، مقادیر قبلی از DB (نه از state expire‌شده)، اسنپ‌شات کامل، مهار JSON بلند
- بی‌اثر: UPDATE بی‌اثر لاگ نمی‌شود؛ rollback لاگ را هم برمی‌گرداند؛ خطای لاگ نوشتن بیزینس را نمی‌شکند
- اندپوینت: 401/403/200، صفحه‌بندی، همه‌ی فیلترها، فیلتر تاریخ ISO و جلالی، changed_fields
- میدل‌ور: انتقال زمینه‌ی کاربر (ContextVar) به اندپوینت async و sync، و نشت‌نکردن بین درخواست‌ها
- E2E: نوشتن از مسیر HTTP ⇒ لاگ با username/IP واقعی
- جداسازی: هیچ‌کدام از ۶ روتر محافظت‌شده به audit_trail وابسته نشده‌اند

اجرا (طبق قانون پروژه، همیشه روی کپی — نه DB واقعی):
    cd /home/user/KharazmiApp && DATABASE_URL=sqlite:////tmp/audit_trail_test.db \
        PYTHONPATH=/home/user/KharazmiApp/Kharazmi_Server python3 -m pytest Kharazmi_Server/test_audit_trail.py -q
"""
import contextlib
import datetime
import io
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
import routers.audit_trail as audit_trail
from dependencies import get_db, hash_password
from main import app
from models import (
    Base, Branch, Course, Enrollment, FinancialAuditLog, Installment, Student, Transaction, User, UserSession,
)
from today_summary import gregorian_to_jalali

PROTECTED_ROUTERS = ("finance", "timeline", "audit", "dunning", "dashboard", "exports")


class AuditTrailBase(unittest.TestCase):
    """زیرساخت مشترک: DB فایلی در /tmp (تراکنش‌های مستقل، بدون StaticPool) + سه نقش."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="audit_trail_test_")
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass  # سشن مشترک تست بسته نمی‌شود

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        self.db.add(Branch(id=1, name="مرکزی", active=True))
        self.db.add_all([
            User(id=1, username="09120000000", password=hash_password("123"), full_name="Admin",
                 role="admin", sub_role="admin", branch_id=None),
            User(id=2, username="09121111111", password=hash_password("123"), full_name="Secretary",
                 role="admin", sub_role="secretary", branch_id=None),
            User(id=3, username="09123333333", password=hash_password("101"), full_name="Teacher",
                 role="teacher", sub_role="teacher", branch_id=None),
        ])
        self.db.commit()
        self.db.add_all([
            UserSession(token="tok_admin", user_id=1, sub_role="admin", created_at=datetime.datetime.now()),
            UserSession(token="tok_secretary", user_id=2, sub_role="secretary", created_at=datetime.datetime.now()),
            UserSession(token="tok_teacher", user_id=3, sub_role="teacher", created_at=datetime.datetime.now()),
        ])
        self.db.commit()

        self.student = Student(id=1, first_name="سینا", last_name="مرادی", national_code="0000000001",
                               student_mobile="09120000001", parent_mobile="09120000001")
        self.course = Course(id=1, title="ریاضی کنکور", code="MATH1", class_time="16:00")
        self.db.add_all([self.student, self.course])
        self.db.commit()
        self.enrollment = Enrollment(id=1, student_id=1, course_id=1, total_tuition=1000000,
                                     register_date="1405/06/01")
        self.db.add(self.enrollment)
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        try:
            self.db.close()
        finally:
            self.engine.dispose()
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---------- helpers ----------
    def _add_transaction(self, session=None, **kwargs):
        session = session or self.db
        payload = dict(student_id=1, enrollment_id=1, course_id=1, amount=100000,
                       payment_method="cash", date="1405/06/25", receiver="admin",
                       description="شهریه", target_wallet="institute")
        payload.update(kwargs)
        tx = Transaction(**payload)
        session.add(tx)
        session.commit()
        return tx

    def _audit_rows(self):
        return (self.db.query(FinancialAuditLog)
                .order_by(FinancialAuditLog.id.asc()).all())

    def _get_logs(self, token="tok_admin", **params):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.get("/audit-trail/logs", params=params, headers=headers)

    def _insert_log(self, *, when, action="update", entity_type="transaction", entity_id=1,
                    username="admin", user_id=1, old=None, new=None, ip="127.0.0.1", raw_new=None):
        row = FinancialAuditLog(
            timestamp=when, user_id=user_id, username=username, action=action,
            entity_type=entity_type, entity_id=entity_id,
            old_values=json.dumps(old, ensure_ascii=False) if old is not None else None,
            new_values=raw_new if raw_new is not None else (
                json.dumps(new, ensure_ascii=False) if new is not None else None),
            ip_address=ip,
        )
        self.db.add(row)
        self.db.commit()
        return row.id


# ==========================================
# 1) لاگ‌گیری خودکار (ORM)
# ==========================================
class TestAuditTrailCapture(AuditTrailBase):

    def test_create_is_logged_with_pk_and_full_snapshot(self):
        tx = self._add_transaction()
        rows = self._audit_rows()
        self.assertEqual(len(rows), 1, "یک create ⇒ دقیقاً یک ردیف لاگ")
        row = rows[0]
        self.assertEqual(row.action, "create")
        self.assertEqual(row.entity_type, "transaction")
        self.assertEqual(row.entity_id, tx.id, "PK تازه‌ساخته‌شده در create باید ثبت شود (نه None)")
        self.assertIsNone(row.old_values)
        new_values = json.loads(row.new_values)
        self.assertEqual(new_values["amount"], 100000)
        self.assertEqual(new_values["description"], "شهریه")
        # defaultهای ستون هم بعد از INSERT در اسنپ‌شات دیده می‌شوند
        self.assertIn("is_deleted", new_values)
        self.assertFalse(new_values["is_deleted"])

    def test_update_logs_previous_values_from_db(self):
        tx = self._add_transaction()
        tx.amount = 250000
        self.db.commit()

        rows = self._audit_rows()
        self.assertEqual([r.action for r in rows], ["create", "update"])
        update_row = rows[1]
        self.assertEqual(update_row.entity_id, tx.id)
        old_values = json.loads(update_row.old_values)
        new_values = json.loads(update_row.new_values)
        self.assertEqual(old_values["amount"], 100000, "مقدار قبلی باید از DB خوانده شود، نه از state")
        self.assertEqual(new_values["amount"], 250000)

    def test_noop_update_is_not_logged(self):
        """بعد از commit آبجکت expire می‌شود؛ set دوباره‌ی همان مقدار نباید لاگ کاذب بسازد."""
        tx = self._add_transaction()
        tx.amount = 100000  # همان مقدار قبلی
        self.db.commit()
        self.assertEqual(len(self._audit_rows()), 1, "UPDATE بی‌اثر ⇒ ردیف جدید نباید اضافه شود")

    def test_delete_is_logged_with_old_values(self):
        tx = self._add_transaction()
        tx_id = tx.id
        self.db.delete(tx)
        self.db.commit()

        rows = self._audit_rows()
        self.assertEqual([r.action for r in rows], ["create", "delete"])
        delete_row = rows[1]
        self.assertEqual(delete_row.entity_id, tx_id)
        self.assertIsNone(delete_row.new_values)
        self.assertEqual(json.loads(delete_row.old_values)["amount"], 100000)

    def test_installment_changes_are_logged_as_installment(self):
        inst = Installment(enrollment_id=1, amount=300000, due_date="1405/07/01", is_paid=False)
        self.db.add(inst)
        self.db.commit()
        inst.is_paid = True
        inst.paid_at = "1405/06/26"
        self.db.commit()

        rows = self._audit_rows()
        self.assertEqual([r.entity_type for r in rows], ["installment", "installment"])
        self.assertEqual([r.action for r in rows], ["create", "update"])
        self.assertEqual(rows[1].entity_id, inst.id)
        self.assertTrue(json.loads(rows[1].new_values)["is_paid"])

    def test_rollback_discards_audit_row(self):
        """لاگ باید در همان تراکنش درج شود ⇒ rollback آن را هم برمی‌گرداند."""
        session = self.Session()
        try:
            session.add(Transaction(student_id=1, course_id=1, amount=999, description="rollback-me"))
            session.flush()
            self.assertGreater(session.query(FinancialAuditLog).count(), 0)
            session.rollback()
        finally:
            session.close()
        self.db.expire_all()
        self.assertEqual(self.db.query(FinancialAuditLog).count(), 0,
                         "تغییر commit‌نشده نباید در لاگ بماند")

    def test_missing_audit_table_does_not_break_business_write(self):
        """اگر جدول لاگ در دسترس نباشد، نوشتن مالی باید سالم بماند (هشدار در لاگ سرور)."""
        other_engine = create_engine(f"sqlite:///{os.path.join(self.tmpdir, 'no_audit.db')}")
        Transaction.__table__.create(bind=other_engine)
        OtherSession = sessionmaker(bind=other_engine)
        captured = io.StringIO()
        session = OtherSession()
        try:
            with contextlib.redirect_stdout(captured):
                session.add(Transaction(student_id=1, course_id=1, amount=7, description="no-audit-table"))
                session.commit()
            self.assertEqual(session.query(Transaction).count(), 1)
            self.assertIn("Audit Trail", captured.getvalue(), "خطای لاگ باید با هشدار گزارش شود")
        finally:
            session.close()
            other_engine.dispose()

    def test_huge_values_are_truncated_not_lost(self):
        self._add_transaction(description="د" * 5000)
        row = self._audit_rows()[0]
        stored = json.loads(row.new_values)["description"]
        self.assertLess(len(stored), 1100, "مقدار غول باید بریده شود تا DB باد نکند")
        self.assertTrue(stored.endswith("…"))

    def test_non_financial_models_are_not_logged(self):
        self.db.add(Student(id=99, first_name="بی", last_name="ربط", national_code="0000000099"))
        self.db.commit()
        self.assertEqual(len(self._audit_rows()), 0, "فقط Transaction/Installment لاگ می‌شوند")

    def test_user_attribution_from_context(self):
        token = audit_trail.set_audit_context(7, "operator", "10.0.0.5")
        try:
            self._add_transaction()
        finally:
            audit_trail.reset_audit_context(token)
        row = self._audit_rows()[0]
        self.assertEqual((row.user_id, row.username, row.ip_address), (7, "operator", "10.0.0.5"))

    def test_setup_is_idempotent(self):
        self.assertFalse(audit_trail.setup_audit_listeners(), "نصب دوباره‌ی listener نباید رخ دهد")
        self.assertTrue(audit_trail._LISTENERS_INSTALLED)
        self.assertIn("financial_audit_logs", models.Base.metadata.tables)


# ==========================================
# 2) اندپوینت GET /audit-trail/logs
# ==========================================
class TestAuditTrailEndpoint(AuditTrailBase):

    def test_requires_token(self):
        self.assertEqual(self._get_logs(token=None).status_code, 401)

    def test_secretary_and_teacher_are_forbidden(self):
        self.assertEqual(self._get_logs(token="tok_secretary").status_code, 403)
        self.assertEqual(self._get_logs(token="tok_teacher").status_code, 403)

    def test_admin_gets_paginated_response(self):
        for index in range(5):
            self._insert_log(when=datetime.datetime.utcnow() + datetime.timedelta(minutes=index),
                             entity_id=index + 1, new={"amount": index})
        response = self._get_logs(limit=2, page=1)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 5)
        self.assertEqual(body["limit"], 2)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["pages"], 3)
        self.assertEqual(len(body["logs"]), 2)
        # جدیدترین‌ها اول
        self.assertGreater(body["logs"][0]["entity_id"], body["logs"][1]["entity_id"])
        last_page = self._get_logs(limit=2, page=3).json()
        self.assertEqual(len(last_page["logs"]), 1)

    def test_entity_and_action_filters(self):
        self._insert_log(when=datetime.datetime.utcnow(), entity_type="transaction", entity_id=11, action="create")
        self._insert_log(when=datetime.datetime.utcnow(), entity_type="transaction", entity_id=12, action="update")
        self._insert_log(when=datetime.datetime.utcnow(), entity_type="installment", entity_id=11, action="delete")

        by_type = self._get_logs(entity_type="installment").json()
        self.assertEqual([log["entity_type"] for log in by_type["logs"]], ["installment"])

        by_entity = self._get_logs(entity_type="transaction", entity_id=11).json()
        self.assertEqual(len(by_entity["logs"]), 1)
        self.assertEqual(by_entity["logs"][0]["action"], "create")

        by_action = self._get_logs(action="delete").json()
        self.assertEqual([log["action"] for log in by_action["logs"]], ["delete"])

        by_user = self._get_logs(user_id=1).json()
        self.assertEqual(by_user["total"], 3)

    def test_invalid_filters_are_rejected(self):
        self.assertEqual(self._get_logs(entity_type="bogus").status_code, 400)
        self.assertEqual(self._get_logs(action="bogus").status_code, 400)
        self.assertEqual(self._get_logs(limit=500).status_code, 422)
        self.assertEqual(self._get_logs(page=0).status_code, 422)
        self.assertEqual(self._get_logs(start_date="1405/07/10", end_date="1405/07/01").status_code, 400)
        self.assertEqual(self._get_logs(start_date="نه-تاریخ").status_code, 400)

    def test_date_filters_iso_and_jalali(self):
        when_utc = datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
        self._insert_log(when=when_utc, entity_id=1)
        local_day = audit_trail._to_local_naive(when_utc).date()
        other_day = local_day - datetime.timedelta(days=3)

        iso_hit = self._get_logs(start_date=local_day.isoformat(), end_date=local_day.isoformat()).json()
        self.assertEqual(iso_hit["total"], 1, "فیلتر تاریخ خالص ISO باید کل روز محلی را پوشش دهد")

        miss = self._get_logs(start_date=other_day.isoformat(), end_date=other_day.isoformat()).json()
        self.assertEqual(miss["total"], 0)

        jalali_year, jalali_month, jalali_day = gregorian_to_jalali(local_day)
        jalali_hit = self._get_logs(
            start_date=f"{jalali_year}/{jalali_month:02d}/{jalali_day:02d}",
            end_date=f"{jalali_year}/{jalali_month:02d}/{jalali_day:02d}",
        ).json()
        self.assertEqual(jalali_hit["total"], 1, "فیلتر تاریخ جلالی باید کار کند")

    def test_timestamp_is_returned_in_server_local_time(self):
        when_utc = datetime.datetime.utcnow() - datetime.timedelta(minutes=1)
        self._insert_log(when=when_utc, entity_id=1)
        returned = self._get_logs().json()["logs"][0]["timestamp"]
        expected = when_utc.replace(tzinfo=datetime.timezone.utc).astimezone().replace(tzinfo=None)
        self.assertEqual(returned, expected.isoformat(sep=" "))

    def test_changed_fields_created_by_real_writes(self):
        tx = self._add_transaction()
        tx.amount = 500000
        self.db.commit()
        self.db.delete(tx)
        self.db.commit()

        logs = self._get_logs().json()["logs"]
        self.assertEqual([log["action"] for log in logs], ["delete", "update", "create"])

        create_log = logs[2]
        self.assertIn("amount", create_log["changed_fields"])
        self.assertNotIn("payment_method", [f for f in create_log["changed_fields"] if f == "id"])

        update_log = logs[1]
        self.assertEqual(update_log["changed_fields"], ["amount"],
                         "در update فقط ستون واقعاً تغییریافته باید گزارش شود")
        self.assertEqual(update_log["old_values"]["amount"], 100000)
        self.assertEqual(update_log["new_values"]["amount"], 500000)
        self.assertEqual(update_log["entity_id"], tx.id)
        self.assertEqual(update_log["entity_type"], "transaction")

        delete_log = logs[0]
        self.assertIn("amount", delete_log["changed_fields"])
        self.assertIsNone(delete_log["new_values"])

    def test_corrupt_json_does_not_break_response(self):
        self._insert_log(when=datetime.datetime.utcnow(), entity_id=1, raw_new="{not-json")
        response = self._get_logs()
        self.assertEqual(response.status_code, 200)
        log = response.json()["logs"][0]
        self.assertIn("raw", log["new_values"])
        self.assertEqual(log["changed_fields"], [])

    def test_empty_database_returns_zero_pages(self):
        body = self._get_logs().json()
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["pages"], 0)
        self.assertEqual(body["logs"], [])


# ==========================================
# 3) میدل‌ور زمینه‌ی کاربر
# ==========================================
class TestAuditContextMiddleware(AuditTrailBase):
    """میدل‌ور واقعی روی یک اپ کوچک (اندپوینت async و sync) — بدون وابستگی به payloadهای finance."""

    def setUp(self):
        super().setUp()
        seen = {}
        self.seen = seen
        mini = FastAPI()
        mini.add_middleware(audit_trail.AuditContextMiddleware)

        @mini.post("/async-probe")
        async def async_probe():
            seen["async"] = audit_trail.current_audit_context()
            return {"ok": True}

        @mini.post("/sync-probe")
        def sync_probe():
            # اندپوینت‌های sync در threadpool اجرا می‌شوند — ContextVar باید آنجا هم دیده شود.
            seen["sync"] = audit_trail.current_audit_context()
            return {"ok": True}

        @mini.get("/read-probe")
        def read_probe():
            seen["read"] = audit_trail.current_audit_context()
            return {"ok": True}

        self.probe_client = TestClient(mini)
        # میدل‌ور با SessionLocal سراسری کار می‌کند ⇒ به DB همین تست وصلش می‌کنیم
        self._patcher = mock.patch.object(models, "SessionLocal", self.Session)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        super().tearDown()

    def test_async_and_sync_endpoints_see_user(self):
        response = self.probe_client.post("/async-probe", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.seen["async"].get("username"), "09120000000")
        self.assertEqual(self.seen["async"].get("user_id"), 1)

        self.probe_client.post("/sync-probe", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(self.seen["sync"].get("username"), "09120000000",
                         "ContextVar باید در threadpool اندپوینت sync هم در دسترس باشد")

    def test_ip_from_forwarded_header(self):
        self.probe_client.post("/async-probe", headers={
            "Authorization": "Bearer tok_admin",
            "X-Forwarded-For": "203.0.113.7, 10.0.0.1",
        })
        self.assertEqual(self.seen["async"].get("ip_address"), "203.0.113.7")

    def test_get_request_does_not_resolve_user(self):
        self.probe_client.get("/read-probe", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(self.seen["read"], {}, "GET باید بدون سربار و بدون زمینه باشد")

    def test_invalid_token_leaves_context_empty(self):
        self.probe_client.post("/async-probe", headers={"Authorization": "Bearer tok-unknown"})
        self.assertEqual(self.seen["async"], {})

    def test_context_does_not_leak_between_requests(self):
        self.probe_client.post("/async-probe", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(self.seen["async"].get("user_id"), 1)
        self.probe_client.post("/async-probe")  # بدون توکن
        self.assertEqual(self.seen["async"], {}, "کاربر درخواست قبلی نباید به درخواست بعدی نشت کند")


# ==========================================
# 4) E2E: نوشتن از مسیر HTTP با انتساب به کاربر
# ==========================================
class TestAuditTrailEndToEnd(AuditTrailBase):

    def setUp(self):
        super().setUp()
        mini = FastAPI()
        mini.add_middleware(audit_trail.AuditContextMiddleware)

        @mini.post("/pay")
        def pay():
            session = models.SessionLocal()
            try:
                session.add(Transaction(student_id=1, enrollment_id=1, course_id=1, amount=45000,
                                        payment_method="cash", date="1405/06/25", description="پرداخت E2E"))
                session.commit()
            finally:
                session.close()
            return {"ok": True}

        self.e2e_client = TestClient(mini)
        self._patcher = mock.patch.object(models, "SessionLocal", self.Session)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        super().tearDown()

    def test_http_write_is_attributed_to_the_logged_in_user(self):
        response = self.e2e_client.post("/pay", headers={
            "Authorization": "Bearer tok_admin",
            "X-Forwarded-For": "198.51.100.9",
        })
        self.assertEqual(response.status_code, 200)

        self.db.expire_all()
        rows = self._audit_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.action, "create")
        self.assertEqual(row.entity_type, "transaction")
        self.assertEqual(row.username, "09120000000")
        self.assertEqual(row.user_id, 1)
        self.assertEqual(row.ip_address, "198.51.100.9")
        self.assertEqual(json.loads(row.new_values)["amount"], 45000)


# ==========================================
# 5) جداسازی از روترهای محافظت‌شده
# ==========================================
class TestIsolationFromProtectedRouters(unittest.TestCase):

    def test_protected_routers_are_untouched(self):
        # FIX(tests-dir): پوشهٔ سرور یک سطح بالاتر از پوشهٔ tests/ است.
        routers_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "routers")
        for name in PROTECTED_ROUTERS:
            path = os.path.join(routers_dir, f"{name}.py")
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            self.assertNotIn("audit_trail", source, f"{name}.py نباید به audit_trail وابسته شود")
            self.assertNotIn("FinancialAuditLog", source, f"{name}.py نباید جدول لاگ را دست بزند")


if __name__ == "__main__":
    unittest.main(verbosity=2)
