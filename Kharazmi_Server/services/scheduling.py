"""لایهٔ service — منطق زمان‌بندی کلاس (REFAC P3a).

چرا این ماژول: `parse_time_to_minutes`/`days_overlap`/`check_scheduling_conflicts` قواعد
خالصِ «تداخل نوبت هفتگی» هستند و هیچ وابستگی‌ای به HTTP ندارند، ولی وسط `routers/classes.py`
تعریف شده بودند و `routers/admin.py` هم برای استفاده از آن‌ها مجبور بود از **روترِ دیگر**
import کند (`from routers.classes import check_scheduling_conflicts`). حالا قاعدهٔ زمان‌بندی
یک منبع یگانه دارد و روترها فقط مصرف‌کننده‌اند.

کد **بایت‌به‌بایت** از `routers/classes.py` منتقل شده است؛ هیچ منطقی تغییر نکرده
(رفتار یکسان، فقط جای تعریف عوض شده). `routers/classes.py` همان نام‌ها را re-export
می‌کند تا همهٔ مسیرهای import قبلی کار کنند.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Course


def parse_time_to_minutes(time_str):
    # E.g. "16:00-17:30" or "16:00" or "16"
    try:
        time_str = time_str.strip().replace(" ", "")
        if "-" in time_str:
            parts = time_str.split("-")
            start_str = parts[0]
            end_str = parts[1]
        else:
            start_str = time_str
            end_str = None

        def to_min(t_s):
            if ":" in t_s:
                h, m = t_s.split(":")
                return int(h) * 60 + int(m)
            return int(t_s) * 60

        start_m = to_min(start_str)
        if end_str:
            end_m = to_min(end_str)
        else:
            end_m = start_m + 90 # پیش‌فرض ۹۰ دقیقه برای جلسه کلاسی تک‌ساعته
        return start_m, end_m
    except Exception:
        return None


def days_overlap(day1, day2):
    day1 = day1.strip()
    day2 = day2.strip()
    if day1 == day2:
        return True

    even_days = {"شنبه", "دوشنبه", "چهارشنبه", "زوج"}
    odd_days = {"یکشنبه", "سه‌شنبه", "پنج‌شنبه", "فرد"}

    if day1 in even_days and day2 in even_days:
        if day1 == "زوج" or day2 == "زوج" or day1 == day2:
            return True
    if day1 in odd_days and day2 in odd_days:
        if day1 == "فرد" or day2 == "فرد" or day1 == day2:
            return True

    return False


def check_scheduling_conflicts(db: Session, teacher_id: int, days_of_week: str,
                               class_time: str, exclude_course_id: int | None = None):
    """Return active classes which overlap the proposed weekly slot."""
    proposed = parse_time_to_minutes(class_time)
    if not proposed:
        raise HTTPException(status_code=400, detail="ساعت کلاس معتبر نیست")
    result = []
    for other in db.query(Course).filter(
        Course.teacher_id == teacher_id, Course.is_deleted == False,
        Course.is_suspended == False, Course.is_paused == False
    ).all():
        if exclude_course_id and other.id == exclude_course_id:
            continue
        if not days_overlap(other.days_of_week or "", days_of_week or ""):
            continue
        other_time = parse_time_to_minutes(other.class_time or "")
        if other_time and proposed[0] < other_time[1] and other_time[0] < proposed[1]:
            result.append(other)
    return result
