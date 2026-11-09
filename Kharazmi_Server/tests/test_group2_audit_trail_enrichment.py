# test_group2_audit_trail_enrichment.py
# ═══════════════════════════════════════════════════════════════════════════════
# گروه ۲ — آیتم ۸: «تاریخچهٔ تغییرات مالی، course_id و branch_id خام نشان می‌دهد»
#
# وضعیت قبل از فیکس (GET /audit-trail/logs): هر ردیف فقط
#   id, timestamp, username, action, entity_type, entity_id, old_values, new_values,
#   ip_address, changed_fields
# را برمی‌گرداند ⇒ کلاینت مجبور است شناسهٔ خام (`course_id: 7`, `branch_id: 2`,
# `student_id: 41`) را خودش به نام تبدیل کند و هیچ «نوع تغییر به زبان ساده»،
# «کاربر تغییردهنده»، «لینک صورت‌حساب»، «جست‌وجو بر اساس نام» یا «رنگ/آیکون» ندارد.
#
# موارد «پیشنهاد من» هم به همین اندپوینت اضافه می‌شوند (نه اندپوینت/موتور جدید):
#   ۱) نام‌ها به‌جای شناسهٔ خام (کلاس/شعبه/دانش‌آموز/معلم/ثبت‌نام)
#   ۲) برچسب فارسی ستون‌ها + جملهٔ خوانا (change_summary) + نوع تغییر به زبان ساده
#   ۳) کاربر تغییردهنده با fallback روی ActivityLog موجود (نه موتور لاگ جدید)
#   ۴) لینک مستقیم به صورت‌حساب دانش‌آموز (همان اندپوینت /reports/student_statement)
#   ۵) جست‌وجو بر اساس نام دانش‌آموز/معلم/کلاس/شعبه/گیرنده
#   ۶) رنگ هر نوع تغییر (کلاینت Android مستقیم مصرف می‌کند؛ drawable جدید لازم نیست)
#
# اجرا (DB موقت — هرگز gaj_db.db واقعی):
#   DATABASE_URL=sqlite:////tmp/g2_i8.db JWT_SECRET_KEY=test \
#     python3 -m pytest Kharazmi_Server/tests/test_group2_audit_trail_enrichment.py -q
# ═══════════════════════════════════════════════════════════════════════════════
import datetime
import json

from models import ActivityLog, Branch, Course, Enrollment, Installment, Student, Teacher, Transaction
from test_audit_trail import AuditTrailBase

JALALI_NOW = None  # (فقط برای خوانایی؛ تاریخ‌ها از datetime.now ساخته می‌شوند)


class TestAuditTrailEnriched(AuditTrailBase):
    """دنیای پایه از `test_audit_trail.AuditTrailBase` (همان سه نقش/توکن) + معلم و شعبهٔ دوم."""

    def setUp(self):
        super().setUp()
        self.db.add(Branch(id=2, name="شعبه شرق", active=True))
        self.db.add(Teacher(id=7, first_name="مریم", last_name="احمدی", mobile="09120000203",
                            national_code="0012345911", is_approved=True, is_deleted=False))
        self.db.add(Student(id=2, first_name="زهرا", last_name="کریمی", national_code="0000000002",
                            student_mobile="09120000002", parent_mobile="09120000002"))
        self.db.add(Course(id=2, title="فیزیک یازدهم", code="PHY2", teacher_id=7,
                           class_time="18:00", branch_id=2, is_admin_approved=True))
        self.db.add(Enrollment(id=2, student_id=2, course_id=2, total_tuition=800000,
                               register_date="1405/06/01"))
        self.db.commit()

    # ---------- helpers ----------
    def _one(self, **params):
        resp = self._get_logs(**params)
        self.assertEqual(resp.status_code, 200, resp.text)
        logs = resp.json()["logs"]
        self.assertEqual(len(logs), 1, f"دقیقاً یک ردیف انتظار می‌رفت: {json.dumps(logs, ensure_ascii=False)}")
        return logs[0]

    def test_8a_ids_are_joined_to_names_instead_of_raw_ids(self):
        """ریشهٔ آیتم ۸: `course_id`/`branch_id`/`student_id` خام در تاریخچه دیده می‌شد."""
        tx = self._add_transaction(branch_id=2, receiver="مدیر")
        log = self._one(entity_type="transaction", entity_id=tx.id, action="create")
        refs = log.get("entity_refs")
        self.assertIsInstance(refs, dict, f"entity_refs باید نام‌ها را داشته باشد: {log}")
        self.assertEqual(refs.get("course"), "ریاضی کنکور", refs)
        self.assertEqual(refs.get("branch"), "شعبه شرق", refs)
        self.assertEqual(refs.get("student"), "سینا مرادی", refs)
        self.assertEqual(refs.get("teacher"), "", refs)  # کلاس ۱ در فیکسچر معلم ندارد
        # مقادیر خام همچنان در old/new_values هست (سازگاری عقب‌رو + قابلیت ممیزی دقیق)
        self.assertEqual(log["new_values"]["course_id"], 1)
        self.assertEqual(log["new_values"]["branch_id"], 2)
        self.assertEqual(log["labels"]["course_id"], "کلاس", log["labels"])
        self.assertEqual(log["labels"]["branch_id"], "شعبه", log["labels"])

    def test_8b_changed_fields_get_persian_labels_and_a_readable_summary(self):
        tx = self._add_transaction()
        tx.amount = 250000
        self.db.commit()
        log = self._one(entity_type="transaction", entity_id=tx.id, action="update")
        self.assertEqual(log["changed_fields"], ["amount"])
        self.assertEqual(log["changed_labels"], ["مبلغ"], log)
        self.assertIn("مبلغ", log["change_summary"])
        self.assertIn("250,000", log["change_summary"])  # مبلغ با جداکنندهٔ هزارگان
        self.assertNotIn("amount: 100000 -> 250000", log["change_summary"])
        # نوع تغییر به زبان ساده + رنگ/آیکون (مورد «پیشنهاد من»)
        self.assertEqual(log["action_label"], "ویرایش", log)
        self.assertEqual(log["change_type"], "edited", log)
        self.assertEqual(log["action_color"], "#FB8C00", log)
        self.assertTrue(log["icon_color"], log)

    def test_8c_actor_falls_back_to_activity_log_when_the_audit_row_has_no_user(self):
        """نوشتن‌های سیستمی/ورکری `username` ندارند ⇒ نام کاربر از ActivityLog موجود بیاید."""
        when = datetime.datetime.utcnow()
        self.db.add(ActivityLog(id=777, admin_username="09120000000", action="transaction_refund",
                                target_id=1, target_name="سینا مرادی",
                                details="استرداد تراکنش #555 به مبلغ 100,000 تومان.",
                                timestamp=when))
        self.db.commit()
        self._insert_log(when=when, action="update", entity_type="transaction", entity_id=555,
                         username=None, user_id=None,
                         old={"amount": 100000}, new={"amount": 0, "is_reversed": True})
        log = self._one(entity_type="transaction", entity_id=555)
        self.assertIsNone(log["username"], "ستون واقعی دست‌کاری نمی‌شود")
        self.assertEqual(log["actor_username"], "09120000000", log)
        self.assertEqual(log["actor_source"], "activity_log", log)
        self.assertEqual(log["actor_action"], "استرداد تراکنش", log)
        self.assertEqual(log["change_type"], "reversed", log)
        self.assertEqual(log["action_color"], "#E53935", log)

    def test_8c2_actor_prefers_the_audit_context_when_it_exists(self):
        """لاگ ممیزی خودش کاربر دارد ⇒ همان اولویت دارد و سراغ ActivityLog نمی‌رویم."""
        when = datetime.datetime.utcnow()
        self.db.add(ActivityLog(id=778, admin_username="کاربر-دیگر", action="transaction_refund",
                                target_id=777, target_name="سینا مرادی", details="استرداد تراکنش #777.",
                                timestamp=when))
        self.db.commit()
        self._insert_log(when=when, action="update", entity_type="transaction", entity_id=777,
                         username="09120000000", user_id=1,
                         old={"amount": 100000}, new={"amount": 0, "is_reversed": True})
        log = self._one(entity_type="transaction", entity_id=777)
        self.assertEqual(log["actor_source"], "audit_context", log)
        self.assertEqual(log["actor_username"], "09120000000", log)
        self.assertIsNone(log["actor_action"], log)

    def test_8d_direct_link_to_the_student_statement(self):
        tx = self._add_transaction()  # student_id=1 در helper پایه
        log = self._one(entity_type="transaction", entity_id=tx.id, action="create")
        self.assertEqual(log["student_id"], 1, log)
        self.assertEqual(log["student_name"], "سینا مرادی", log)
        self.assertEqual(log["student_statement_path"], "/reports/student_statement?student_id=1", log)

    def test_8e_search_by_student_and_teacher_name(self):
        tx1 = self._add_transaction(branch_id=2, receiver="مدیر")          # سینا / ریاضی کنکور
        tx2 = self._add_transaction(student_id=2, course_id=2, enrollment_id=2, branch_id=2)
        inst = Installment(enrollment_id=2, amount=300000, due_date="1405/07/01", is_paid=False)
        self.db.add(inst)
        self.db.commit()

        by_student = self._get_logs(entity_type="transaction", search="سینا")
        self.assertEqual(by_student.status_code, 200, by_student.text)
        ids = {row["entity_id"] for row in by_student.json()["logs"]}
        self.assertIn(tx1.id, ids, by_student.json())
        self.assertNotIn(tx2.id, ids, "جست‌وجوی نام نباید ردیف دانش‌آموز دیگر را بیاورد")

        by_teacher = self._get_logs(entity_type="transaction", search="مریم احمدی")
        self.assertEqual({row["entity_id"] for row in by_teacher.json()["logs"]}, {tx2.id},
                         by_teacher.json())

        # نام معلمِ کلاسِ ثبت‌نام هم برای installment پیدا می‌شود (زنجیره قسط→ثبت‌نام→کلاس→معلم)
        by_teacher_inst = self._get_logs(entity_type="installment", search="احمدی")
        self.assertIn(inst.id, {row["entity_id"] for row in by_teacher_inst.json()["logs"]},
                      by_teacher_inst.json())
        # جست‌وجوی بی‌نتیجه ⇒ ۲۰۰ با لیست خالی (نه ۵۰۰/۴۰۴)
        empty = self._get_logs(search="هیچکس")
        self.assertEqual(empty.status_code, 200, empty.text)
        self.assertEqual(empty.json()["logs"], [], empty.json())
        self.assertEqual(empty.json()["total"], 0, empty.json())

    def test_8f_action_colors_cover_every_change_type(self):
        tx = self._add_transaction()
        create_log = self._one(entity_type="transaction", entity_id=tx.id, action="create")
        self.assertEqual(create_log["action_label"], "ایجاد", create_log)
        self.assertEqual(create_log["change_type"], "new_payment", create_log)
        self.assertEqual(create_log["action_color"], "#4CAF50", create_log)

        tx.is_deleted = True
        self.db.commit()
        void_log = self._one(entity_type="transaction", entity_id=tx.id, action="update")
        self.assertEqual(void_log["change_type"], "voided", void_log)
        # action_label ترجمهٔ خودِ action است؛ ظرافت «باطل‌شده» در change_type/icon_color می‌آید
        self.assertEqual(void_log["action_label"], "ویرایش", void_log)
        self.assertEqual(void_log["action_color"], "#9E9E9E", void_log)
        self.assertEqual(void_log["icon_color"], "#9E9E9E", void_log)

        tx_id = tx.id
        self.db.delete(tx)
        self.db.commit()
        delete_log = self._one(entity_type="transaction", entity_id=tx_id, action="delete")
        self.assertEqual(delete_log["change_type"], "deleted", delete_log)
        self.assertEqual(delete_log["action_label"], "حذف", delete_log)
        self.assertEqual(delete_log["action_color"], "#E53935", delete_log)

    def test_8g_installment_fields_are_labelled_too(self):
        inst = Installment(enrollment_id=1, amount=200000, due_date="1405/07/10", is_paid=False)
        self.db.add(inst)
        self.db.commit()
        log = self._one(entity_type="installment", entity_id=inst.id, action="create")
        self.assertEqual(log["labels"]["due_date"], "سررسید", log["labels"])
        self.assertEqual(log["labels"]["is_paid"], "پرداخت‌شده", log["labels"])
        self.assertEqual(log["labels"]["paid_amount"], "مبلغ پرداخت‌شده", log["labels"])
        self.assertEqual(log["labels"]["enrollment_id"], "ثبت‌نام", log["labels"])
        self.assertEqual(log["entity_refs"].get("enrollment"), "سینا مرادی — ریاضی کنکور",
                         log["entity_refs"])
        self.assertEqual(log["entity_refs"].get("student"), "سینا مرادی", log["entity_refs"])
        self.assertEqual(log["student_statement_path"], "/reports/student_statement?student_id=1", log)

        inst.amount = 250000
        inst.is_paid = True
        self.db.commit()
        upd = self._one(entity_type="installment", entity_id=inst.id, action="update")
        self.assertEqual(sorted(upd["changed_fields"]), ["amount", "is_paid"], upd)
        self.assertEqual(sorted(upd["changed_labels"]), sorted(["مبلغ", "پرداخت‌شده"]), upd)
        self.assertIn("بله", upd["change_summary"], upd)  # مقدار بول به فارسی

    def test_8h_legacy_filters_paging_and_bad_search_still_work(self):
        self._add_transaction(branch_id=2)
        self._add_transaction(student_id=2, course_id=2, enrollment_id=2)
        # فیلترهای قدیمی + صفحه‌بندی دست‌نخورده
        page = self._get_logs(entity_type="transaction", action="create", page=1, limit=1)
        self.assertEqual(page.status_code, 200, page.text)
        body = page.json()
        self.assertEqual(body["limit"], 1, body)
        self.assertEqual(len(body["logs"]), 1, body)
        self.assertGreaterEqual(body["total"], 2, body)
        self.assertEqual(body["pages"], body["total"], body)
        self.assertEqual(self._get_logs(entity_type="unknown").status_code, 400)
        # جست‌وجوی خالی/فاصله ⇒ فیلتر اعمال نمی‌شود (همهٔ ردیف‌ها)
        blank = self._get_logs(search="   ", entity_type="transaction")
        self.assertEqual(blank.status_code, 200, blank.text)
        self.assertEqual(blank.json()["total"], self._get_logs(entity_type="transaction").json()["total"])
        # کلیدهای قدیمی هر ردیف هنوز سر جایشان‌اند (کلاینت منتشرشده نمی‌شکند)
        row = blank.json()["logs"][0]
        for key in ("id", "timestamp", "username", "action", "entity_type", "entity_id",
                    "old_values", "new_values", "ip_address", "changed_fields"):
            self.assertIn(key, row, row.keys())

    def test_8i_search_matches_receiver_and_course_title(self):
        tx1 = self._add_transaction(receiver="منشی دفتر")
        tx2 = self._add_transaction(student_id=2, course_id=2, enrollment_id=2, receiver="مدیر")
        by_receiver = self._get_logs(entity_type="transaction", search="منشی دفتر")
        self.assertEqual({row["entity_id"] for row in by_receiver.json()["logs"]}, {tx1.id},
                         by_receiver.json())
        by_course = self._get_logs(entity_type="transaction", search="فیزیک")
        self.assertEqual({row["entity_id"] for row in by_course.json()["logs"]}, {tx2.id},
                         by_course.json())

    def test_8j_enrichment_never_500s_on_broken_or_orphan_rows(self):
        """JSON خراب / رکورد یتیم (student/course حذف‌شده) ⇒ ۲۰۰ با مقادیر تهی، نه ۵۰۰."""
        when = datetime.datetime.utcnow()
        self._insert_log(when=when, action="update", entity_type="transaction", entity_id=999999,
                         username=None, user_id=None, raw_new="{not-json", old=None)
        resp = self._get_logs(entity_type="transaction", entity_id=999999)
        self.assertEqual(resp.status_code, 200, resp.text)
        log = resp.json()["logs"][0]
        self.assertEqual(log["student_name"], "", log)
        self.assertEqual(log["student_statement_path"], "", log)
        self.assertEqual(log["entity_refs"], {"student": "", "teacher": ""}, log)
        self.assertEqual(log["actor_username"], "", log)
        self.assertTrue(log["change_summary"], "خلاصه نباید خالی بماند")
