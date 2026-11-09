"""لایهٔ service — آرشیو کلاس‌های حذف‌شده (گزارش فقط‌خواندنی) (REFAC P3a).

چرا این ماژول: بزرگ‌ترین خوشهٔ منسجمِ `routers/admin.py` بود (۴۱۵ خط، ۱۱ تابع) که هیچ
وابستگی‌ای به HTTP نداشت جز یک `HTTPException` برای گزارشِ ورودیِ نامعتبر. کارش ساختِ
«گزارش تاریخیِ یک کلاس آرشیوشده» است: متادیتای حذف از `ClassDeletionRequest`،
اسنپ‌شات مالی لحظهٔ حذف، تجمیع جلسات/حضور و غیاب، و نرمال‌سازیِ «منبعِ بازیابی»
(restore provenance) با قاعدهٔ fail-closed برای رکوردهای legacy.

نکتهٔ مهمِ رفتاری که با انتقال حفظ شده: این توابع **فقط خواندنی‌اند** و هیچ رکوردی
نمی‌نویسند؛ هر تاریخِ ناموجود «خالی» می‌ماند و هرگز حدس زده نمی‌شود (قاعدهٔ خودِ
پروژه برای کلاس‌های legacy که پیش از ساختِ جدولِ حذف، حذف شده‌اند).

کد **بایت‌به‌بایت** از `routers/admin.py` منتقل شده و هیچ منطقی تغییر نکرده.
`routers/admin.py` همان نام‌ها را import می‌کند (۹ تای آن‌ها را هنوز صدا می‌زند)، پس
رفتار و مسیرهای دسترسی قبلی یکسان مانده‌اند.
"""

import datetime
import json

from fastapi import Depends, Header, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

import models
from dependencies import check_admin_access, get_db
from financial_calculations import calculate_enrollment_debt_breakdown
from models import Attendance, Course, Enrollment, SessionLog, Student, Teacher, Transaction
from services.branch_scope import get_user_branch_filter


# ==========================================
# آرشیو کلاس‌های حذف‌شده (فقط ادمین) — فقط خواندنی + branch isolation
# ==========================================
def _fmt_datetime(dt) -> str:
    """قالب تاریخ پروژه؛ None → رشته‌ی خالی (هیچ تاریخی حدس زده نمی‌شود)."""
    return dt.strftime("%Y/%m/%d %H:%M") if dt else ""


def _safe_person_name(obj) -> str:
    """نام legacy ممکن است NULL باشد — هرگز «None None» برنگردان."""
    if obj is None:
        return ""
    return f"{obj.first_name or ''} {obj.last_name or ''}".strip()


def _archived_deletion_meta(db: Session, course_ids: list[int]) -> dict:
    """متادیتای حذف از جدول ClassDeletionRequest (بدون تاریخ حدسی).

    `Course` ستون تاریخ حذف **ندارد**؛ هر دو مسیر حذف (حذف مستقیم ادمین در classes.py و
    تایید درخواست) یک ردیف `approved` با `decided_at` ثبت می‌کنند. کلاس‌های legacy که پیش از
    این جدول حذف شده‌اند تاریخ ندارند و مقدارشان خالی می‌ماند.
    """
    if not course_ids:
        return {}
    rows = (
        db.query(models.ClassDeletionRequest)
        .filter(
            models.ClassDeletionRequest.course_id.in_(course_ids),
            models.ClassDeletionRequest.status == "approved",
        )
        .order_by(models.ClassDeletionRequest.id)
        .all()
    )
    meta: dict = {}
    for r in rows:  # آخرین ردیف (بیشترین id) متادیتا را می‌دهد؛ اولین تاریخ موجود حفظ می‌شود.
        ts = r.decided_at or r.created_at
        entry = meta.get(r.course_id)
        if entry is None:
            meta[r.course_id] = {
                "deleted_at": ts,
                "forgive_session_charges": bool(r.forgive_session_charges),
                "requested_by_role": r.requested_by_role,
                "admin_note": r.admin_note,
            }
        else:
            if entry["deleted_at"] is None and ts is not None:
                entry["deleted_at"] = ts
            entry["forgive_session_charges"] = bool(r.forgive_session_charges)
            entry["requested_by_role"] = r.requested_by_role
            entry["admin_note"] = r.admin_note
    return meta


def _archived_class_aggregates(db: Session, course_ids: list[int]) -> dict:
    """شمارش تاریخی ثبت‌نام/جلسه/تراکنش هر کلاس با کوئری گروهی (بدون N+1).

    همه‌ی ردیف‌ها شمرده می‌شوند (آرشیوشده‌ها هم) چون آرشیو باید **تاریخچه** را نشان دهد؛
    `Course.is_deleted`/`Enrollment.is_deleted` هیچ ردیفی را حذف نمی‌کنند.
    """
    stats: dict = {cid: {"students_total": 0, "students_active": 0, "sessions_total": 0,
                         "sessions_archived": 0, "transactions_count": 0, "transactions_total": 0}
                   for cid in course_ids}
    if not course_ids:
        return stats
    for cid, is_deleted, cnt in (
        db.query(Enrollment.course_id, Enrollment.is_deleted, func.count(Enrollment.id))
        .filter(Enrollment.course_id.in_(course_ids))
        .group_by(Enrollment.course_id, Enrollment.is_deleted)
        .all()
    ):
        if cid not in stats:
            continue
        stats[cid]["students_total"] += cnt
        # is_deleted=None برای ردیف‌های legacy یعنی «آرشیو نشده» (سیاست موجود پروژه).
        if not is_deleted:
            stats[cid]["students_active"] += cnt
    for cid, is_deleted, cnt in (
        db.query(SessionLog.course_id, SessionLog.is_deleted, func.count(SessionLog.id))
        .filter(SessionLog.course_id.in_(course_ids))
        .group_by(SessionLog.course_id, SessionLog.is_deleted)
        .all()
    ):
        if cid not in stats:
            continue
        stats[cid]["sessions_total"] += cnt
        if is_deleted:
            stats[cid]["sessions_archived"] += cnt
    for cid, cnt, total in (
        db.query(
            Transaction.course_id,
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount), 0),
        )
        .filter(Transaction.course_id.in_(course_ids))
        .group_by(Transaction.course_id)
        .all()
    ):
        if cid not in stats:
            continue
        stats[cid]["transactions_count"] = cnt
        stats[cid]["transactions_total"] = total or 0
    return stats


def _archive_search_variants(term: str) -> list[str]:
    """«ی/ي» و «ک/ك» عربی و فارسی را هم‌ارز می‌کند تا جست‌وجوی آرشیو به تایپ کیبورد حساس نباشد."""
    term = (term or "").strip()
    fa = term.replace("ي", "ی").replace("ك", "ک")
    ar = term.replace("ی", "ي").replace("ک", "ك")
    out: list[str] = []
    for v in (term, fa, ar):
        if v and v not in out:
            out.append(v)
    return out


def _archive_parse_filter_date(value: str | None, label: str) -> datetime.date | None:
    """تاریخ فیلتر آرشیو: جلالی (۱۴۰۵/۰۷/۰۶) یا میلادی؛ نامعتبر ⇒ ۴۲۲ (نه نادیده‌گرفتن بی‌صدا)."""
    if value is None or not str(value).strip():
        return None
    from today_summary import parse_project_date  # lazy: مثل بقیهٔ روترها
    parsed = parse_project_date(str(value))
    if parsed is None:
        raise HTTPException(status_code=422, detail=f"{label} نامعتبر است؛ قالب درست: 1405/07/06")
    return parsed


def _archive_jalali(dt: datetime.datetime | None) -> dict:
    """تاریخ حذف به جلالی + روز هفته (اپ فارسی است؛ تاریخ میلادی برای کاربر بی‌معنی بود)."""
    if not dt:
        return {"deleted_at_jalali": "", "deleted_weekday": ""}
    from today_summary import PERSIAN_DAY_NAMES, jalali_date_string
    return {
        "deleted_at_jalali": f"{jalali_date_string(dt.date())} {dt.strftime('%H:%M')}",
        "deleted_weekday": PERSIAN_DAY_NAMES.get(dt.weekday(), ""),
    }


def _normalize_class_restore_provenance(value):
    """Return a validated v1 deletion ledger, or None for legacy/incomplete snapshots."""
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1:
        return None
    list_keys = ("enrollment_ids", "session_ids", "transaction_rows", "installment_rows", "wallet_credits")
    if any(not isinstance(value.get(key), list) for key in list_keys):
        return None
    for key in ("enrollment_ids", "session_ids"):
        rows = value[key]
        if any(not isinstance(row, int) or isinstance(row, bool) or row <= 0 for row in rows):
            return None
        if len(rows) != len(set(rows)):
            return None

    transaction_keys = {
        "id", "student_id", "course_id", "enrollment_id", "session_id", "type",
        "amount", "share_teacher", "share_institute", "is_reversed", "wallet_credited",
    }
    nullable_integer_fields = (
        "student_id", "course_id", "enrollment_id", "session_id", "amount",
        "share_teacher", "share_institute",
    )
    transaction_ids = []
    for row in value["transaction_rows"]:
        if not isinstance(row, dict) or not transaction_keys.issubset(row):
            return None
        if not isinstance(row.get("id"), int) or isinstance(row.get("id"), bool) or row["id"] <= 0:
            return None
        if any(field_value is not None and (not isinstance(field_value, int) or isinstance(field_value, bool))
               for field_value in (row.get(field) for field in nullable_integer_fields)):
            return None
        if row.get("type") is not None and not isinstance(row.get("type"), str):
            return None
        if not isinstance(row.get("is_reversed"), bool) or row["is_reversed"]:
            return None
        if not isinstance(row.get("wallet_credited"), bool):
            return None
        if row["wallet_credited"] and (row.get("type") != "session_charge" or row.get("student_id") is None):
            return None
        transaction_ids.append(row["id"])
    if len(transaction_ids) != len(set(transaction_ids)):
        return None

    installment_keys = {"id", "enrollment_id", "amount", "due_date", "is_paid", "paid_at", "paid_amount"}
    installment_ids = []
    for row in value["installment_rows"]:
        if not isinstance(row, dict) or not installment_keys.issubset(row):
            return None
        if (not isinstance(row.get("id"), int) or isinstance(row.get("id"), bool) or row["id"] <= 0
                or not isinstance(row.get("enrollment_id"), int)
                or isinstance(row.get("enrollment_id"), bool)
                or row["enrollment_id"] <= 0):
            return None
        for field in ("amount", "paid_amount"):
            field_value = row.get(field)
            if field_value is not None and (not isinstance(field_value, int) or isinstance(field_value, bool)):
                return None
        for field in ("due_date", "paid_at"):
            field_value = row.get(field)
            if field_value is not None and not isinstance(field_value, str):
                return None
        if not isinstance(row.get("is_paid"), bool):
            return None
        installment_ids.append(row["id"])
    if len(installment_ids) != len(set(installment_ids)):
        return None

    credits_by_student = {}
    for row in value["wallet_credits"]:
        if not isinstance(row, dict) or not {"student_id", "teacher", "institute"}.issubset(row):
            return None
        student_id = row.get("student_id")
        if not isinstance(student_id, int) or isinstance(student_id, bool) or student_id <= 0:
            return None
        if student_id in credits_by_student:
            return None
        if any(not isinstance(row.get(field), int) or isinstance(row.get(field), bool)
               for field in ("teacher", "institute")):
            return None
        credits_by_student[student_id] = row

    expected_credits = {}
    for row in value["transaction_rows"]:
        if row["wallet_credited"]:
            amounts = expected_credits.setdefault(row["student_id"], {"teacher": 0, "institute": 0})
            amounts["teacher"] += int(row.get("share_teacher") or 0)
            amounts["institute"] += int(row.get("share_institute") or 0)
    if set(credits_by_student) != set(expected_credits):
        return None
    for student_id, credit in credits_by_student.items():
        expected = expected_credits[student_id]
        if any(credit[field] != expected[field] for field in ("teacher", "institute")):
            return None
    return value


def _latest_class_restore_provenance(db: Session, course_id: int):
    record = (
        db.query(models.ClassDeletionRequest)
        .filter(
            models.ClassDeletionRequest.course_id == course_id,
            models.ClassDeletionRequest.status == "approved",
            models.ClassDeletionRequest.snapshot_json.isnot(None),
        )
        .order_by(models.ClassDeletionRequest.id.desc())
        .first()
    )
    if not record:
        return None
    try:
        snapshot = json.loads(record.snapshot_json or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(snapshot, dict):
        return None
    return _normalize_class_restore_provenance(snapshot.get("restore_provenance"))


def _archived_snapshot_students(db: Session, course_id: int) -> dict:
    """اسنپ‌شات مالی لحظهٔ حذف/درخواست حذف (student_id → ردیف). خرابیِ JSON ⇒ خالی (بدون کرش)."""
    row = (
        db.query(models.ClassDeletionRequest)
        .filter(models.ClassDeletionRequest.course_id == course_id,
                models.ClassDeletionRequest.status == "approved",
                models.ClassDeletionRequest.snapshot_json.isnot(None))
        .order_by(models.ClassDeletionRequest.id.desc())
        .first()
    )
    if not row:
        return {}
    try:
        data = json.loads(row.snapshot_json or "{}")
    except (TypeError, ValueError):
        return {}
    out = {}
    for item in (data.get("students") or []):
        if isinstance(item, dict) and item.get("student_id") is not None:
            out[item["student_id"]] = item
    return out


def _archived_class_people_report(db: Session, course, forgive_session_charges: bool) -> dict:
    """گزارش کامل تاریخیِ یک کلاس آرشیوشده: حضور/غیاب، فهرست دانش‌آموزان و وضعیت مالی.

    فقط خواندنی است و هیچ رکوردی نمی‌نویسد. قواعد:
      • حضور و غیاب از ردیف‌های «فعال» Attendance (is_deleted=False) جلساتِ همین کلاس؛ ردیفِ جلسه‌ای
        که پیش‌تر جداگانه برگشت خورده آرشیو شده و شمرده نمی‌شود (حذف کلاس ردیف حضور را آرشیو نمی‌کند).
      • Present و Late «حاضر» هستند؛ Absent با excused=True «غیبت موجه» و بقیه «غیرموجه».
      • مالی: اگر اسنپ‌شات لحظهٔ حذف موجود باشد همان (source=snapshot)، وگرنه محاسبهٔ ledger که
        پرداخت‌های واقعی‌اش هنگام حذف آرشیو نمی‌شوند (source=computed).
    """
    from dependencies import display_name
    from today_summary import PERSIAN_DAY_NAMES, parse_project_date

    # ---------- حضور و غیاب ----------
    att_rows = (
        db.query(Attendance.student_id, Attendance.session_id, Attendance.status, Attendance.excused)
        .join(SessionLog, SessionLog.id == Attendance.session_id)
        .filter(SessionLog.course_id == course.id, Attendance.is_deleted == False)
        .all()
    )
    per_student: dict = {}
    per_session: dict = {}
    for student_id, session_id, status_value, excused in att_rows:
        st = per_student.setdefault(student_id, {"present": 0, "late": 0, "absent_excused": 0, "absent_unexcused": 0})
        ss = per_session.setdefault(session_id, {"present": 0, "absent": 0, "absent_excused": 0})
        if status_value in ("Present", "Late"):
            st["present"] += 1
            ss["present"] += 1
            if status_value == "Late":
                st["late"] += 1
        elif status_value == "Absent":
            ss["absent"] += 1
            if excused:
                st["absent_excused"] += 1
                ss["absent_excused"] += 1
            else:
                st["absent_unexcused"] += 1

    # ---------- دانش‌آموزان (ثبت‌نام‌های آرشیوی هم) ----------
    enrollments = db.query(Enrollment).filter(Enrollment.course_id == course.id).order_by(Enrollment.id).all()
    student_ids = {e.student_id for e in enrollments if e.student_id is not None} | set(per_student.keys())
    students = {
        s.id: s for s in db.query(Student).filter(Student.id.in_(student_ids)).all()
    } if student_ids else {}
    snapshot = _archived_snapshot_students(db, course.id)

    # هزینه‌ای که با حذف کلاس ابطال شد: session_charge آرشیوشده‌ای که حضور فعالِ همان (جلسه، شاگرد) دارد.
    forgiven: dict = {}
    if forgive_session_charges:
        active_pairs = {(sid, ses) for sid, ses, _, _ in att_rows}
        session_ids = [r[0] for r in db.query(SessionLog.id).filter(SessionLog.course_id == course.id).all()]
        if session_ids:
            for t in db.query(Transaction).filter(
                Transaction.type == "session_charge",
                Transaction.is_deleted == True,
                Transaction.session_id.in_(session_ids),
            ).all():
                if (t.student_id, t.session_id) in active_pairs:
                    f = forgiven.setdefault(t.student_id, [0, 0])
                    f[0] += int(t.share_teacher or 0)
                    f[1] += int(t.share_institute or 0)

    finance: dict = {}
    for en in enrollments:
        if en.student_id is None:
            continue
        b = calculate_enrollment_debt_breakdown(db, en)
        row = finance.setdefault(en.student_id, {"tuition": 0, "paid": 0, "tuition_debt": 0,
                                                  "debt_teacher": 0, "debt_institute": 0, "source": "computed"})
        row["tuition"] += int(b["tuition"] or 0)
        row["paid"] += int(b["paid_teacher"] or 0) + int(b["paid_institute"] or 0)
        row["tuition_debt"] += int(b["debt"] or 0)
        # بدهی جلسه‌ای فقط وقتی چارج‌ها هنوز زنده‌اند (حذف بدون ابطال هزینه‌ها) معنا دارد.
        if not forgive_session_charges and (b.get("sessions_billed") or 0) > 0:
            row["debt_teacher"] += int(b["debt_teacher"] or 0)
            row["debt_institute"] += int(b["debt_institute"] or 0)
    # اسنپ‌شات لحظهٔ حذف، مرجعِ «مانده/پرداختیِ زمان حذف» است و بر محاسبهٔ فعلی مقدم می‌شود.
    for sid, snap in snapshot.items():
        row = finance.get(sid)
        if row is None:
            continue
        row["tuition"] = int(snap.get("tuition_final") or 0)
        row["paid"] = int(snap.get("total_paid") or 0)
        row["tuition_debt"] = int(snap.get("debt") or 0)
        row["source"] = "snapshot"

    rows = []
    for sid in sorted(student_ids, key=lambda i: display_name(students.get(i), "نامشخص")):
        stu = students.get(sid)
        att = per_student.get(sid, {"present": 0, "late": 0, "absent_excused": 0, "absent_unexcused": 0})
        fin = finance.get(sid, {"tuition": 0, "paid": 0, "tuition_debt": 0, "debt_teacher": 0,
                                "debt_institute": 0, "source": "none"})
        absent = att["absent_excused"] + att["absent_unexcused"]
        total = att["present"] + absent
        f_t, f_i = forgiven.get(sid, [0, 0])
        rows.append({
            "student_id": sid,
            "name": display_name(stu, "نامشخص"),
            "student_code": getattr(stu, "student_code", None),
            "present": att["present"],
            "late": att["late"],
            "absent": absent,
            "absent_excused": att["absent_excused"],
            "absent_unexcused": att["absent_unexcused"],
            "attendance_rate": round(att["present"] * 100 / total) if total else None,
            "tuition": fin["tuition"],
            "paid": fin["paid"],
            "tuition_debt": fin["tuition_debt"],
            "session_debt_teacher": fin["debt_teacher"],
            "session_debt_institute": fin["debt_institute"],
            "debt_total": fin["tuition_debt"] + fin["debt_teacher"] + fin["debt_institute"],
            "forgiven_teacher": f_t,
            "forgiven_institute": f_i,
            "finance_source": fin["source"],
        })

    totals_att = {
        "present": sum(r["present"] for r in rows),
        "late": sum(r["late"] for r in rows),
        "absent": sum(r["absent"] for r in rows),
        "absent_excused": sum(r["absent_excused"] for r in rows),
        "absent_unexcused": sum(r["absent_unexcused"] for r in rows),
    }
    denom = totals_att["present"] + totals_att["absent"]
    totals_att["attendance_rate"] = round(totals_att["present"] * 100 / denom) if denom else None
    totals_fin = {
        "tuition": sum(r["tuition"] for r in rows),
        "paid": sum(r["paid"] for r in rows),
        "tuition_debt": sum(r["tuition_debt"] for r in rows),
        "session_debt": sum(r["session_debt_teacher"] + r["session_debt_institute"] for r in rows),
        "debt_total": sum(r["debt_total"] for r in rows),
        "debtors": sum(1 for r in rows if r["debt_total"] > 0),
        "forgiven_total": sum(r["forgiven_teacher"] + r["forgiven_institute"] for r in rows),
    }

    # ---------- جلسه‌ها ----------
    session_rows = []
    for sess in db.query(SessionLog).filter(SessionLog.id.in_(list(per_session.keys()))).order_by(SessionLog.id).all() if per_session else []:
        d = parse_project_date(sess.date)
        agg = per_session.get(sess.id, {"present": 0, "absent": 0, "absent_excused": 0})
        session_rows.append({
            "session_id": sess.id,
            "date": sess.date or "",
            "weekday": PERSIAN_DAY_NAMES.get(d.weekday(), "") if d else "",
            "present": agg["present"],
            "absent": agg["absent"],
            "absent_excused": agg["absent_excused"],
            "absent_unexcused": agg["absent"] - agg["absent_excused"],
        })
    return {
        "students": rows,
        "attendance_totals": totals_att,
        "finance_totals": totals_fin,
        "sessions_held": len(per_session),
        "sessions_history": session_rows,
        "first_session_date": session_rows[0]["date"] if session_rows else "",
        "last_session_date": session_rows[-1]["date"] if session_rows else "",
        "has_snapshot": bool(snapshot),
    }


def get_deleted_classes(
    query: str | None = None,
    title: str | None = None,
    teacher: str | None = None,
    code: str | None = None,
    deleted_from: str | None = None,
    deleted_to: str | None = None,
    branch_id: int | None = None,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
    _: str = Depends(check_admin_access),
):
    """بدنهٔ دامنه‌ایِ `get_deleted_classes`؛ توضیحِ HTTP در پوستهٔ روتر است."""
    # الگوی branch isolation پروژه (analytics/crm/exports) — ادمینِ شعبه‌دار فقط شعبه‌ی خودش.
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)

    # FIX(null-data): is_deleted=True صریح؛ ردیف‌های legacy با NULL «فعال» حساب می‌شوند و
    # طبق سیاست موجود پروژه در آرشیو نمی‌آیند (لیست عادی و آرشیو قاطی نمی‌شوند).
    q = db.query(Course).filter(Course.is_deleted == True)
    if resolved_branch is not None:
        q = q.filter(Course.branch_id == resolved_branch)
    # فیلترهای جست‌وجو (همه با AND): عبارت آزاد، نام کلاس، نام معلم، کد کلاس. هر واژه جدا حساب می‌شود
    # (ترتیب «نام و نام‌خانوادگی» مهم نیست) و ی/ي و ک/ك یکی‌اند.
    teacher_full = (
        func.coalesce(Teacher.first_name, "").op("||")(" ").op("||")(func.coalesce(Teacher.last_name, ""))
    )
    field_map = {"title": Course.title, "code": Course.code, "teacher": teacher_full}

    def _apply_terms(q_, raw: str | None, fields):
        for token in (raw or "").split():
            clauses = [f.ilike(f"%{v}%") for v in _archive_search_variants(token) for f in fields]
            q_ = q_.filter(or_(*clauses))
        return q_

    q = q.outerjoin(Teacher, Teacher.id == Course.teacher_id)
    q = _apply_terms(q, query, [field_map["title"], field_map["code"], field_map["teacher"]])
    q = _apply_terms(q, title, [field_map["title"]])
    q = _apply_terms(q, code, [field_map["code"]])
    q = _apply_terms(q, teacher, [field_map["teacher"]])

    date_from = _archive_parse_filter_date(deleted_from, "تاریخ شروع")
    date_to = _archive_parse_filter_date(deleted_to, "تاریخ پایان")
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from   # بازهٔ وارونه ⇒ جابه‌جا (خطا نده)
    courses = q.all()
    course_ids = [c.id for c in courses]

    meta_map = _archived_deletion_meta(db, course_ids)
    if date_from or date_to:
        # کلاسِ بدون تاریخ حذف (legacy) در بازهٔ زمانی «نامعلوم» است و وارد نتیجه نمی‌شود.
        def _in_range(cid: int) -> bool:
            when = meta_map.get(cid, {}).get("deleted_at")
            if not when:
                return False
            day = when.date()
            return (date_from is None or day >= date_from) and (date_to is None or day <= date_to)
        courses = [c for c in courses if _in_range(c.id)]
        course_ids = [c.id for c in courses]
        meta_map = {cid: meta_map[cid] for cid in course_ids if cid in meta_map}
    stats_map = _archived_class_aggregates(db, course_ids)

    teacher_ids = {c.teacher_id for c in courses if c.teacher_id is not None}
    branch_ids = {c.branch_id for c in courses if c.branch_id is not None}
    teachers = {t.id: t for t in db.query(Teacher).filter(Teacher.id.in_(teacher_ids)).all()} if teacher_ids else {}
    branches = {b.id: b for b in db.query(models.Branch).filter(models.Branch.id.in_(branch_ids)).all()} if branch_ids else {}

    # ترتیب قطعی: تازه‌ترین حذف اول؛ کلاس‌های بدون تاریخ حذف آخر (شناسه نزولی).
    courses.sort(
        key=lambda c: (meta_map.get(c.id, {}).get("deleted_at") or datetime.datetime.min, c.id),
        reverse=True,
    )

    result = []
    for c in courses:
        st = stats_map.get(c.id, {})
        meta = meta_map.get(c.id, {})
        result.append({
            "id": c.id,
            # FIX(null-data): فیلدهای legacy می‌توانند NULL باشند — رشته‌ی خالی می‌رود و
            # فال‌بک نمایش در اپ انجام می‌شود (نه «None/null» در UI).
            "title": c.title or "",
            "code": c.code or "",
            "teacher_id": c.teacher_id,
            "teacher_name": _safe_person_name(teachers.get(c.teacher_id)) or "نامشخص",
            "branch_id": c.branch_id,
            "branch_name": (branches.get(c.branch_id).name if branches.get(c.branch_id) else "") or "",
            "grade_level": c.grade_level or "",
            "days_of_week": c.days_of_week or "",
            "class_time": c.class_time or "",
            "students_count": st.get("students_total", 0),
            "students_active_count": st.get("students_active", 0),
            "sessions_count": st.get("sessions_total", 0),
            "transactions_count": st.get("transactions_count", 0),
            "deleted_at": _fmt_datetime(meta.get("deleted_at")),
            **_archive_jalali(meta.get("deleted_at")),
            "forgive_session_charges": bool(meta.get("forgive_session_charges", False)),
            "is_suspended": bool(c.is_suspended),
            "bg_color": c.bg_color or "#FFFFFF",
        })
    return result
