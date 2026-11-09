# portal_data.py
# FIX(C6) — دادهٔ واقعی «تکالیف / آزمون‌ها / جلسات پیش‌رو» برای پورتال ولی و پورتال دانش‌آموز.
#
# باگی که این ماژول رفع می‌کند (همان باگ در **هر دو** پورتال بود):
#   در `routers/parent.py` (`GET /parent/child_profile`) و `routers/students.py`
#   (`GET /students/my_profile`) این سه لیست **قالبی و ساختگی** بودند:
#       عنوان تکلیف : «تمرین‌ها و حل مسائل فصل ۲ کتاب <نام کلاس>»
#       سررسید تکلیف: «۱۴۰۵/۰۶/۰۵»  ← تاریخ ثابت برای همهٔ خانواده‌ها
#       عنوان آزمون : «آزمون هماهنگ مستمر کلاسی <نام کلاس>»
#       تاریخ آزمون: «۱۴۰۵/۰۶/۱۰»  ← تاریخ ثابت
#       جلسهٔ پیش‌رو : «شنبه و دوشنبه‌ها» ساعت «۱۶:۰۰ الی ۱۷:۳۰» ← بی‌ربط به برنامهٔ واقعی کلاس
#   ⇒ هر ولی/دانش‌آموز — مستقل از واقعیت — یک تکلیف و یک آزمون قلابی می‌دید که هیچ معلمی
#   ثبت نکرده بود، و برنامهٔ هفتگی واقعی کلاس هم نمایش داده نمی‌شد. (اثر آموزشی/مالی:
#   والدین به تکلیفی که وجود ندارد رسیدگی می‌کردند و از تکالیف و آزمون‌های واقعی بی‌خبر می‌ماندند.)
#
# قرارداد پاسخ (کلیدها و نوع مقادیر) **بدون تغییر** نگه داشته شده تا کلاینت‌های منتشرشده
# (ParentPortalActivity / StudentPortalActivity با مدل `ParentProfileResponse`) نشکنند:
#   homework[i]          = {course_title: str, title: str, due_date: str, status: str}
#   exams[i]             = {course_title: str, title: str, date: str, max_score: int}
#   upcoming_sessions[i] = {course_title: str, date: str, time: str}
# نکتهٔ مهم مدل کلاینت: `max_score` در اپ **Int** است (Gson عدد اعشاری را رد می‌کند) ⇒ اینجا
# همیشه عدد صحیح برگردانده می‌شود.
import datetime
import math

from models import Course, Exam, ExamAttempt, Homework, HomeworkSubmission

# سقف ردیف‌ها در هر لیست — مثل سقف اعلان‌های پورتال (FIX(C1)) تا پاسخ برای خانوادهٔ
# پرونده‌سنگین سبک بماند.
PORTAL_ITEMS_LIMIT = 50

# برچسب فارسی وضعیت تکلیف برای نمایش در اپ. کد ناشناخته عیناً برگردانده می‌شود (حدس نمی‌زنیم).
_HOMEWORK_STATUS_LABELS = {
    "pending": "در انتظار تحویل",
    "submitted": "تحویل شده",
    "late": "با تأخیر تحویل شده",
    "graded": "تصحیح شده",
    "returned": "بازگشت داده شده",
}

# تیتر جایگزین برای کلاس‌های legacy که نامشان NULL است (هرگز «None» نمایش داده نشود).
_UNNAMED_COURSE = "کلاس بدون نام"


def _status_label(raw) -> str:
    """کد وضعیت تکلیف ⇒ برچسب فارسی؛ مقدار خالی/ناشناخته دست‌نخورده (بدون جعل)."""
    code = (raw or "").strip()
    if not code:
        return _HOMEWORK_STATUS_LABELS["pending"]
    return _HOMEWORK_STATUS_LABELS.get(code.lower(), code)


def _ordered_course_ids(db, student) -> list:
    """شناسهٔ کلاس‌های فعالِ دانش‌آموز (فقط ثبت‌نام‌های حذف‌نشده و کلاس‌های حذف‌نشده)."""
    from models import Enrollment  # lazy: جلوگیری از بار چرخه‌ای در import ماژول

    enrollments = db.query(Enrollment).filter(
        Enrollment.student_id == student.id,
        Enrollment.is_deleted == False,  # noqa: E712
    ).all()
    course_ids = []
    for en in enrollments:
        course = en.course if en.course else db.query(Course).filter(Course.id == en.course_id).first()
        if course is not None and course.is_deleted is not True and course.id not in course_ids:
            course_ids.append(course.id)
    return course_ids


def _course_titles(db, course_ids) -> dict:
    if not course_ids:
        return {}
    rows = db.query(Course).filter(Course.id.in_(course_ids)).all()
    return {c.id: (c.title or _UNNAMED_COURSE) for c in rows}


def build_portal_homework(db, student) -> list:
    """تکالیف واقعی ثبت‌شده توسط معلم‌ها برای کلاس‌های همین دانش‌آموز.

    وضعیت هر تکلیف **به‌ازای خود دانش‌آموز** محاسبه می‌شود: اگر تحویل داده باشد وضعیت
    تحویلش، وگرنه `pending` — دقیقاً همان منطق اندپوینت `GET /homework/student/list`.
    """
    course_ids = _ordered_course_ids(db, student)
    if not course_ids:
        return []
    titles = _course_titles(db, course_ids)

    rows = db.query(Homework).filter(Homework.course_id.in_(course_ids)) \
        .order_by(Homework.id.desc()).limit(PORTAL_ITEMS_LIMIT).all()

    submissions = {}
    if rows:
        for sub in db.query(HomeworkSubmission).filter(
            HomeworkSubmission.homework_id.in_([h.id for h in rows]),
            HomeworkSubmission.student_id == student.id,
        ).all():
            submissions[sub.homework_id] = sub

    result = []
    for hw in rows:
        submission = submissions.get(hw.id)
        result.append({
            "course_title": titles.get(hw.course_id, _UNNAMED_COURSE),
            "title": hw.title or "",
            "due_date": hw.due_date or "",
            "status": _status_label(submission.status if submission else "pending"),
        })
    return result


def build_portal_exams(db, student) -> list:
    """آزمون‌های واقعی کلاس‌های همین دانش‌آموز (فقط آزمون‌های منتشرشده/در جریان سیستم).

    `max_score` عمداً عدد صحیح است (قرارداد کلاینت: `ParentExamItem.max_score: Int`).
    """
    course_ids = _ordered_course_ids(db, student)
    if not course_ids:
        return []
    titles = _course_titles(db, course_ids)

    rows = db.query(Exam).filter(Exam.course_id.in_(course_ids)) \
        .order_by(Exam.id.desc()).limit(PORTAL_ITEMS_LIMIT).all()

    result = []
    for ex in rows:
        try:
            # گردکردن «نیم به بالا» (نه round بانکی پایتون): ۱۸.۵ باید ۱۹ نمایش داده شود،
            # چون نمرهٔ نیم‌نمره در آموزشگاه به سمت بالا خوانده می‌شود (۱۸.۵ ⇒ ۱۹).
            raw = float(ex.max_score if ex.max_score is not None else 20)
            max_score = int(math.floor(raw + 0.5))
        except (TypeError, ValueError):
            max_score = 20
        result.append({
            "course_title": titles.get(ex.course_id, _UNNAMED_COURSE),
            "title": ex.title or "",
            "date": ex.date or "",
            # FIX(contract): عمداً int — مدل Kotlin این فیلد را Int می‌خواند و Gson برای
            # مقدار اعشاری (۲۰.۰) استثنا می‌دهد؛ پس هرگز float فرستاده نمی‌شود.
            "max_score": max_score,
        })
    return result


def build_portal_upcoming_sessions(db, student) -> list:
    """برنامهٔ هفتگیِ واقعی کلاس‌های دانش‌آموز (روزها و ساعتِ ثبت‌شده روی خود کلاس).

    کلاس‌های حذف‌شده و تعلیق‌شده نمی‌آیند و کلاسی که هیچ روز/ساعتی برایش ثبت نشده
    در لیست نمی‌آید (به‌جای نمایش زمانِ ساختگی).
    """
    course_ids = _ordered_course_ids(db, student)
    if not course_ids:
        return []

    rows = db.query(Course).filter(Course.id.in_(course_ids), Course.is_suspended == False).all()  # noqa: E712
    rows.sort(key=lambda c: c.id)

    result = []
    for course in rows:
        days = (course.days_of_week or "").strip()
        time = (course.class_time or "").strip()
        if not days and not time:
            continue
        result.append({
            "course_title": course.title or _UNNAMED_COURSE,
            "date": days,
            "time": time,
        })
        if len(result) >= PORTAL_ITEMS_LIMIT:
            break
    return result


def build_portal_activity(db, student) -> dict:
    """هر سه لیست با یک فراخوانی (پورتال ولی و پورتال دانش‌آموز از همین استفاده می‌کنند)."""
    return {
        "homework": build_portal_homework(db, student),
        "exams": build_portal_exams(db, student),
        "upcoming_sessions": build_portal_upcoming_sessions(db, student),
    }
