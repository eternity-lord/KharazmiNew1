# test_branch_resolution.py
# Tests for the central branch-resolution policy (resolve_creation_branch) and the
# fixed creation paths: POST /students/register, POST /students/register_and_enroll,
# POST /classes/create, POST /enrollments/add, plus the safe branch backfill logic.
# Goal: new records always get a valid branch; ambiguous cases get a controlled 400;
# the session-end financial guard stays intact for legacy NULL/NULL rows.
import datetime
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

import models
from models import Base, Branch, Course, Enrollment, InstituteShare, Student, Teacher, Transaction, User, UserSession
from schemas import (
    AttendanceItem, AttendanceSubmitData, CourseCreate, EnrollmentCreate,
    StudentCreate, StudentRegisterAndEnrollRequest,
)
from dependencies import get_active_branch, resolve_creation_branch
from routers.students import register_student, register_and_enroll_student
from routers.classes import create_class, add_enrollment
from routers import attendance
from backfill_branch_ids import collect_plan, apply_plan


def _fake_request(scope_path="/"):
    return Request({
        "type": "http", "method": "POST", "path": scope_path,
        "headers": [(b"host", b"test")], "query_string": b"",
    })


class BranchWorldBase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.Session()

        self.db.add_all([
            Branch(id=1, name="شعبه یک", active=True),
            Branch(id=2, name="شعبه دو", active=True),
        ])
        self.db.flush()

        self.admin_global = User(id=1, username="09120000001", password="x", full_name="مدیر کل",
                                 role="admin", sub_role="admin", branch_id=None)
        self.sec1 = User(id=2, username="09120000002", password="x", full_name="منشی یک",
                         role="admin", sub_role="secretary", branch_id=1)
        self.sec2 = User(id=3, username="09120000003", password="x", full_name="منشی دو",
                         role="admin", sub_role="secretary", branch_id=2)
        self.db.add_all([self.admin_global, self.sec1, self.sec2])
        self.db.flush()

        self.teacher1 = Teacher(first_name="معلم", last_name="یک", mobile="09120000011",
                                national_code="0012345678", is_approved=True, branch_id=1)
        self.teacher_user = User(id=4, username="09120000011", password="x", full_name="معلم یک",
                                 role="teacher", sub_role="teacher")
        self.db.add_all([self.teacher1, self.teacher_user])
        self.db.flush()

        self.db.add_all([
            UserSession(token="tok_admin", user_id=self.admin_global.id, sub_role="admin", created_at=datetime.datetime.now()),
            UserSession(token="tok_sec1", user_id=self.sec1.id, sub_role="secretary", created_at=datetime.datetime.now()),
            UserSession(token="tok_sec2", user_id=self.sec2.id, sub_role="secretary", created_at=datetime.datetime.now()),
            UserSession(token="tok_teacher", user_id=self.teacher_user.id, sub_role="teacher", created_at=datetime.datetime.now()),
        ])
        self.db.commit()
        self._nc = 1000000000

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _nc_code(self):
        # کدهای ملی معتبر (checksum 9 رقمی) — از سری معروف
        for cand in ("1000000028", "1000000036", "1000000044", "1000000052", "1000000060",
                     "1000000079", "1000000087", "1000000095", "1000000103", "1000000111",
                     "1000000129", "1000000137", "1000000145", "1000000153", "1000000161",
                     "1000000170", "1000000188", "1000000196", "1000000204", "1000000212"):
            if not self.db.query(Student).filter(Student.national_code == cand).first():
                return cand
        raise RuntimeError("no free national code")

    def _mobile(self):
        self._mobile_n = getattr(self, "_mobile_n", 0) + 1
        return f"0912{1000000 + self._mobile_n:07d}"

    def _student_create(self, **kw):
        payload = dict(
            first_name="دانش‌آموز", last_name="تست", father_name="پدر",
            national_code=self._nc_code(), birth_date="1390/01/01",
            student_mobile=self._mobile(), parent_mobile="09129990000",
            home_phone="02100000000", address="تهران", study_status="فعال", gender="male",
        )
        payload.update(kw)
        return StudentCreate(**payload)

    def _register_and_enroll(self, **kw):
        payload = dict(
            first_name="دانش‌آموز", last_name="تست", father_name="پدر",
            national_code=self._nc_code(), birth_date="1390/01/01",
            student_mobile=self._mobile(), parent_mobile="09129990001",
            home_phone="02100000000", address="تهران", study_status="فعال", gender="male",
            course_id=None, total_tuition=1000000, paid_amount=0,
            register_date="1405/06/01", shift="عصر",
        )
        payload.update(kw)
        return StudentRegisterAndEnrollRequest(**payload)


# ==========================================
# 1. سیاست مرکزی resolve_creation_branch
# ==========================================
class TestResolveCreationBranch(BranchWorldBase):
    def test_explicit_valid_branch_public(self):
        self.assertEqual(resolve_creation_branch(self.db, requested_branch_id=2), 2)

    def test_explicit_inactive_branch_400(self):
        self.db.query(Branch).filter(Branch.id == 2).update({"active": False})
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            resolve_creation_branch(self.db, requested_branch_id=2)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_explicit_branch_branch_user_isolation_403(self):
        with self.assertRaises(HTTPException) as ctx:
            resolve_creation_branch(self.db, user=self.sec1, requested_branch_id=2)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_explicit_own_branch_ok(self):
        self.assertEqual(resolve_creation_branch(self.db, user=self.sec1, requested_branch_id=1), 1)

    def test_teacher_explicit_other_branch_403(self):
        with self.assertRaises(HTTPException) as ctx:
            resolve_creation_branch(self.db, teacher=self.teacher1, requested_branch_id=2)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_teacher_explicit_own_branch_ok(self):
        self.assertEqual(resolve_creation_branch(self.db, teacher=self.teacher1, requested_branch_id=1), 1)

    def test_own_branch_used(self):
        self.assertEqual(resolve_creation_branch(self.db, user=self.sec2), 2)

    def test_own_branch_inactive_400(self):
        self.db.query(Branch).filter(Branch.id == 1).update({"active": False})
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            resolve_creation_branch(self.db, user=self.sec1)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_single_active_branch_fallback(self):
        self.db.query(Branch).filter(Branch.id == 2).update({"active": False})
        self.db.commit()
        # کاربر بدون شعبه + بدون branch صریح: فقط تک‌شعبه‌ی فعال
        self.assertEqual(resolve_creation_branch(self.db, user=self.admin_global), 1)

    def test_multi_branch_ambiguous_400(self):
        with self.assertRaises(HTTPException) as ctx:
            resolve_creation_branch(self.db, user=self.admin_global)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_fallback_branch_from_business_object(self):
        # بدون branch کاربر، اما branchِ شیء تجاری (مثلاً کلاس) معتبر است
        self.assertEqual(resolve_creation_branch(self.db, user=self.admin_global, fallback_branch_id=2), 2)

    def test_fallback_inactive_falls_through_to_ambiguous(self):
        self.db.query(Branch).filter(Branch.id == 2).update({"active": False})
        self.db.commit()
        # fallback نامعتبر → استفاده نمی‌شود؛ چون ۲ شعبه... نه ۱ فعال باقی مانده است → ۱
        self.assertEqual(resolve_creation_branch(self.db, user=self.admin_global, fallback_branch_id=2), 1)


# ==========================================
# 2. مسیرهای ثبت دانش‌آموز
# ==========================================
class TestStudentCreationPaths(BranchWorldBase):
    def test_register_single_branch_system_no_branch(self):
        self.db.query(Branch).filter(Branch.id == 2).update({"active": False})
        self.db.commit()
        result = register_student(_fake_request(), self._student_create(), db=self.db)
        student = self.db.query(Student).filter(Student.id == result["id"]).first()
        self.assertEqual(student.branch_id, 1)

    def test_register_multi_branch_system_no_branch_400(self):
        with self.assertRaises(HTTPException) as ctx:
            register_student(_fake_request(), self._student_create(), db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_register_with_valid_explicit_branch(self):
        result = register_student(_fake_request(), self._student_create(branch_id=2), db=self.db)
        student = self.db.query(Student).filter(Student.id == result["id"]).first()
        self.assertEqual(student.branch_id, 2)

    def test_register_with_fake_branch_400(self):
        with self.assertRaises(HTTPException) as ctx:
            register_student(_fake_request(), self._student_create(branch_id=999), db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def _course(self, branch_id, code):
        course = Course(title=f"کلاس {code}", code=code, teacher_id=self.teacher1.id,
                        is_admin_approved=True, is_deleted=False, branch_id=branch_id,
                        teacher_session_price=100000, grade_level="دهم", class_time="16:00",
                        days_of_week="شنبه")
        self.db.add(course)
        self.db.commit()
        return course

    def test_register_and_enroll_with_valid_branch(self):
        course = self._course(1, "B1001")
        result = register_and_enroll_student(
            self._register_and_enroll(course_id=course.id),
            db=self.db, authorization="Bearer tok_sec1", sub_role="secretary"
        )
        student = self.db.query(Student).filter(Student.id == result["id"]).first()
        enrollment = self.db.query(Enrollment).filter(Enrollment.id == result["enrollment_id"]).first()
        self.assertEqual(student.branch_id, 1)
        self.assertEqual(enrollment.branch_id, 1)

    def test_register_and_enroll_secretary_sending_other_branch_403(self):
        course = self._course(1, "B1002")
        with self.assertRaises(HTTPException) as ctx:
            register_and_enroll_student(
                self._register_and_enroll(course_id=course.id, branch_id=2),
                db=self.db, authorization="Bearer tok_sec1", sub_role="secretary"
            )
        self.assertEqual(ctx.exception.status_code, 403)
        # داده‌ای ساخته نشده باشد
        self.assertEqual(self.db.query(Student).count(), 0)

    def test_register_and_enroll_global_admin_uses_course_branch(self):
        # ادمین کل بدون شعبه + کلاس شعبه‌دار ⇒ branch همان کلاس (منبع قابل‌اعتماد، نه تخمین)
        course = self._course(2, "B1003")
        result = register_and_enroll_student(
            self._register_and_enroll(course_id=course.id, paid_amount=100000),
            db=self.db, authorization="Bearer tok_admin", sub_role="admin"
        )
        student = self.db.query(Student).filter(Student.id == result["id"]).first()
        self.assertEqual(student.branch_id, 2)
        trans = self.db.query(Transaction).filter(Transaction.enrollment_id == result["enrollment_id"]).first()
        self.assertIsNotNone(trans)
        self.assertEqual(trans.branch_id, 2)

    def test_register_and_enroll_no_course_multi_branch_400(self):
        with self.assertRaises(HTTPException) as ctx:
            register_and_enroll_student(
                self._register_and_enroll(),
                db=self.db, authorization="Bearer tok_admin", sub_role="admin"
            )
        self.assertEqual(ctx.exception.status_code, 400)


# ==========================================
# 3. ساخت کلاس
# ==========================================
class TestClassCreationBranch(BranchWorldBase):
    def _course_create(self, **kw):
        payload = dict(
            title="کلاس تست", code="T1", teacher_id=self.teacher1.id, education_type="دبیرستان",
            grade_level="دهم", gender_type="مختلط", class_time="18:00-19:00",
            days_of_week="شنبه", teacher_session_price=100000,
        )
        payload.update(kw)
        return CourseCreate(**payload)

    def test_admin_single_branch_no_branch(self):
        self.db.query(Branch).filter(Branch.id == 2).update({"active": False})
        self.db.commit()
        result = create_class(self._course_create(), override=True, db=self.db,
                              authorization="Bearer tok_admin", sub_role="admin")
        self.assertEqual(result["status"], "success")
        course = self.db.query(Course).filter(Course.id == result["id"]).first()
        self.assertEqual(course.branch_id, 1)

    def test_admin_multi_branch_no_branch_400(self):
        with self.assertRaises(HTTPException) as ctx:
            create_class(self._course_create(), override=True, db=self.db,
                         authorization="Bearer tok_admin", sub_role="admin")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_admin_with_branch_uses_own(self):
        result = create_class(self._course_create(), override=True, db=self.db,
                              authorization="Bearer tok_sec2", sub_role="secretary")
        course = self.db.query(Course).filter(Course.id == result["id"]).first()
        self.assertEqual(course.branch_id, 2)

    def test_teacher_class_gets_teacher_branch(self):
        result = create_class(self._course_create(), override=True, db=self.db,
                              authorization="Bearer tok_teacher", sub_role="teacher")
        course = self.db.query(Course).filter(Course.id == result["id"]).first()
        self.assertEqual(course.branch_id, 1)
        self.assertEqual(course.teacher_id, self.teacher1.id)

    def test_teacher_sending_other_branch_403(self):
        with self.assertRaises(HTTPException) as ctx:
            create_class(self._course_create(branch_id=2), override=True, db=self.db,
                         authorization="Bearer tok_teacher", sub_role="teacher")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.db.query(Course).count(), 0)


# ==========================================
# 4. سازگاری branch در enrollment
# ==========================================
class TestEnrollmentBranchConsistency(BranchWorldBase):
    def _student(self, branch_id, nc_suffix):
        st = Student(first_name=f"شاگرد{nc_suffix}", last_name="تست",
                     national_code=self._nc_code(), student_mobile=f"0914{self._nc_code()}",
                     branch_id=branch_id, wallet_teacher=0, wallet_institute=0, wallet_balance=0)
        self.db.add(st)
        self.db.commit()
        return st

    def _course(self, branch_id, code):
        course = Course(title=f"کلاس{code}", code=code, teacher_id=self.teacher1.id,
                        is_admin_approved=True, is_deleted=False, branch_id=branch_id,
                        teacher_session_price=100000, grade_level="دهم", class_time="16:00",
                        days_of_week="شنبه")
        self.db.add(course)
        self.db.commit()
        return course

    def test_enrollment_prefers_student_branch(self):
        # policy فعلی H7: branch شاگرد اولویت دارد — بدون تغییر
        st = self._student(1, "a")
        course = self._course(2, "C1")
        data = EnrollmentCreate(student_id=st.id, course_id=course.id, register_date="1405/06/01",
                                shift="عصر", total_tuition=1000000, paid_amount=0,
                                payment_method="نقدی", receiver="-")
        add_enrollment(data, db=self.db, sub_role="admin")
        enrollment = self.db.query(Enrollment).filter(Enrollment.student_id == st.id).first()
        self.assertEqual(enrollment.branch_id, 1)

    def test_enrollment_falls_back_to_course_branch(self):
        st = self._student(None, "b")
        course = self._course(2, "C2")
        data = EnrollmentCreate(student_id=st.id, course_id=course.id, register_date="1405/06/01",
                                shift="عصر", total_tuition=1000000, paid_amount=0,
                                payment_method="نقدی", receiver="-")
        add_enrollment(data, db=self.db, sub_role="admin")
        enrollment = self.db.query(Enrollment).filter(Enrollment.student_id == st.id).first()
        self.assertEqual(enrollment.branch_id, 2)

    def test_enrollment_both_null_stays_null_no_blind_guess(self):
        st = self._student(None, "c")
        course = self._course(None, "C3")
        data = EnrollmentCreate(student_id=st.id, course_id=course.id, register_date="1405/06/01",
                                shift="عصر", total_tuition=1000000, paid_amount=0,
                                payment_method="نقدی", receiver="-")
        add_enrollment(data, db=self.db, sub_role="admin")
        enrollment = self.db.query(Enrollment).filter(Enrollment.student_id == st.id).first()
        self.assertIsNone(enrollment.branch_id, "دو branch NULL ⇒ حدس کورکورانه ممنوع (guard پایان جلسه پاسخ می‌دهد)")


# ==========================================
# 5. end-to-end: ثبت → کلاس → enrollment → جلسه → پایان جلسه
# ==========================================
class TestBranchEndToEnd(BranchWorldBase):
    def setUp(self):
        super().setUp()
        self.db.add(InstituteShare(count_1=50000, count_2=60000, count_3=70000,
                                   count_4=80000, count_5=90000))
        self.db.commit()

    def test_full_flow_session_charge_has_valid_branch(self):
        # 1) کلاس با endpoint واقعی (ادمین کل در سیستم چندشعبه‌ای branch را صریح می‌فرستد)
        course_data = CourseCreate(title="ریاضی E2E", code="E2E1", teacher_id=self.teacher1.id,
                                   education_type="دبیرستان", grade_level="دهم", gender_type="مختلط",
                                   class_time="18:00-19:00", days_of_week="شنبه", teacher_session_price=100000,
                                   branch_id=1)
        res = create_class(course_data, override=True, db=self.db,
                           authorization="Bearer tok_admin", sub_role="admin")
        course = self.db.query(Course).filter(Course.id == res["id"]).first()
        self.assertEqual(course.branch_id, 1)

        # 2) دانش‌آموز با endpoint واقعی (branch صریح فعال)
        reg = register_student(_fake_request(), self._student_create(branch_id=1), db=self.db)
        student = self.db.query(Student).filter(Student.id == reg["id"]).first()
        self.assertEqual(student.branch_id, 1)

        # 3) enrollment
        data = EnrollmentCreate(student_id=student.id, course_id=course.id, register_date="1405/06/01",
                                shift="عصر", total_tuition=1000000, paid_amount=500000,
                                payment_method="نقدی", receiver="منشی")
        add_enrollment(data, db=self.db, sub_role="admin")
        enrollment = self.db.query(Enrollment).filter(Enrollment.student_id == student.id).first()
        self.assertEqual(enrollment.branch_id, 1)

        # 4+5+6) جلسه + حضور + پایان جلسه
        request = AttendanceSubmitData(course_id=course.id, date="1405/06/20",
                                       items=[AttendanceItem(student_id=student.id, status="Present")])
        attendance.submit_session_and_calculate(request, db=self.db,
                                                authorization="Bearer tok_admin", sub_role="admin")

        # 7) session_charge با branch معتبر
        charge = self.db.query(Transaction).filter(
            Transaction.type == "session_charge",
            Transaction.student_id == student.id,
            Transaction.course_id == course.id,
        ).first()
        self.assertIsNotNone(charge, "session_charge باید ساخته شده باشد")
        self.assertEqual(charge.branch_id, 1)

    def test_legacy_null_null_still_controlled_400_no_partial_transaction(self):
        # داده‌ی legacy: شاگرد و کلاس هر دو branch=NULL (مستقیم از ORM — شبیه رکوردهای قدیمی)
        st = Student(first_name="قدیمی", last_name="تست", national_code=self._nc_code(),
                     student_mobile=f"0915{self._nc_code()}", branch_id=None,
                     wallet_teacher=0, wallet_institute=0, wallet_balance=0)
        course = Course(title="کلاس قدیمی", code="LEG1", teacher_id=self.teacher1.id,
                        is_admin_approved=True, is_deleted=False, branch_id=None,
                        teacher_session_price=100000, grade_level="دهم", class_time="16:00",
                        days_of_week="شنبه")
        self.db.add_all([st, course])
        self.db.commit()
        self.db.add(Enrollment(student_id=st.id, course_id=course.id, register_date="1405/06/01",
                               shift="عصر", total_tuition=1000000, total_paid=0))
        self.db.commit()

        request = AttendanceSubmitData(course_id=course.id, date="1405/06/21",
                                       items=[AttendanceItem(student_id=st.id, status="Present")])
        with self.assertRaises(HTTPException) as ctx:
            attendance.submit_session_and_calculate(request, db=self.db,
                                                    authorization="Bearer tok_admin", sub_role="admin")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("شعبه", ctx.exception.detail)

        # بدون تراکنش ناقص و بدون جلسه‌ی نیمه‌کاره (rollback کامل)
        self.assertEqual(self.db.query(Transaction).filter(Transaction.type == "session_charge").count(), 0)
        self.assertEqual(self.db.query(models.SessionLog).filter(models.SessionLog.course_id == course.id).count(), 0)


# ==========================================
# 6. منطق backfill (فقط موارد بدون ابهام)
# ==========================================
class TestBranchBackfill(BranchWorldBase):
    def _student(self, branch_id):
        st = Student(first_name="BF", last_name="تست", national_code=self._nc_code(),
                     student_mobile=f"0916{self._nc_code()}", branch_id=branch_id,
                     wallet_teacher=0, wallet_institute=0, wallet_balance=0)
        self.db.add(st)
        return st

    def _course(self, branch_id, code, teacher_id="UNSET"):
        if teacher_id == "UNSET":
            teacher_id = self.teacher1.id
        course = Course(title=f"BF{code}", code=code, teacher_id=teacher_id,
                        is_admin_approved=True, is_deleted=False, branch_id=branch_id,
                        teacher_session_price=100000, grade_level="دهم")
        self.db.add(course)
        return course

    def test_student_candidate_from_single_branch_enrollments(self):
        st = self._student(None)
        c1 = self._course(1, "S1")
        c2 = self._course(1, "S2")
        self.db.flush()
        self.db.add_all([
            Enrollment(student_id=st.id, course_id=c1.id, total_tuition=1000, total_paid=0, register_date="1405/01/01"),
            Enrollment(student_id=st.id, course_id=c2.id, total_tuition=1000, total_paid=0, register_date="1405/01/02"),
        ])
        self.db.commit()

        plan = collect_plan(self.db)
        decisions = {r[0].id: (r[1], r[2]) for r in plan["students"]}
        self.assertEqual(decisions[st.id], ("candidate", 1))

        applied = apply_plan(self.db, plan)
        self.db.expire_all()
        self.assertEqual(self.db.get(Student, st.id).branch_id, 1)
        self.assertEqual(applied[0], 1)

    def test_student_ambiguous_multi_branch_untouched(self):
        st = self._student(None)
        c1 = self._course(1, "A1")
        c2 = self._course(2, "A2")
        self.db.flush()
        self.db.add_all([
            Enrollment(student_id=st.id, course_id=c1.id, total_tuition=1000, total_paid=0, register_date="1405/01/01"),
            Enrollment(student_id=st.id, course_id=c2.id, total_tuition=1000, total_paid=0, register_date="1405/01/02"),
        ])
        self.db.commit()

        plan = collect_plan(self.db)
        decisions = {r[0].id: r[1] for r in plan["students"]}
        self.assertEqual(decisions[st.id], "ambiguous")

        apply_plan(self.db, plan)
        self.db.expire_all()
        self.assertIsNone(self.db.get(Student, st.id).branch_id, "مبهم ⇒ دست‌نخورده")

    def test_student_without_enrollment_untouched(self):
        st = self._student(None)
        self.db.commit()
        plan = collect_plan(self.db)
        decisions = {r[0].id: r[1] for r in plan["students"]}
        self.assertEqual(decisions[st.id], "ambiguous")
        apply_plan(self.db, plan)
        self.db.expire_all()
        self.assertIsNone(self.db.get(Student, st.id).branch_id)

    def test_course_candidate_from_valid_teacher_branch(self):
        c = self._course(None, "T1")
        self.db.commit()
        plan = collect_plan(self.db)
        decisions = {r[0].id: (r[1], r[2]) for r in plan["courses"]}
        self.assertEqual(decisions[c.id], ("candidate", 1))
        apply_plan(self.db, plan)
        self.db.expire_all()
        self.assertEqual(self.db.get(Course, c.id).branch_id, 1)

    def test_course_with_unknown_teacher_untouched(self):
        c = self._course(None, "T2", teacher_id=None)
        self.db.commit()
        plan = collect_plan(self.db)
        decisions = {r[0].id: r[1] for r in plan["courses"]}
        self.assertEqual(decisions[c.id], "ambiguous")
        apply_plan(self.db, plan)
        self.db.expire_all()
        self.assertIsNone(self.db.get(Course, c.id).branch_id)

    def test_course_multi_branch_teacher_untouched(self):
        # معلم چندشعبه‌ای: کلاس‌های دیگر او در دو شعبه‌ی متفاوت ⇒ branch او قابل اتکا نیست
        self._course(1, "MB1")
        self._course(2, "MB2")
        self.db.flush()
        c = self._course(None, "MB3")
        self.db.commit()
        plan = collect_plan(self.db)
        decisions = {r[0].id: r[1] for r in plan["courses"]}
        self.assertEqual(decisions[c.id], "ambiguous")
        apply_plan(self.db, plan)
        self.db.expire_all()
        self.assertIsNone(self.db.get(Course, c.id).branch_id)

    def test_backfill_never_touches_financials(self):
        st = self._student(None)
        c = self._course(1, "F1")
        self.db.flush()
        en = Enrollment(student_id=st.id, course_id=c.id, total_tuition=1000, total_paid=500,
                        register_date="1405/01/01", branch_id=None)
        self.db.add(en)
        self.db.commit()
        trans = Transaction(student_id=st.id, enrollment_id=en.id, course_id=c.id, amount=500,
                            payment_method="نقدی", date="1405/01/01", type="enrollment_payment",
                            branch_id=None)
        self.db.add(trans)
        self.db.commit()

        plan = collect_plan(self.db)
        apply_plan(self.db, plan)
        self.db.expire_all()
        # شاگرد اصلاح شد (با یک منبع معتبر)
        self.assertEqual(self.db.get(Student, st.id).branch_id, 1)
        # اما enrollment/transaction مالی دست‌نخورده ماندند
        self.assertIsNone(self.db.get(Enrollment, en.id).branch_id)
        self.assertIsNone(self.db.get(Transaction, trans.id).branch_id)


if __name__ == "__main__":
    unittest.main()
