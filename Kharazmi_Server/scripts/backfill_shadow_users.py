"""
بک‌فیل Userهای سایه (H2) — لینک امن شاگردان موجود به ردیف users.

پس‌زمینه: سشن دانش‌آموز/ولی با user_id=Student.id ساخته می‌شد در حالی که
UserSession.user_id باید به users.id اشاره کند. از این به بعد هر Student دو
سایه دارد (نقش student و parent) و سشن‌ها به آیدی سایه‌ها اشاره می‌کنند.

این اسکریپت برای همه‌ی Studentهایی که user_id یا parent_user_id ندارند،
سایه‌ی گمشده را می‌سازد و لینک می‌کند. idempotent است (اجرای دوباره بی‌اثر).

اجرا (پیش‌فرض فقط گزارش، بدون تغییر):
    cd Kharazmi_Server && python3 scripts/backfill_shadow_users.py
اعمال واقعی:
    cd Kharazmi_Server && python3 scripts/backfill_shadow_users.py --apply
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SessionLocal, Student  # noqa: E402
from dependencies import ensure_student_shadow_users  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="بک‌فیل امن User سایه شاگردان")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="اعمال واقعی تغییرات (بدون این فلگ فقط گزارش)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        students = db.query(Student).order_by(Student.id).all()
        missing_student = [s for s in students if not s.user_id]
        missing_parent = [s for s in students if not s.parent_user_id]

        print(f"کل شاگردان: {len(students)}")
        print(f"بدون سایه student: {len(missing_student)} {[s.id for s in missing_student]}")
        print(f"بدون سایه parent: {len(missing_parent)} {[s.id for s in missing_parent]}")

        if not args.apply:
            print("حالت گزارش (dry-run) — تغییری اعمال نشد. برای اعمال: --apply")
            return 0

        for s in students:
            ensure_student_shadow_users(db, s)
        db.commit()
        print(f"انجام شد: سایه‌های گمشده ساخته و لینک شدند.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
