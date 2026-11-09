"""
Export to Excel/CSV — خروجی سه گزارش کلیدی برای تحلیل آفلاین (Admin Only, Read-Only, Isolated)

سه اندپوینت:
- GET /exports/debtors               → بدهکاران (منطق کوئری debtors_list کپی شده — بدون فراخوانی اندپوینت)
- GET /exports/overdue_installments  → اقساط معوق (is_paid == False و due_date < امروز جلالی)
- GET /exports/audit_alerts          → هشدارهای Audit Radar (فراخوانی مستقیم get_suspicious_patterns)

Design Notes:
- Isolation: هیچ‌یک از finance.py / timeline.py / audit.py / dunning.py / dashboard.py تغییر نمی‌کند.
  فقط هلپرهای موجود «import» می‌شوند (get_user_branch_filter، calculate_student_debt،
  get_suspicious_patterns) — همان فلسفه‌ی timeline/dunning/audit.
- Security: هر سه اندپوینت Depends(check_admin_access) → 401 بدون توکن، 403 برای منشی/معلم/شاگرد/ولی.
- Read-Only: فقط SELECT؛ هیچ‌گونه نوشتن (کیف پول/تراکنش/لاگ/شمارنده) انجام نمی‌شود.
- Streaming: CSV ردیف‌به‌ردیف yield می‌شود (generator + yield_per) پس 10k+ ردیف در حافظه ساخته نمی‌شود.
- Excel-friendly: BOM یونیکد (\ufeff) در ابتدای استریم تا اکسل فارسی را UTF-8 تشخیص دهد.
"""

import csv
import datetime
import io
from typing import Iterator, List, Optional

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from models import Branch, Enrollment, Installment, Student
from dependencies import get_db, check_admin_access
from financial_calculations import calculate_student_debt
from today_summary import jalali_date_string, parse_project_date

router = APIRouter()

# BOM برای سازگاری اکسل با فارسی (بدون آن، اکسل متن را Latin-1 می‌خواند)
_UTF8_BOM = "\ufeff"
_CSV_MEDIA_TYPE = "text/csv; charset=utf-8"


def _csv_stream(header: List[str], rows: Iterator[List[object]]) -> Iterator[str]:
    """استریم CSV: BOM + سرستون‌ها + ردیف‌ها یکی‌یکی (بدون ساخت کل فایل در حافظه)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    yield _UTF8_BOM

    writer.writerow([_safe_cell(c) for c in header])
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    for row in rows:
        writer.writerow([_safe_cell(c) for c in row])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


def _safe_cell(value: object) -> object:
    """Hardening سبک: جلوگیری از CSV/Excel formula injection روی مقادیر متنی
    (سلول متنی که با = + - @ شروع شود در اکسل فرمول اجرا می‌کند). اعداد دست‌نخورده می‌مانند."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def _csv_response(filename: str, header: List[str], rows: Iterator[List[object]]) -> StreamingResponse:
    return StreamingResponse(
        _csv_stream(header, rows),
        media_type=_CSV_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ==========================================
# ۱) بدهکاران — GET /exports/debtors
# ==========================================
def _iter_debtor_rows(db: Session, resolved_branch: Optional[int]) -> Iterator[List[object]]:
    """FIX (گروه۲/آیتم ۶ و ۹): به‌جای کپی‌منطق، از منبع یگانهٔ `build_debtor_rows`
    (finance.py) استفاده می‌شود ⇒ فیلتر شعبه (NULL = سراسری/legacy) و ستون‌های جدید
    («تاریخ آخرین پرداخت»، «قدمت بدهی») با لیست و Excel یکسان می‌ماند و واگرا نمی‌شود."""
    from routers.finance import build_debtor_rows  # lazy: بدون چرخهٔ import
    for row in build_debtor_rows(db, resolved_branch):
        yield [
            row["student_id"],
            row["student_name"],
            row["national_code"] or "",
            row.get("parent_mobile") or "",
            row["debt_teacher"],
            row["debt_institute"],
            row["total_debt"],
            " | ".join(row["active_courses"]),
            row.get("last_payment_date") or "",
            row.get("debt_age_days") if row.get("debt_age_days") is not None else "",
        ]


@router.get("/exports/debtors")
def export_debtors(
    branch_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access),
):
    """خروجی CSV بدهکاران — فقط ادمین. فیلتر شعبه مثل debtors_list از توکن ادمین resolve می‌شود."""
    # lazy import (سبک dashboard.py): از finance.py فقط تابع هلپر خوانده می‌شود، نه اندپوینت
    from routers.finance import get_user_branch_filter

    # شعبهٔ ناموجود نباید با سیاست legacy (`branch_id=NULL`) اشتباه شود و ردیف سراسری برگرداند.
    # برای شعبهٔ معتبر، ردیف‌های legacy همچنان طبق قرارداد گزارش بدهکاران قابل مشاهده‌اند.
    invalid_requested_branch = branch_id is not None and db.query(Branch).filter(Branch.id == branch_id).first() is None
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)

    header = [
        "شناسه",
        "نام دانش‌آموز",
        "کد ملی",
        "موبایل ولی",
        "بدهی معلم",
        "بدهی آموزشگاه",
        "بدهی کل",
        "کلاس‌های فعال",
        "تاریخ آخرین پرداخت",  # FIX (گروه۲/آیتم۹): ستون‌های پیگیری عملی
        "قدمت بدهی (روز)",
    ]
    rows = iter(()) if invalid_requested_branch else _iter_debtor_rows(db, resolved_branch)
    return _csv_response("debtors.csv", header, rows)


# ==========================================
# ۲) اقساط معوق — GET /exports/overdue_installments
# ==========================================
def _iter_overdue_rows(db: Session, today: datetime.date) -> Iterator[List[object]]:
    """اقساط پرداخت‌نشده با سررسید گذشته.

    فیلتر SQL (ایندکس‌پسند، همان الگوی dashboard.py): رشته‌ی جلالی «YYYY/MM/DD» قابل مقایسه‌ی
    لغوی است → `due_date < today_jalali` مسیر سریع است. شرط دوم ردیف‌هایی را می‌آورد که شکل
    متعارف جلالی ندارند (تاریخ‌های legacy میلادی/غیرصفرپد) تا در پایتون با parse_project_date
    دقیق بررسی شوند؛ ردیف‌های نامعتبر/AIنده رد می‌شوند.
    """
    today_jalali = jalali_date_string(today)

    query = (
        db.query(Installment)
        .join(Enrollment, Installment.enrollment_id == Enrollment.id)
        .join(Student, Enrollment.student_id == Student.id)
        .options(
            joinedload(Installment.enrollment).joinedload(Enrollment.student),
            joinedload(Installment.enrollment).joinedload(Enrollment.course),
        )
        .filter(
            Installment.is_paid == False,  # noqa: E712 (سبک پروژه)
            Installment.is_deleted == False,  # noqa: E712
            Enrollment.is_deleted == False,  # noqa: E712
            Student.is_deleted == False,  # noqa: E712
            Installment.due_date.isnot(None),
            or_(
                Installment.due_date < today_jalali,
                ~Installment.due_date.like("14__/__/__"),  # شکل غیرمتعارف → بررسی دقیق در پایتون
            ),
        )
        .order_by(Installment.due_date.asc(), Installment.id.asc())
        .yield_per(500)  # استریم دسته‌ای: حافظه مستقل از تعداد ردیف‌ها
    )

    for inst in query:
        due = parse_project_date(inst.due_date)
        if due is None or due >= today:
            continue  # تاریخ نامعتبر یا سررسید آینده → معوق نیست

        days_overdue = (today - due).days
        enroll = inst.enrollment
        student = enroll.student if enroll else None
        course = enroll.course if enroll else None

        # وضعیت هم‌واژگان با Dunning (باکت‌ها: ۱ تا ۷ روز = معوق، بیش از ۷ روز = بحرانی)
        status = "بحرانی" if days_overdue > 7 else "معوق"

        yield [
            inst.id,
            f"{student.first_name} {student.last_name}" if student else "---",
            (student.parent_mobile or "") if student else "",
            course.title if course else "کلاس حذف شده",
            inst.amount or 0,
            inst.due_date or "",
            days_overdue,
            status,
        ]


@router.get("/exports/overdue_installments")
def export_overdue_installments(
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access),
):
    """خروجی CSV اقساط معوق — فقط ادمین."""
    today = datetime.datetime.now().date()
    header = [
        "شناسه قسط",
        "نام دانش‌آموز",
        "موبایل ولی",
        "عنوان کلاس",
        "مبلغ",
        "سررسید",
        "روزهای تأخیر",
        "وضعیت",
    ]
    return _csv_response("overdue_installments.csv", header, _iter_overdue_rows(db, today))


# ==========================================
# ۳) هشدارهای رادار — GET /exports/audit_alerts
# ==========================================
def _iter_alert_rows(alerts) -> Iterator[List[object]]:
    for a in alerts:
        yield [
            a.type,
            a.severity,
            a.title,
            a.description,
            a.entity_id,
            a.entity_name,
            a.detected_at,
        ]


@router.get("/exports/audit_alerts")
def export_audit_alerts(
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access),
):
    """خروجی CSV هشدارهای Audit Radar — فقط ادمین. منطق کپی نمی‌شود؛ خود تابع Audit صدا زده می‌شود
    (Isolation: audit.py دست‌نخورده می‌ماند)."""
    # lazy import (سبک dashboard.py) — بدون کپی منطق الگوهای مشکوک
    from routers.audit import get_suspicious_patterns

    alerts = get_suspicious_patterns(db=db, _="admin")
    header = ["نوع", "شدت", "عنوان", "توضیحات", "شناسه موجودیت", "نام موجودیت", "زمان تشخیص"]
    return _csv_response("audit_alerts.csv", header, _iter_alert_rows(alerts))
