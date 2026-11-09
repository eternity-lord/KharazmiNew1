import datetime
import json
import time as time_module

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dependencies import (
    check_admin_access,
    check_user_login,
    display_name,
    get_db,
    get_session_parent,
    get_session_student,
)
from models import (
    Attendance,
    Course,
    Enrollment,
    LiveSession,
    SessionLog,
    Student,
    Teacher,
    UserSession,
)
from schemas import (
    AttendanceItem,
    AttendanceLogRequest,
    AttendanceSubmitData,
    HistoryRequest,
    StudentAttendanceHistoryRequest,
)

# REFAC(P3a): آجرهای «کلاس زنده» به لایهٔ service رفتند — services/live_session.py.
# این import هم مصرفِ داخلیِ handlerهای همین فایل است و هم **بازصادرات**: ورکرِ
# auto-end در `main.py:643` این نام‌ها را lazy از `routers.attendance` می‌گیرد
# (DuplicateSessionDate، _get_live_max_minutes، _now_str، claim_live_session_for_finalize)
# و تست‌ها هم `attendance.finalize_live_session` را صدا می‌زنند؛ پس همهٔ مسیرهای قبلی
# دست‌نخورده کار می‌کنند. `finalize_live_session` و `_resolve_live_session_for_action`
# عمداً در همین روتر مانده‌اند (دلیلش در docstring ماژول service توضیح داده شده).
from services import session_submission
from services.live_session import (
    DuplicateSessionDate,
    _close_live_as_duplicate,
    _existing_live_date_session,
    _get_live_max_minutes,
    _greg_date_from_ts,
    _now_str,
    _upsert_attendance_row,
    _verify_live_course_teacher,
    claim_live_session_for_finalize,
)

# FIX (F-S4): قرارداد واحد وضعیت حضور — هم در schema و هم در مسیرهای داخلی (کلاس زنده).
from validation import validate_attendance_status

router = APIRouter()

# =========================================================================
# 🆕 لایه‌ی «کلاس زنده» (Live Sessions) — فقط وضعیت؛ بدون تغییر منطق مالی
# این توابع روی همان submit_session_and_calculate سوار می‌شوند و آن را با
# دیتای جمع‌شده‌ی لحظه‌ای صدا می‌زنند. هیچ محاسبه‌ای جایگزین نمی‌شود.
# =========================================================================


def _resolve_live_session_for_action(db: Session, identifier: int):
    """Resolve the live-session identifier used by teacher live endpoints.

    The public contract is ``LiveSession.id``. Older app builds sometimes sent
    ``course_id`` in the same path, so use that only when no live row has the
    identifier and only for an active session. Ownership is still checked by
    every caller after this lookup.
    """
    live = db.query(LiveSession).filter(LiveSession.id == identifier).first()
    if live is not None:
        return live
    return (
        db.query(LiveSession)
        .filter(
            LiveSession.course_id == identifier,
            LiveSession.status.in_(("LIVE", "FINALIZING")),
        )
        .order_by(desc(LiveSession.id))
        .first()
    )


def finalize_live_session(db: Session, live: LiveSession) -> dict:
    """
    پایان‌دادن یک جلسه‌ی زنده و واگذاری محاسبه‌ی مالی به مسیر موجود.
    فاقد هرگونه تغییر در محاسبه: فقط دیتای لحظه‌ای را وارد submit_session می‌کند.
    """
    course = db.query(Course).filter(Course.id == live.course_id).first()
    if not course:
        live.status = "ENDED"
        live.end_time = _now_str()
        live.ended_automatically = live.ended_automatically or False
        db.commit()
        return {"message": "جلسه پایان یافت (کلاس حذف شده بود)", "session_id": None, "session_code": None, "details": None}

    # دیتای لحظه‌ای جمع‌شده تا همین لحظه
    roster = {}
    raw = live.live_roster or "{}"
    try:
        roster = json.loads(raw) if raw else {}
    except Exception:
        roster = {}

    items = []
    skipped_ineligible = []
    for sid_str, entry in roster.items():
        if not isinstance(entry, dict):
            continue
        try:
            sid = int(sid_str)
        except Exception:
            continue
        # FIX (F-S4): راسترِ legacy ممکن است وضعیت غیرمجاز داشته باشد؛ به‌جای ۵۰۰ شدن بستن جلسه،
        # ردیف نامعتبر نادیده گرفته می‌شود (هیچ مالی برایش جابه‌جا نمی‌شود).
        try:
            validate_attendance_status(str(entry.get("status", "Present")))
        except ValueError:
            skipped_ineligible.append(sid)
            continue
        # FIX (F-S1): دانش‌آموز حذف‌شده/معلق/بدون عضویت فعال نباید در جلسه بیاید. راستر داده‌ی UI است،
        # پس اینجا ردیف نامواجد **فیلتر** می‌شود (به‌جای رد کل بستن جلسه) تا finalize کلاس زنده
        # به‌خاطر آرشیو شدن یک دانش‌آموز وسط کلاس شکست نخورد؛ اصولاً هیچ ردیفی از او نوشته نمی‌شود.
        student = (
            db.query(Student)
            .filter(Student.id == sid, Student.is_deleted == False, Student.is_suspended == False)
            .first()
        )
        enrolled = (
            db.query(Enrollment)
            .filter(Enrollment.student_id == sid, Enrollment.course_id == course.id,
                    Enrollment.is_deleted == False)
            .first()
        )
        if student is None or enrolled is None:
            skipped_ineligible.append(sid)
            continue
        items.append(
            AttendanceItem(
                student_id=sid,
                status=str(entry.get("status", "Present")),
                excused=bool(entry.get("excused", False)),
            )
        )

    # FIX F-C6(a): راستر خالی = صفر حاضر (نه همه حاضر) — fallback قبلیِ «همه حاضر» کل کلاس را شارژ می‌کرد.
    # FIX (F-S3): اما جلسه‌ی بدون هیچ ردیف مجاز **ساخته نمی‌شود** (هم‌سیاست با ثبت دستی): کلاس زنده
    # بسته می‌شود و SessionLog خالی ساخته نمی‌شود تا تاریخ کلاس قفل نشود.
    start_ts = float(live.started_at_ts or time_module.time())
    date_str = _greg_date_from_ts(start_ts)

    # FIX (گروه۱/آیتم۱): همان گارد یکتاییِ ثبت دستی، با تاریخ کانونیکال شمسی.
    # این pre-check علاوه بر ایندکس/گارد مسیر submit، خطای duplicate را پیش از هر
    # محاسبه یا تغییر کیف به یک پاسخ قابل‌مدیریت برای end_live تبدیل می‌کند.
    _canon_date, _existing = _existing_live_date_session(db, course.id, live.started_at_ts)
    if _existing is not None:
        raise DuplicateSessionDate(course.id, _canon_date, _existing.id, _existing.session_code)

    if not items:
        live.status = "ENDED"
        live.end_time = _now_str()
        db.commit()
        return {
            "message": "جلسه‌ی زنده پایان یافت؛ هیچ ردیف حضور قابل‌ثبتی نداشت و جلسه‌ای ثبت نشد.",
            "session_id": None,
            "session_code": None,
            "details": {"skipped_student_ids": skipped_ineligible},
        }

    data = AttendanceSubmitData(course_id=course.id, date=date_str, items=items)

    # فراخوانی مسیر موجود ثبت جلسه (بدون تغییر منطق مالی)
    result = submit_session_and_calculate(data=data, db=db, _system_caller="live_system")

    # ثبت زمان واقعی روی SessionLog برای نمایش در تاریخچه
    if result and result.get("session_id"):
        # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
        s = db.query(SessionLog).filter(SessionLog.is_deleted == False).filter(SessionLog.id == result["session_id"]).first()
        if s:
            s.start_time = datetime.datetime.fromtimestamp(start_ts).strftime("%H:%M")
            s.end_time = datetime.datetime.utcnow().strftime("%H:%M")
            db.commit()

    live.status = "ENDED"
    live.end_time = _now_str()
    db.commit()
    return result


class LiveRosterEntry(BaseModel):
    status: str = "Present"   # Present / Absent / Late
    excused: bool = False


class LiveStatusSave(BaseModel):
    items: dict  # {student_id: {status, excused}} — snapshot کامل یا جزئی


class LiveEndBody(BaseModel):
    date: str | None = None  # اختیاری؛ در غیر این صورت تاریخ شروع جلسه به‌کار می‌رود


@router.post("/attendance/{course_id}/start_live")
def start_live_session(
    course_id: int,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")

    # FIX H10: شروع جلسه‌ی زنده در کلاس معلق ممنوع.
    if course.is_suspended:
        raise HTTPException(status_code=403, detail="این کلاس معلق است و امکان شروع جلسه‌ی زنده برای آن وجود ندارد")
    if course.is_paused:
        raise HTTPException(status_code=403, detail="این کلاس موقتاً متوقف است و امکان شروع جلسه‌ی زنده وجود ندارد")

    _verify_live_course_teacher(db, course, authorization, sub_role)

    # جلوگیری از شروع مجدد: یک جلسه زنده فعال برای این کلاس نباید باز باشد
    existing = (
        db.query(LiveSession)
        .filter(LiveSession.course_id == course_id, LiveSession.status == "LIVE")
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"این کلاس هم‌اکنون در حال برگزاری است (جلسه زنده #{existing.id} از قبلاً باز است)",
        )

    now_ts = int(time_module.time())
    live = LiveSession(
        course_id=course.id,
        teacher_id=course.teacher_id,
        status="LIVE",
        start_time=_now_str(),
        started_at_ts=now_ts,
        ended_automatically=False,
        live_roster="{}",
    )
    db.add(live)
    db.commit()
    db.refresh(live)

    return {
        "message": "جلسه‌ی زنده شروع شد.",
        "live_session_id": live.id,
        "course_id": course.id,
        "status": live.status,
        "start_time": live.start_time,
        "started_at_ts": int(live.started_at_ts) if live.started_at_ts is not None else None,
        "max_minutes": _get_live_max_minutes(db),
    }


@router.post("/attendance/{session_id}/end_live")
def end_live_session(
    session_id: int,
    body: LiveEndBody | None = None,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login),
):
    # شناسه‌ی رسمی path، LiveSession.id است؛ برای buildهای قدیمی که course_id
    # را فرستاده‌اند فقط یک جلسه‌ی فعال resolve می‌شود.
    live = _resolve_live_session_for_action(db, session_id)
    if not live:
        raise HTTPException(status_code=404, detail="جلسه‌ی زنده یافت نشد")
    live_id = live.id
    live_course_id = live.course_id
    live_started_at_ts = live.started_at_ts

    course = db.query(Course).filter(Course.id == live_course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")

    # FIX M14: احراز قبل از هر جهش وضعیتی (403 بر 400-بسته‌شده مقدم است تا وضعیت به غریبه لو نرود
    # و ریکوئست غیرمجاز نتواند جلسه را ببندد).
    _verify_live_course_teacher(db, course, authorization, sub_role)

    # FIX F-C6(c): تسخیر اتمیک LIVE→FINALIZING — مشترک با ورکر auto-end (الگوی H8-P4).
    # فقط یکی از دو مسیرِ هم‌زمان (دستی/ورکر) finalize را اجرا می‌کند؛ بازنده rowcount صفر
    # می‌گیرد (همان پیام «از قبل بسته شده»). finalize در انتها وضعیت را ENDED می‌کند.
    if not claim_live_session_for_finalize(db, live_id):
        db.rollback()
        raise HTTPException(status_code=400, detail="این جلسه از قبل بسته شده است")
    db.refresh(live)  # UPDATE خام آبجکت را stale کرد؛ finalize باید وضعیت تازه ببیند.

    # FIX M14: تاریخ جلسه از سرور است (finalize از started_at_ts می‌سازد) — body.date عمداً نادیده
    # گرفته می‌شود و فقط برای سازگاری کلاینت‌های قدیمی در امضا مانده است.

    try:
        result = finalize_live_session(db, live)
    except Exception as exc:
        # finalize و submit در یک تراکنش هستند؛ هر خطا ابتدا rollback می‌شود تا
        # اثر مالی نیمه‌کاره باقی نماند. 409های مسیر ثبت جلسه فقط وقتی duplicate
        # محسوب می‌شوند که رکورد موجود واقعاً قابل مشاهده باشد (برای race هم).
        db.rollback()
        duplicate = exc if isinstance(exc, DuplicateSessionDate) else None
        if duplicate is None and isinstance(exc, HTTPException) and exc.status_code == 409:
            duplicate_date, existing = _existing_live_date_session(
                db, live_course_id, live_started_at_ts
            )
            if existing is not None:
                duplicate = DuplicateSessionDate(
                    live_course_id, duplicate_date, existing.id, existing.session_code
                )
        if duplicate is None and isinstance(exc, IntegrityError):
            duplicate_date, existing = _existing_live_date_session(
                db, live_course_id, live_started_at_ts
            )
            if existing is not None:
                duplicate = DuplicateSessionDate(
                    live_course_id, duplicate_date, existing.id, existing.session_code
                )
        if duplicate is not None:
            return _close_live_as_duplicate(db, live_id, duplicate)

        # شکست قابل‌اصلاح: جلسه‌ی زنده باید برای retry به LIVE برگردد.
        db.query(LiveSession).filter(LiveSession.id == live_id).update(
            {LiveSession.status: "LIVE"}, synchronize_session=False
        )
        db.commit()
        raise

    return {
        "message": "جلسه‌ی زنده پایان یافت و محاسبات مالی انجام شد.",
        "live_session_id": live.id,
        "ended_automatically": live.ended_automatically,
        "session_id": result.get("session_id"),
        "session_code": result.get("session_code"),
        "details": result.get("details"),
    }


@router.post("/attendance/{session_id}/cancel_live")
def cancel_live_session(
    session_id: int,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login),
):
    """Cancel a live session without attendance, tuition, wallet, or transactions."""
    live = _resolve_live_session_for_action(db, session_id)
    if not live:
        raise HTTPException(status_code=404, detail="جلسه‌ی زنده یافت نشد")
    live_id = live.id

    course = db.query(Course).filter(Course.id == live.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")
    # احراز هویت پیش از اعلام وضعیت/جهش؛ همان سیاست end_live.
    _verify_live_course_teacher(db, course, authorization, sub_role)

    # فقط LIVE قابل لغو است؛ UPDATE مشروط، دو درخواست هم‌زمان را اتمیک می‌کند.
    if live.status == "CANCELLED":
        return {
            "message": "کلاس زنده قبلاً لغو شده بود؛ هیچ اثر مالی یا حضور و غیابی ثبت نشده است.",
            "live_session_id": live_id,
            "status": "CANCELLED",
        }
    if live.status != "LIVE":
        raise HTTPException(status_code=409, detail="این جلسه قبلاً پایان یافته و قابل لغو نیست")

    cancelled = (
        db.query(LiveSession)
        .filter(LiveSession.id == live_id, LiveSession.status == "LIVE")
        .update(
            {
                LiveSession.status: "CANCELLED",
                LiveSession.end_time: _now_str(),
                # snapshot لحظه‌ای نیز برای یک جلسه‌ی لغوشده قابل استفاده نیست.
                LiveSession.live_roster: "{}",
            },
            synchronize_session=False,
        )
    )
    if cancelled != 1:
        db.rollback()
        latest = db.query(LiveSession).filter(LiveSession.id == live_id).first()
        if latest is not None and latest.status == "CANCELLED":
            return {
                "message": "کلاس زنده قبلاً لغو شده بود؛ هیچ اثر مالی یا حضور و غیابی ثبت نشده است.",
                "live_session_id": live_id,
                "status": "CANCELLED",
            }
        raise HTTPException(status_code=409, detail="این جلسه هم‌زمان بسته شد و دیگر قابل لغو نیست")
    db.commit()
    return {
        "message": "کلاس زنده لغو شد و هیچ شهریه، حضور و غیاب یا تراکنشی ثبت نشد.",
        "live_session_id": live_id,
        "status": "CANCELLED",
    }


@router.post("/attendance/{session_id}/live_status")
def save_live_status(
    session_id: int,
    body: LiveStatusSave,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login),
):
    live = _resolve_live_session_for_action(db, session_id)
    if not live:
        raise HTTPException(status_code=404, detail="جلسه‌ی زنده یافت نشد")
    if live.status != "LIVE":
        raise HTTPException(status_code=400, detail="جلسه‌ی زنده دیگر فعال نیست")

    course = db.query(Course).filter(Course.id == live.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")
    _verify_live_course_teacher(db, course, authorization, sub_role)

    # ادغام با رکورد قبلی (snapshot جزئی قابل قبول است)
    existing = {}
    try:
        existing = json.loads(live.live_roster or "{}") if live.live_roster else {}
    except Exception:
        existing = {}
    for sid, entry in body.items.items():
        if isinstance(entry, dict):
            # FIX (F-S4): وضعیت نامعتبر نباید وارد راستر شود (وگرنه در finalize بی‌صدا/خطا می‌شد).
            try:
                _status = validate_attendance_status(str(entry.get("status", "Present")))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
            existing[str(sid)] = {
                "status": _status,
                "excused": bool(entry.get("excused", False)),
            }
    live.live_roster = json.dumps(existing, ensure_ascii=False)
    db.commit()

    return {"message": "وضعیت لحظه‌ای ذخیره شد.", "count": len(existing)}


@router.get("/attendance/live/current")
def get_current_live_session(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login),
):
    """جلسه‌ی زنده‌ی فعلیِ معلمِ لاگین‌شده (برای رزومه/تایمر در داشبورد معلم)."""
    if sub_role in ("admin", "secretary"):
        return None
    from routers.reports import get_logged_in_teacher
    logged = get_logged_in_teacher(db, authorization)
    if not logged:
        return None
    live = (
        db.query(LiveSession)
        .filter(LiveSession.teacher_id == logged.id, LiveSession.status == "LIVE")
        .order_by(desc(LiveSession.id))
        .first()
    )
    if not live:
        return None
    course = db.query(Course).filter(Course.id == live.course_id).first()
    return {
        "live_session_id": live.id,
        "course_id": live.course_id,
        "class_title": course.title if course else "",
        "course_code": course.code if course else "",
        "status": live.status,
        "start_time": live.start_time,
        "started_at_ts": int(live.started_at_ts) if live.started_at_ts is not None else None,
        "max_minutes": _get_live_max_minutes(db),
    }


@router.post("/attendance/get")
def get_class_attendance(req: AttendanceLogRequest, db: Session = Depends(get_db), authorization: str | None = Header(None), sub_role: str = Depends(check_user_login)):
    # دریافت لیست غیبت‌های ثبت شده برای یک کلاس در تاریخ خاص
    course = db.query(Course).filter(Course.id == req.course_id).first()
    if not course:
        return []
    # FIX (L14/Y3): گزارش کلاس — ادمین/منشی + معلمِ مالک کلاس (الگوی audit-v2/#11). شاگرد/ولی 403.
    if sub_role not in ("admin", "secretary"):
        if sub_role != "teacher":
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اطلاعات این کلاس نیستید")
        from routers.reports import get_logged_in_teacher  # lazy (جلوگیری از import چرخه‌ای)
        _me = get_logged_in_teacher(db, authorization)
        if not _me or course.teacher_id != _me.id:
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اطلاعات این کلاس نیستید")
    # FIX (F-C4): تاریخ کانونیکال شمسی با مبدل مرکزی H3 — قبلاً رشته‌ی خام کلاینت مقایسه
    # می‌شد و ورودی میلادی ساکت خالی برمی‌گرداند. نامعتبر → [] (لحن read-path، مثل «جلسه‌ای نیست»).
    from today_summary import jalali_date_string, parse_project_date  # lazy، مثل submit_session
    _qday = parse_project_date(req.date)
    if _qday is None:
        return []
    session = (
        # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
        db.query(SessionLog).filter(SessionLog.is_deleted == False)
        .filter(SessionLog.course_id == req.course_id, SessionLog.date == jalali_date_string(_qday))
        .first()
    )
    if not session:
        return []

    atts = db.query(Attendance).filter(
        Attendance.session_id == session.id, Attendance.is_deleted == False,  # FIX (F-S2)
    ).all()
    result = []
    for a in atts:
        st = db.query(Student).filter(Student.id == a.student_id, Student.is_deleted == False).first()
        st_name = display_name(st, "نامشخص") if st else "حذف شده"
        result.append(
            {
                "student_id": a.student_id,
                "name": st_name,
                "status": a.status,
            }
        )
    return result


@router.post("/attendance/submit_session")
def submit_session_and_calculate(
    data: AttendanceSubmitData, db: Session = Depends(get_db), authorization: str | None = Header(None),
    sub_role: str = Depends(check_user_login), _system_caller: str | None = None
):
    # REFAC(P3b): بدنهٔ ۲۴۳ خطیِ دامنه (ثبت SessionLog، سهم‌ها، شارژ کیف پول،
    # جریمهٔ غیبت، تراکنش‌ها و اعلان‌ها) به `services/session_submission.py` رفت.
    # این پوسته فقط لایهٔ HTTP است: همان امضا، همان تزریق‌ها و همان پاسخ JSON.
    # چرا نام تابع این‌جا می‌ماند و تابع سرویس را صدا می‌زند: تست‌ها و
    # scripts/run_financial_audit.py این handler را مستقیم (گاهی پوزیشنال) صدا
    # می‌زنند و finalize_live_session هم با `_system_caller="live_system"` از آن
    # استفاده می‌کند؛ پس `routers.attendance.submit_session_and_calculate` باید
    # همچنان همان قرارداد را داشته باشد.
    return session_submission.submit_session_and_calculate(
        data, db, authorization, sub_role, _system_caller
    )


@router.post("/attendance/get_history")
def get_history(req: HistoryRequest, db: Session = Depends(get_db), authorization: str | None = Header(None), sub_role: str = Depends(check_user_login)):
    course = db.query(Course).filter(Course.id == req.course_id).first()
    if not course:
        return []
    # FIX (L14/Y3): گزارش کلاس — ادمین/منشی + معلمِ مالک کلاس (الگوی audit-v2/#11). شاگرد/ولی 403.
    if sub_role not in ("admin", "secretary"):
        if sub_role != "teacher":
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اطلاعات این کلاس نیستید")
        from routers.reports import get_logged_in_teacher  # lazy (جلوگیری از import چرخه‌ای)
        _me = get_logged_in_teacher(db, authorization)
        if not _me or course.teacher_id != _me.id:
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اطلاعات این کلاس نیستید")
    sessions = (
        # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
        db.query(SessionLog).filter(SessionLog.is_deleted == False)
        .filter(SessionLog.course_id == req.course_id)
        .order_by(desc(SessionLog.id))
        .all()
    )

    result = []
    for s in sessions:
        # FIX: H6(A2) - هزینه‌ی کل جلسه = مبالغ قراردادی + جریمه‌ی غایبین غیرموجه.
        total_session_cost = (
            (s.final_teacher_cost or 0) + (s.final_institute_share or 0)
            + (s.absent_penalty_teacher or 0) + (s.absent_penalty_institute or 0)
        )

        result.append(
            {
                "session_id": s.id,
                "date": s.date,
                "attendees": s.attendee_count,
                "cost_per_student": s.cost_per_student,
                "total_cost": total_session_cost,
                "status": s.status or "Finished",
                # 🆕 زمان واقعی شروع/پایان جلسه (برای کلاس‌های زنده)
                "start_time": s.start_time or getattr(s, "time", None) or "",
                "end_time": s.end_time or "",
            }
        )
    return result


@router.post("/attendance/student_history")
def get_student_attendance_history(req: StudentAttendanceHistoryRequest, db: Session = Depends(get_db), authorization: str | None = Header(None), sub_role: str = Depends(check_user_login)):
    student = db.query(Student).filter(Student.id == req.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

    course = db.query(Course).filter(Course.id == req.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")

    # FIX (audit-v2/#11): IDOR خواندن — ادمین/منشی + معلمِ مالک کلاس (ClassDetail معلم‌ها این را صدا
    # می‌زند) + خودِ شاگرد/ولی. انحراف از spec: معلمِ مالک اضافه شد وگرنه مسیر مشروع معلم می‌شکست.
    # 404ها عمداً قبل‌اند (الگوی H16: گارد بعد از 404).
    if sub_role not in ("admin", "secretary"):
        if sub_role == "teacher":
            from routers.reports import get_logged_in_teacher
            _me = get_logged_in_teacher(db, authorization)
            if not _me or course.teacher_id != _me.id:
                raise HTTPException(status_code=403, detail="شما مجاز به مشاهده سوابق این کلاس نیستید")
        elif sub_role in ("student", "parent"):
            _parts = (authorization or "").split()
            _tok = _parts[1] if len(_parts) == 2 and _parts[0].lower() == "bearer" else None
            _sess = db.query(UserSession).filter(UserSession.token == _tok).first() if _tok else None
            _own = get_session_student(db, _sess) if sub_role == "student" else get_session_parent(db, _sess)
            if not _own:
                raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
            if _own.id != req.student_id:
                raise HTTPException(status_code=403, detail="شما مجاز به مشاهده سوابق این دانش‌آموز نیستید")
        else:
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده سوابق حضور نیستید")

    # واکشی تمامی جلسات این کلاس
    # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
    sessions = db.query(SessionLog).filter(SessionLog.is_deleted == False).filter(SessionLog.course_id == req.course_id).order_by(SessionLog.date.asc()).all()

    total_sessions = len(sessions)
    present_count = 0
    absent_count = 0
    history_list = []

    for s in sessions:
        att = db.query(Attendance).filter(
            Attendance.session_id == s.id, Attendance.student_id == req.student_id,
            Attendance.is_deleted == False,   # FIX (F-S2)
        ).first()
        status_text = "ثبت نشده"
        if att:
            if att.status in ["Present", "Late"]:
                present_count += 1
                status_text = "حاضر" if att.status == "Present" else "تاخیر"
            elif att.status == "Absent":
                absent_count += 1
                status_text = "غایب موجه" if att.excused else "غایب غیرموجه"

        history_list.append({
            "session_id": s.id,
            "date": s.date,
            "status": status_text,
            "session_cost": s.cost_per_student,
            "attendee_count": s.attendee_count
        })

    # FIX (O-S2 — کشف‌شده حین fix): سطر قبلی `present_count.float()` بود که در پایتون همیشه AttributeError می‌داد ⇒ هر کلاس با ≥۱ جلسه این endpoint را ۵۰۰ می‌کرد (سطر بعدی همان محاسبه‌ی درست را داشت و بر روی سطر خراب سایه می‌انداخت) ⇒ سطر مرده حذف شد.
    # در کاتلین تبدیل به فلوت داریم، در پایتون مستقیم تقسیم میکنیم
    rate = (present_count / total_sessions * 100) if total_sessions > 0 else 100.0

    return {
        "student_name": display_name(student, "نامشخص"),
        "course_title": course.title,
        "course_code": course.code,
        "total_sessions": total_sessions,
        "present_count": present_count,
        "absent_count": absent_count,
        "attendance_rate": round(rate, 2),
        "attendance_history": history_list
    }

@router.get("/attendance/session/{session_code}")
def get_session_details(session_code: int, db: Session = Depends(get_db), authorization: str | None = Header(None), sub_role: str = Depends(check_user_login)):
    # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
    session = db.query(SessionLog).filter(SessionLog.is_deleted == False).filter(SessionLog.session_code == session_code).first()
    if not session:
        raise HTTPException(status_code=404, detail="جلسه مورد نظر یافت نشد")

    course = db.query(Course).filter(Course.id == session.course_id).first()
    # FIX (audit-v2/#11): IDOR خواندن — ادمین/منشی + معلمِ مالک کلاس (AttendanceActivity هم از Main هم
    # از TeacherDashboard باز می‌شود). شاگرد/ولی مسیر مشروعی ندارند (پورتال‌ها جزئیات جلسه نمی‌بینند).
    if sub_role not in ("admin", "secretary"):
        if sub_role != "teacher":
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده جزئیات این جلسه نیستید")
        from routers.reports import get_logged_in_teacher
        _me = get_logged_in_teacher(db, authorization)
        if not _me or not course or course.teacher_id != _me.id:
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده جزئیات این جلسه نیستید")
    t_name = ""
    if course and course.teacher:
        t_name = display_name(course.teacher, "نامشخص")

    atts = db.query(Attendance).filter(
        Attendance.session_id == session.id, Attendance.is_deleted == False,  # FIX (F-S2)
    ).all()
    items = []
    for a in atts:
        student = db.query(Student).filter(Student.id == a.student_id, Student.is_deleted == False).first()
        st_name = display_name(student, "نامشخص") if student else "حذف شده"
        items.append({
            "student_id": a.student_id,
            "name": st_name,
            "status": a.status,
            "excused": a.excused,
            "student_code": student.student_code if student else None
        })

    return {
        "session_id": session.id,
        "session_code": session.session_code,
        "course_id": session.course_id,
        "class_title": course.title if course else "کلاس حذف شده",
        "class_code": course.code if course else "---",
        "teacher_name": t_name,
        "date": session.date,
        "attendee_count": session.attendee_count,
        "items": items
    }

@router.put("/attendance/session/{session_code}")
def edit_past_session(
    session_code: int,
    data: AttendanceSubmitData,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
    sub_role: str = Depends(check_user_login)
):
    # REFAC(P3b): بدنهٔ دامنه به `services/session_submission.py` رفت؛ این پوسته فقط لایهٔ HTTP است
    #     # (همان امضا، همان تزریق‌ها، همان پاسخ JSON). نام تابع عمداً این‌جا می‌ماند:
    #     # تست‌ها و اسکریپت‌ها این handler را مستقیم — گاهی با آرگومان پوزیشنال —
    #     # صدا می‌زنند، پس `routers.attendance.edit_past_session` باید همان قرارداد قبلی را داشته باشد.
    return session_submission.edit_past_session(session_code, data, db, authorization, sub_role)

@router.delete("/attendance/session/{session_code}")
def delete_session_endpoint(
    session_code: int,
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)
):
    # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
    session = db.query(SessionLog).filter(SessionLog.is_deleted == False).filter(SessionLog.session_code == session_code).first()
    if not session:
        raise HTTPException(status_code=404, detail="جلسه مورد نظر یافت نشد")

    # FIX (audit-v2/critical-8-قدم۱): دقیقاً همان گیت settled ویرایش (H6-FOLLOWUP-2 + H8-gap) — جلسه‌ی
    # تسویه‌شده قابل حذف نیست (پول رفته + payout/رد Settlement). قبل از reverse مخرب.
    settled_exists = db.query(Attendance.id).filter(
        Attendance.session_id == session.id,
        Attendance.is_billed == True,
        Attendance.is_deleted == False,   # FIX (F-S2): ردیف آرشیوشده جلسه‌ی فعال را قفل نمی‌کند.
    ).first()
    if settled_exists or session.is_penalty_settled:
        raise HTTPException(
            status_code=409,
            detail="این جلسه قبلاً با معلم تسویه شده و قابل حذف نیست؛ برای اصلاح، ابتدا با بخش مالی/تسویه هماهنگ کنید",
        )

    from dependencies import reverse_session_financial_impacts
    # FIX (audit-v2/critical-8-قدم۲): اتمیک با is_deleted پایین (تک‌کامیت انتهای تابع) — دیگر پنجره‌ی
    # «کرش وسط = جلسه‌ی فعال بدون شارژ/حضور» وجود ندارد. edit عمداً دست‌نخورده (پیش‌فرض True).
    reverse_session_financial_impacts(session.id, db, commit=False)

    # FIX: Bug 14 - archived financial rows still reference this session; retain the parent row too.
    session.is_deleted = True
    db.commit()
    return {"message": "جلسه با موفقیت حذف گردید و ترازها اصلاح شدند."}

# FIX H18-interim: شمارنده‌ی حافظه‌ای ضد brute-force برای qr_check-in (۵ تلاش / ۵ دقیقه / شاگرد).
# عمداً جدول LoginAttempt (H14) استفاده نشد: آن جدول معنای «تلاش لاگین» دارد و این اندپوینت
# لاگین نیست؛ شمارنده‌ی حافظه‌ای بدون مایگریشن کافی است (با ری‌استارت صفر می‌شود — موقتی).
_QR_CHECKIN_ATTEMPTS: dict = {}
_QR_CHECKIN_MAX_ATTEMPTS = 5
_QR_CHECKIN_WINDOW_SECONDS = 300


def _qr_checkin_allowed(student_id: int) -> bool:
    now = time_module.time()
    recent = [t for t in _QR_CHECKIN_ATTEMPTS.get(student_id, []) if now - t < _QR_CHECKIN_WINDOW_SECONDS]
    if len(recent) >= _QR_CHECKIN_MAX_ATTEMPTS:
        _QR_CHECKIN_ATTEMPTS[student_id] = recent
        return False
    recent.append(now)
    _QR_CHECKIN_ATTEMPTS[student_id] = recent
    return True


class QrCheckInRequest(BaseModel):
    session_code: int
    token: str
    expires_at: float  # UNIX timestamp
    salt: str

# FIX H18-interim (سخت‌سازی موقت، نه بازطراحی):
# - فیلدهای token/salt/expires_at این درخواست client-supplied و اعتبارسنجی‌نشده‌اند؛ هیچ مولد QR
#   واقعی (سرور یا اپ) در این ورک‌اسپیس وجود ندارد، پس این فیلدها هیچ تضمین امنیتی نمی‌دهند.
# - تا مشخص شدن وضعیت فیچر (مصرف‌کننده‌ی واقعی دارد یا باید بازطراحی/حذف شود)، فقط:
#   (۱) جلسه باید مال همان روز باشد (چک سروری با ساعت سرور)، (۲) ریت‌لیمیت حافظه‌ای
#   ۵ تلاش در ۵ دقیقه به‌ازای هر شاگرد، ضد brute-force روی session_code ترتیبی.
@router.post("/attendance/qr_check-in")
def qr_student_check_in(
    req: QrCheckInRequest,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(check_user_login)
):
    session = db.query(UserSession).filter(UserSession.token == authorization.split()[1]).first()
    own = get_session_student(db, session) if session and session.sub_role == "student" else get_session_parent(db, session)
    if not own:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
    student_id = own.id
    # FIX H10: حساب معلق (دانش‌آموز یا ولیِ دانش‌آموز معلق) نمی‌تواند حضور QR ثبت کند.
    if own.is_suspended:
        raise HTTPException(status_code=403, detail="حساب شما معلق است و امکان ثبت حضور وجود ندارد")

    # FIX H18-interim: چک expires_at کلاینت حذف شد — کاملاً client-controlled و قابل دور زدن بود
    # (هر تاریخ آینده‌ای قبول می‌شد) و حس امنیت کاذب می‌داد؛ جایگزین واقعی: چک همان‌روز + ریت‌لیمیت.
    if not _qr_checkin_allowed(student_id):
        raise HTTPException(status_code=429, detail="تعداد تلاش‌های ثبت حضور بیش از حد مجاز است؛ چند دقیقه بعد دوباره تلاش کنید")

    sess = db.query(SessionLog).filter(SessionLog.session_code == req.session_code).first()
    if not sess:
        raise HTTPException(status_code=404, detail="جلسه کلاسی یافت نشد")
    # FIX H18-interim: فقط جلسه‌ی همان روز (با ساعت/تقویم سرور، نه ورودی کلاینت).
    from today_summary import parse_project_date  # lazy، هم‌مثل analytics/automation
    if parse_project_date(sess.date) != datetime.datetime.utcnow().date():
        raise HTTPException(status_code=403, detail="این کد QR فقط برای جلسه‌ی همان روز معتبر است")

    # FIX (F-S1): دانش‌آموز آرشیوشده اجازه‌ی هیچ مسیر حضور (از جمله QR) ندارد — هم‌سیاست با ثبت جلسه.
    if own.is_deleted:
        raise HTTPException(status_code=403, detail="حساب شما حذف/آرشیو شده است و امکان ثبت حضور وجود ندارد")

    # FIX (F-S1): فقط ثبت‌نام **فعال** مجاز است (ردیف آرشیوشده مثل نبودن ثبت‌نام است).
    enrolled = db.query(Enrollment).filter(
        Enrollment.student_id == student_id,
        Enrollment.course_id == sess.course_id,
        Enrollment.is_deleted == False,
    ).first()
    if not enrolled:
        raise HTTPException(status_code=403, detail="شما در این کلاس ثبت‌نام نکرده‌اید و مجاز به حضور نیستید")

    # FIX (F-S2): فقط ردیف **فعال** معیار «قبلاً ثبت شده» است؛ ردیف آرشیوشده مثل نبودن آن است.
    existing_att = db.query(Attendance).filter(
        Attendance.session_id == sess.id,
        Attendance.student_id == student_id,
        Attendance.is_deleted == False,
    ).first()
    if existing_att and existing_att.status in ["Present", "Late"]:
        raise HTTPException(status_code=400, detail="حضور شما قبلاً در این جلسه ثبت شده است")

    if existing_att:
        existing_att.status = "Present"
    else:
        # ردیف آرشیوشده‌ی همین (جلسه، دانش‌آموز) احیا می‌شود، نه INSERT تازه (قید یکتا).
        _upsert_attendance_row(db, sess.id, student_id, "Present", False)

    db.commit()

    st = db.query(Student).filter(Student.id == student_id, Student.is_deleted == False).first()
    if st:
        from dependencies import NotificationService, ensure_student_shadow_users
        if st.user_id is None:
            ensure_student_shadow_users(db, st)
        NotificationService.send_notification(
            db=db,
            recipient_user_id=st.user_id,
            recipient_role="student",
            type="attendance",
            title="🟢 ثبت حضور موفقیت‌آمیز با QR",
            body=f"حضور شما در جلسه شماره #{req.session_code} با اسکن کد QR ثبت شد."
        )

    return {"message": "حضور شما با موفقیت با اسکن کد QR ثبت گردید"}


# =========================================================================
# 🆕 Endpoint های ادمین/منشی برای «کلاس‌های زنده»
# هر دو فقط برای admin/secretary؛ معلم از آن‌ها استفاده نمی‌کند.
# =========================================================================

@router.get("/admin/live_sessions")
def get_admin_live_sessions(
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login),
):
    if sub_role not in ("admin", "secretary"):
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای مشاهده‌ی کلاس‌های زنده را ندارید")

    lives = (
        db.query(LiveSession)
        .filter(LiveSession.status == "LIVE")
        .order_by(LiveSession.id)
        .all()
    )
    now_ts = time_module.time()
    result = []
    for live in lives:
        course = db.query(Course).filter(Course.id == live.course_id).first()
        teacher = db.query(Teacher).filter(Teacher.id == live.teacher_id).first() if live.teacher_id else None

        # شمارش کل اعضای کلاس برای تعیین «نامشخص»
        total_enrolled = (
            # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
            db.query(Enrollment).filter(Enrollment.is_deleted == False)
            .filter(Enrollment.course_id == live.course_id)
            .count()
        )
        roster = {}
        try:
            roster = json.loads(live.live_roster or "{}") if live.live_roster else {}
        except Exception:
            roster = {}
        present = sum(1 for e in roster.values() if isinstance(e, dict) and str(e.get("status", "")) in ("Present", "Late"))
        absent = sum(1 for e in roster.values() if isinstance(e, dict) and str(e.get("status", "")) == "Absent")
        undetermined = max(0, total_enrolled - present - absent)

        started_ts = live.started_at_ts or int(live.started_at_ts or 0)
        elapsed_min = 0
        if started_ts:
            elapsed_min = int((now_ts - started_ts) / 60) if now_ts > started_ts else 0

        result.append({
            "live_session_id": live.id,
            "course_id": live.course_id,
            "class_title": course.title if course else "کلاس حذف شده",
            "course_code": course.code if course else "",
            "teacher_name": display_name(teacher, "نامشخص"),
            "start_time": live.start_time,
            "started_at_ts": int(live.started_at_ts) if live.started_at_ts is not None else None,
            "elapsed_minutes": elapsed_min,
            "total_enrolled": total_enrolled,
            "present": present,
            "absent": absent,
            "undetermined": undetermined,
        })
    return result


@router.get("/admin/live_sessions/{session_id}/roster")
def get_admin_live_session_roster(
    session_id: int,
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login),
):
    if sub_role not in ("admin", "secretary"):
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای مشاهده‌ی کلاس‌های زنده را ندارید")

    live = db.query(LiveSession).filter(LiveSession.id == session_id).first()
    if not live:
        raise HTTPException(status_code=404, detail="جلسه‌ی زنده یافت نشد")

    course = db.query(Course).filter(Course.id == live.course_id).first()
    teacher = db.query(Teacher).filter(Teacher.id == live.teacher_id).first() if live.teacher_id else None

    roster = {}
    try:
        roster = json.loads(live.live_roster or "{}") if live.live_roster else {}
    except Exception:
        roster = {}

    # لیست کامل اعضای کلاس (ثبت‌نام‌شده)
    enrollments = (
        # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
        db.query(Enrollment).filter(Enrollment.is_deleted == False)
        .filter(Enrollment.course_id == live.course_id)
        .order_by(Enrollment.id)
        .all()
    )

    students_list = []
    for en in enrollments:
        st = db.query(Student).filter(Student.id == en.student_id, Student.is_deleted == False).first()
        if not st:
            continue
        entry = roster.get(str(st.id), {})
        if isinstance(entry, dict):
            status = str(entry.get("status", ""))
            excused = bool(entry.get("excused", False))
        else:
            status = ""
            excused = False
        students_list.append({
            "student_id": st.id,
            "student_name": display_name(st, "نامشخص"),
            "status": status if status else "UNSET",  # Present/Late/Absent/UNSET
            "excused": excused,
            "student_mobile": st.student_mobile or "",
            "parent_mobile": st.parent_mobile or "",
        })

    started_ts = live.started_at_ts or 0
    elapsed_min = int((time_module.time() - started_ts) / 60) if started_ts else 0

    return {
        "live_session_id": live.id,
        "course_id": live.course_id,
        "class_title": course.title if course else "کلاس حذف شده",
        "course_code": course.code if course else "",
        "teacher_name": display_name(teacher, "نامشخص"),
        "start_time": live.start_time,
        "started_at_ts": int(live.started_at_ts) if live.started_at_ts is not None else None,
        "elapsed_minutes": max(0, elapsed_min),
        "total_enrolled": len(students_list),
        "present": sum(1 for s in students_list if s["status"] in ("Present", "Late")),
        "absent": sum(1 for s in students_list if s["status"] == "Absent"),
        "undetermined": sum(1 for s in students_list if s["status"] == "UNSET"),
        "students": students_list,
    }
