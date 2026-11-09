"""
ممیزی تاریخ‌های نامعتبر/pseudo-Jalali — فقط گزارش، بدون هیچ تغییری.

پس‌زمینه (H3): ستون‌های تاریخ رشته‌ای‌اند و مخلوط شمسی/میلادی‌اند. مبدل مرکزی
today_summary.parse_project_date هر دو فرمت معتبر را می‌فهمد؛ هرچه آن نفهمد —
نه شمسی واقعی نه میلادی معتبر — این‌جا گزارش می‌شود (pseudo-Jalali یا آشغال).

دامنه (مرتبط با پول/حضور): Transaction.date ،SessionLog.date ،Installment.due_date.
تصحیح تاریخ خودکار ممکن نیست (مقدار درست از روی غلط قابل استنتاج نیست) → فقط دستی.

اجرا:
    cd Kharazmi_Server && python3 scripts/audit_pseudo_jalali_dates.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Installment, SessionLocal, SessionLog, Transaction  # noqa: E402
from today_summary import parse_project_date  # noqa: E402

SAMPLE_CAP = 20
JALALI_LIKE = re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$")


def classify(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return "خالی/NULL"
    if isinstance(value, str) and JALALI_LIKE.match(value.strip()):
        return "شبه‌شمسی (فرمت درست، مقدار نامعتبر)"
    return "فرمت ناشناخته"


def audit_column(db, model, column, label, extra_filter=None):
    q = db.query(model)
    if extra_filter is not None:
        q = q.filter(extra_filter)
    rows = q.all()
    bad = []
    for r in rows:
        v = getattr(r, column)
        try:
            ok = parse_project_date(v) is not None
        except Exception:
            ok = False
        if not ok:
            bad.append((r.id, v))
    print(f"\n[{label}] کل={len(rows)} نامعتبر={len(bad)}")
    for rid, v in bad[:SAMPLE_CAP]:
        print(f"  id={rid} مقدار={v!r} ← {classify(v)}")
    if len(bad) > SAMPLE_CAP:
        print(f"  ... و {len(bad) - SAMPLE_CAP} مورد دیگر")
    return len(bad)


def main() -> int:
    db = SessionLocal()
    try:
        total = 0
        total += audit_column(db, Transaction, "date", "transactions.date",
                              Transaction.is_deleted == False)  # noqa: E712
        total += audit_column(db, SessionLog, "date", "session_logs.date",
                              SessionLog.is_deleted == False)  # noqa: E712
        total += audit_column(db, Installment, "due_date", "installments.due_date",
                              Installment.is_deleted == False)  # noqa: E712
        print(f"\nجمع نامعتبرها: {total} {'(نیاز به بررسی دستی ⚠️)' if total else '✅'}")
        return 2 if total else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
