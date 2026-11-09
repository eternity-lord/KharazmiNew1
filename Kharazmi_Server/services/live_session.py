"""لایهٔ service — primitives کلاس زنده (Live Session) (REFAC P3a).

چرا این ماژول: این ده تابع/کلاس «آجرهای» مدیریت جلسهٔ زنده‌اند و هیچ‌کدام HTTP نمی‌شناسند
(جز یک `HTTPException` در گارد مالکیت کلاس): رشته‌سازی زمان، سقف دقیقهٔ جلسهٔ زنده از
تنظیمات آموزشگاه، گارد «فقط معلمِ مالک»، upsert ردیف حضور با قید یکتای
`uq_attendance_session_student`، تسخیر اتمیک LIVE→FINALIZING (مشترک بین مسیر دستی و ورکر
auto-end در `main.py`)، تاریخ کانونیک جلسه، تشخیص جلسهٔ تکراریِ همان تاریخ، و استثنا
`DuplicateSessionDate`.

دو نکته دربارهٔ آنچه عمداً اینجا **نیامد**:
  • `finalize_live_session` در `routers/attendance.py` ماند، چون محاسبهٔ مالی را به
    `submit_session_and_calculate` (یک handler در همان روتر) واگذار می‌کند؛ انتقالش یا
    چرخهٔ import می‌ساخت یا وابستگیِ service→router. معکوس‌کردنِ آن وابستگی (استخراجِ
    بدنهٔ آن handler به service) کارِ فاز بعدیِ ریفکتور است.
  • `_resolve_live_session_for_action` هم در روتر ماند (هم به‌دلیل همان وابستگی و هم چون
    یک تست ساختاری دقیقاً همین تابع و عبارت `LiveSession.course_id == identifier` را در
    متنِ `routers/attendance.py` جست‌وجو می‌کند).

کد **بایت‌به‌بایت** منتقل شده و منطق تغییر نکرده. `routers/attendance.py` همهٔ این نام‌ها
را re-export می‌کند، پس مسیرهای قبلی — از جمله importِ lazy در `main.py:643`
(`from routers.attendance import DuplicateSessionDate, _get_live_max_minutes, _now_str,
claim_live_session_for_finalize, finalize_live_session`) و `attendance.finalize_live_session`
در تست‌ها — دست‌نخورده کار می‌کنند.
"""

import datetime
import time as time_module

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Attendance, InstituteSettings, LiveSession, SessionLog


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _greg_date_from_ts(ts_epoch: float) -> str:
    return datetime.datetime.fromtimestamp(ts_epoch).strftime("%Y/%m/%d")


def _get_live_max_minutes(db: Session) -> int:
    settings = db.query(InstituteSettings).first()
    if settings and getattr(settings, "live_session_max_minutes", None):
        try:
            return int(settings.live_session_max_minutes)
        except Exception:
            return 180
    return 180


def _verify_live_course_teacher(db: Session, course, authorization, sub_role, action_label: str = "جلسه‌ی زنده") -> None:
    """فقط معلمِ مالکِ کلاس (یا ادمین/منشی) مجاز است (پیش‌فرض: کنترل جلسه‌ی زنده؛ action_label برای مسیرهای دیگر)."""
    if sub_role in ("admin", "secretary"):
        return
    from routers.reports import get_logged_in_teacher
    logged = get_logged_in_teacher(db, authorization)
    if not logged or logged.id != course.teacher_id:
        raise HTTPException(status_code=403, detail=f"شما مالک این کلاس نیستید و مجاز به مدیریت {action_label} نیستید")


def _upsert_attendance_row(db: Session, session_id: int, student_id: int, status: str, excused: bool):
    """FIX (F-S2): یک ردیف حضور به‌ازای هر (جلسه، دانش‌آموز) — بدون INSERT تکراری.

    قید یکتای `uq_attendance_session_student` برجاست و ردیف آرشیوشده هم سطرش را نگه می‌دارد، پس
    ویرایش جلسه/ثبت دوباره باید همان ردیف را احیا (revive) کند نه ردیف تازه بسازد. این تابع در
    حلقه‌های ثبت و ویرایش استفاده می‌شود تا رفتار یکی باشد.
    """
    row = (
        db.query(Attendance)
        .filter(Attendance.session_id == session_id, Attendance.student_id == student_id)
        .first()
    )
    if row is None:
        row = Attendance(session_id=session_id, student_id=student_id, status=status, excused=excused,
                         is_billed=False, is_deleted=False)
        db.add(row)
        return row
    row.status = status
    row.excused = excused
    row.is_deleted = False
    return row


def claim_live_session_for_finalize(db: Session, session_id: int, auto: bool = False) -> bool:
    """FIX F-C6(c): تسخیر اتمیک جلسه‌ی زنده برای finalize — مشترک بین مسیر دستی و ورکر auto-end.
    الگوی UPDATE مشروط (H8-P4): فقط یکی از دو مسیرِ هم‌زمان LIVE→FINALIZING را می‌گیرد؛ بازنده
    rowcount صفر می‌گیرد و نباید finalize را اجرا کند. بدون کامیت — finalize در همان تراکنش
    کامیت می‌کند، پس کرشِ میانی با rollback به LIVE برمی‌گردد و FINALIZINGِ گیرکرده نمی‌ماند."""
    values = {LiveSession.status: "FINALIZING"}
    if auto:
        values[LiveSession.ended_automatically] = True
    claimed_rows = (
        db.query(LiveSession)
        .filter(LiveSession.id == session_id, LiveSession.status == "LIVE")
        .update(values, synchronize_session=False)
    )
    db.flush()
    return claimed_rows == 1


def _live_canonical_date(course_id: int, started_at_ts) -> str:
    """Return the canonical date used by manual session registration."""
    start_ts = float(started_at_ts or time_module.time())
    date_str = _greg_date_from_ts(start_ts)
    from today_summary import jalali_date_string, parse_project_date
    day = parse_project_date(date_str)
    return jalali_date_string(day) if day is not None else date_str


def _existing_live_date_session(db: Session, course_id: int, started_at_ts):
    canonical_date = _live_canonical_date(course_id, started_at_ts)
    existing = (
        db.query(SessionLog)
        .filter(
            SessionLog.course_id == course_id,
            SessionLog.date == canonical_date,
            SessionLog.is_deleted == False,
        )
        .first()
    )
    return canonical_date, existing


def _close_live_as_duplicate(db: Session, live_id: int, duplicate: "DuplicateSessionDate") -> dict:
    """Close a duplicate live attempt without creating a second financial record."""
    db.query(LiveSession).filter(LiveSession.id == live_id).update(
        {LiveSession.status: "ENDED", LiveSession.end_time: _now_str()},
        synchronize_session=False,
    )
    db.commit()
    live = db.query(LiveSession).filter(LiveSession.id == live_id).first()
    return {
        "message": (
            f"جلسهٔ این کلاس در تاریخ {duplicate.date} قبلاً ثبت شده است؛ کلاس زنده بدون ثبت "
            f"جلسهٔ تکراری بسته شد. برای اصلاح حضور/غیاب یا مبالغ، همان جلسهٔ ثبت‌شده "
            f"(کد {duplicate.session_code}) را ویرایش کنید."
        ),
        "live_session_id": live_id,
        "ended_automatically": bool(live.ended_automatically) if live else False,
        "session_id": None,
        "session_code": None,
        "details": None,
        "duplicate_date": True,
        "existing_session_id": duplicate.session_id,
        "existing_session_code": duplicate.session_code,
        "duplicate_date_str": duplicate.date,
    }


class DuplicateSessionDate(Exception):
    """FIX (گروه۱/آیتم۱): جلسهٔ این کلاس در این تاریخ **قبلاً** ثبت شده است.

    چرا لازم است: `finalize_live_session` محاسبهٔ مالی را به `submit_session_and_calculate`
    واگذار می‌کند و گارد یکتایی (course, date) آن `HTTPException(409)` می‌دهد (attendance.py:477).
    پیش‌تر آن ۴۰۹ از `end_live` به کلاینت نشت می‌کرد ⇒ «پایان کلاس زنده» با خطا رد می‌شد و جلسهٔ
    زنده LIVE می‌ماند؛ ورکر auto-end هم هر ۶۰ ثانیه claim → ۴۰۹ → rollback → LIVE را تکرار می‌کرد
    (همان الگویی که F-C9 برای کلاس معلق حل کرد). این استثنا اطلاعات جلسهٔ موجود را حمل می‌کند تا
    فراخوان (end_live / ورکر) تصمیم درست بگیرد: بستن جلسهٔ زنده **بدون** ساخت SessionLog دوم و
    **بدون** هیچ اثر مالی، و ارجاع کاربر به همان جلسهٔ ثبت‌شده (مسیر ویرایش جلسه موجود است).

    نکته: این ۴۰۹ قفل optimistic-lock پروفایل نیست (آن در teachers.py/students.py است و فقط
    PUT پروفایل را می‌گیرد)؛ همان گارد «جلسهٔ تکراری در این تاریخ» است.
    """

    def __init__(self, course_id: int, date: str, session_id=None, session_code=None):
        super().__init__(f"جلسهٔ کلاس {course_id} در تاریخ {date} قبلاً ثبت شده است")
        self.course_id = course_id
        self.date = date
        self.session_id = session_id
        self.session_code = session_code
