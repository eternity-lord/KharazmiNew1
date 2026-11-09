"""
بک‌فیل branch_id تراکنش‌های شارژ جلسه — پیش‌فرض فقط گزارش.

پس‌زمینه: بک‌فیل استارتاپ ممکن است branch_id=1 اشتباه روی شارژها گذاشته باشد؛
NULLها هم قطعاً ناقص‌اند. قانون درست (H7/Bug 9): شعبه‌ی شاگرد، fallback شعبه‌ی کلاس.

گزارش (پیش‌فرض):
  - گروه NULL: branch پیشنهادی برای هر تراکنش.
  - گروه branch=1: فقط آن‌هایی که پیشنهاد H7 مخالف ۱ است (۱های درست، نویز نیستند).
  - گروه نامشخص: نه شاگرد نه کلاس پیدا نشد → فقط دستی.

اعمال محافظه‌کار (--apply): فقط گروه NULL با پیشنهاد بدون‌ابهام (تک‌منبع یا توافق هر دو منبع).
گروه «۱ مشکوک» هرگز خودکار عوض نمی‌شود (ممکن است ۱ واقعی باشد) → دستی.

اجرا (فقط گزارش):
    cd Kharazmi_Server && python3 scripts/backfill_session_charge_branch.py
اعمال NULLهای امن:
    cd Kharazmi_Server && python3 scripts/backfill_session_charge_branch.py --apply
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (  # noqa: E402
    Course,
    Enrollment,
    SessionLocal,
    SessionLog,
    Student,
    Transaction,
)

SAMPLE_CAP = 30


def propose_branch(db, txn):
    """(student_branch, course_branch) — هر کدام ممکن است None باشد."""
    stu_branch = None
    sid = txn.student_id
    if sid is None and txn.enrollment_id:
        en = db.query(Enrollment).filter(Enrollment.id == txn.enrollment_id).first()
        sid = en.student_id if en else None
    if sid:
        st = db.query(Student).filter(Student.id == sid).first()
        stu_branch = st.branch_id if st else None

    course_branch = None
    cid = txn.course_id
    if cid is None and txn.session_id:
        sess = db.query(SessionLog).filter(SessionLog.id == txn.session_id).first()
        cid = sess.course_id if sess else None
    if cid:
        c = db.query(Course).filter(Course.id == cid).first()
        course_branch = c.branch_id if c else None

    proposed = stu_branch if stu_branch is not None else course_branch
    agree = (stu_branch is None or course_branch is None or stu_branch == course_branch)
    return proposed, agree, stu_branch, course_branch


def main() -> int:
    parser = argparse.ArgumentParser(description="بک‌فیل branch_id شارژهای جلسه")
    parser.add_argument("--apply", action="store_true", help="پر کردن NULLهای امن (۱های مشکوک هرگز)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        txns = (
            db.query(Transaction)
            .filter(
                Transaction.type == "session_charge",
                Transaction.is_deleted == False,  # noqa: E712
            )
            .order_by(Transaction.id)
            .all()
        )
        print(f"تراکنش‌های session_charge فعال: {len(txns)}")

        nulls, suspect_ones, unknown = [], [], []
        for t in txns:
            proposed, agree, sb, cb = propose_branch(db, t)
            if t.branch_id is None:
                (nulls if proposed is not None else unknown).append((t, proposed, agree, sb, cb))
            elif t.branch_id == 1 and proposed is not None and proposed != 1:
                suspect_ones.append((t, proposed, agree, sb, cb))

        print(f"NULL: {len(nulls)} | branch=1 مشکوک (پیشنهاد≠۱): {len(suspect_ones)} | نامشخص: {len(unknown)}")

        for title, group in (("NULL", nulls), ("۱ مشکوک", suspect_ones), ("نامشخص", unknown)):
            if not group:
                continue
            print(f"\n[{title}]")
            for t, proposed, agree, sb, cb in group[:SAMPLE_CAP]:
                flag = "" if agree else " [اختلاف شعبه شاگرد/کلاس!]"
                print(
                    f"  txn={t.id} date={t.date} amount={t.amount} branch={t.branch_id} "
                    f"→ پیشنهاد={proposed} (شاگرد={sb} کلاس={cb}){flag}"
                )
            if len(group) > SAMPLE_CAP:
                print(f"  ... و {len(group) - SAMPLE_CAP} مورد دیگر")

        if not args.apply:
            print("\nحالت گزارش (بدون تغییر). ✅")
            return 0

        safe = [(t, p) for t, p, agree, sb, cb in nulls if agree]
        skipped = len(nulls) - len(safe)
        for t, p in safe:
            t.branch_id = p
        db.commit()
        print(f"\nاعمال شد: {len(safe)} NULL پر شد | رد شد (اختلاف منبع): {skipped} | "
              f"۱های مشکوک دست‌نخورده (دستی): {len(suspect_ones)}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
