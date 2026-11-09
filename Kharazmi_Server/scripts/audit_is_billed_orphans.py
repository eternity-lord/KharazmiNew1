"""
ممیزی is_billed یتیم — فقط گزارش، بدون هیچ تغییری (حتی با --apply).

پس‌زمینه: قبل از فیکس H6، باگ edit_past_session می‌توانست Attendance.is_billed را True کند
بدون اینکه Settlement واقعی ثبت شود. چون این پول واقعی معلم‌هاست، هیچ فیکس خودکاری
در کار نیست — خروجی این اسکریپت ورودی بررسی دستی است.

تعریف یتیم (قوی): سطر Attendance با is_billed=True روی جلسه‌ی فعال، که معلمِ آن کلاس
«هیچ» رکورد Settlement در کل دیتابیس ندارد.
اطلاعات تکمیلی: مغایرت تعداد سطرهای بیل‌شده‌ی هر معلم با مجموع session_count تسویه‌هایش.

اجرا:
    cd Kharazmi_Server && python3 scripts/audit_is_billed_orphans.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (  # noqa: E402
    SessionLocal,
    Attendance,
    Course,
    SessionLog,
    Settlement,
    Student,
    Teacher,
)

SAMPLE_CAP = 20


def main() -> int:
    db = SessionLocal()
    try:
        billed = (
            db.query(Attendance, SessionLog, Course)
            .join(SessionLog, Attendance.session_id == SessionLog.id)
            .join(Course, SessionLog.course_id == Course.id)
            .filter(
                Attendance.is_billed == True,  # noqa: E712
                SessionLog.is_deleted == False,  # noqa: E712
            )
            .order_by(Course.teacher_id, SessionLog.date, Attendance.id)
            .all()
        )
        print(f"سطرهای Attendance بیل‌شده روی جلسات فعال: {len(billed)}")
        if not billed:
            print("موردی نیست. ✅")
            return 0

        by_teacher = {}
        for att, sess, course in billed:
            by_teacher.setdefault(course.teacher_id, []).append((att, sess))

        settlements = db.query(Settlement).all()
        settled_teachers = {s.teacher_id for s in settlements}
        settled_counts = {}
        for s in settlements:
            settled_counts[s.teacher_id] = settled_counts.get(s.teacher_id, 0) + (s.session_count or 0)

        orphans = {t: rows for t, rows in by_teacher.items() if t not in settled_teachers}
        print(f"معلم با سطر بیل‌شده: {len(by_teacher)} | معلم بدون هیچ Settlement (یتیم قوی): {len(orphans)}")

        for tid, rows in sorted(orphans.items()):
            t = db.query(Teacher).filter(Teacher.id == tid).first()
            tname = f"{t.first_name} {t.last_name}" if t else "نامشخص"
            print(f"\n[یتیم] معلم {tid} ({tname}) — {len(rows)} سطر بیل‌شده بدون تسویه:")
            for att, sess in rows[:SAMPLE_CAP]:
                st = db.query(Student).filter(Student.id == att.student_id).first()
                sname = f"{st.first_name} {st.last_name}" if st else "?"
                print(
                    f"  att={att.id} session={sess.id} date={sess.date} "
                    f"student={att.student_id}({sname}) status={att.status}"
                )
            if len(rows) > SAMPLE_CAP:
                print(f"  ... و {len(rows) - SAMPLE_CAP} سطر دیگر")

        print("\n[مغایرت شمارشی] (بیل‌شده در برابر مجموع session_count تسویه‌ها):")
        any_mismatch = False
        for tid, rows in sorted(by_teacher.items()):
            if tid in orphans:
                continue
            if len(rows) != settled_counts.get(tid, 0):
                any_mismatch = True
                print(f"  معلم {tid}: بیل‌شده={len(rows)} مجموع‌تسویه={settled_counts.get(tid, 0)}")
        if not any_mismatch:
            print("  مغایرتی نیست. ✅")

        if orphans:
            print("\nنتیجه: نیاز به بررسی دستی دارد (پول واقعی — فیکس خودکار ممنوع). ⚠️")
            return 2
        print("\nنتیجه: یتیم قوی نیست. ✅")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
