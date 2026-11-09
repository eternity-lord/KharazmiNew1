"""
بک‌فیل تراکنش‌های یتیم (orphan deposits) — لینک امن به ثبت‌نام + اصلاح total_paid.

پس‌زمینه: قبل از پیاده‌سازی «منبع حقیقت واحد بدهی»، پرداخت‌ها (type=deposit) با
enrollment_id=None ثبت می‌شدند و Enrollment.total_paid هیچ‌وقت آپدیت نمی‌شد.
این اسکریپت فقط موارد «قابل اثبات امن» را وصل می‌کند و بقیه را برای بررسی دستی گزارش می‌دهد.

قانون امن: شاگردی که «دقیقاً یک» سطر ثبت‌نام در کل دیتابیس دارد و آن یکی هم فعال
(حذف‌نشده) است → همه واریزی‌های یتیمش قطعاً مال همان ثبت‌نام است.
هر حالت دیگری (چند ثبت‌نام، ثبت‌نام حذف‌شده، ...) → فقط گزارش، بدون هیچ تغییری.

اجرا (پیش‌فرض فقط گزارش، بدون تغییر):
    cd Kharazmi_Server && python3 scripts/backfill_link_orphan_deposits.py
اعمال موارد امن:
    cd Kharazmi_Server && python3 scripts/backfill_link_orphan_deposits.py --apply
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SessionLocal, Student, Enrollment, Transaction  # noqa: E402

MONEY_IN_TYPES = ("deposit", "enrollment_payment", "tuition")


def main() -> int:
    parser = argparse.ArgumentParser(description="بک‌فیل امن تراکنش‌های یتیم")
    parser.add_argument("--apply", action="store_true", help="اعمال موارد امن (بدون این فلگ فقط گزارش)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        orphans = (
            db.query(Transaction)
            .filter(
                Transaction.type.in_(MONEY_IN_TYPES),
                Transaction.enrollment_id == None,  # noqa: E711
                Transaction.is_deleted == False,  # noqa: E712
                Transaction.is_reversed == False,  # noqa: E712
                Transaction.amount > 0,
            )
            .order_by(Transaction.student_id, Transaction.id)
            .all()
        )
        print(f"تعداد واریزی‌های یتیم (مثبت، فعال، بدون لینک): {len(orphans)}")
        if not orphans:
            print("کاری برای انجام نیست. ✅")
            return 0

        # گروه‌بندی بر اساس شاگرد
        by_student = {}
        for t in orphans:
            by_student.setdefault(t.student_id, []).append(t)

        safe_links = []   # (enrollment_id, [tx,...])
        manual = []       # (student_id, [tx,...], reason)

        for student_id, txs in sorted(by_student.items()):
            enroll_rows = db.query(Enrollment).filter(Enrollment.student_id == student_id).all()
            active = [e for e in enroll_rows if not e.is_deleted]
            total = sum(t.amount for t in txs)
            if len(enroll_rows) == 1 and len(active) == 1:
                safe_links.append((active[0], txs, total))
            else:
                if not enroll_rows:
                    reason = "هیچ ثبت‌نامی ندارد"
                elif not active:
                    reason = f"فقط {len(enroll_rows)} ثبت‌نام حذف‌شده دارد"
                else:
                    reason = f"{len(active)} ثبت‌نام فعال + {len(enroll_rows) - len(active)} حذف‌شده دارد"
                manual.append((student_id, txs, total, reason))

        print(f"\nموارد امن (تک‌ثبت‌نامی): {len(safe_links)} شاگرد")
        safe_total = 0
        for enroll, txs, total in safe_links:
            safe_total += total
            print(f"  - شاگرد {enroll.student_id} → ثبت‌نام #{enroll.id}: {len(txs)} تراکنش، جمع {total:,} تومان "
                  f"(total_paid فعلی: {enroll.total_paid or 0:,})")

        print(f"\nنیازمند بررسی دستی: {len(manual)} شاگرد")
        manual_total = 0
        for student_id, txs, total, reason in manual:
            manual_total += total
            st = db.query(Student).filter(Student.id == student_id).first()
            name = f"{st.first_name} {st.last_name}" if st else "نامشخص"
            tx_ids = ", ".join(f"#{t.id} ({t.amount:,})" for t in txs[:10])
            more = f" و {len(txs) - 10} تراکنش دیگر" if len(txs) > 10 else ""
            print(f"  - شاگرد {student_id} ({name}): {reason}؛ {len(txs)} تراکنش، جمع {total:,} تومان: {tx_ids}{more}")

        print(f"\nجمع مبالغ امن: {safe_total:,} تومان | جمع مبالغ دستی: {manual_total:,} تومان")

        if not args.apply:
            print("\nحالت گزارش (dry-run) — هیچ تغییری اعمال نشد. برای اعمال موارد امن، با --apply اجرا کن.")
            return 0

        if not safe_links:
            print("\nمورد امنی برای اعمال وجود ندارد.")
            return 0

        # اعمال موارد امن با قفل ردیفی، در یک تراکنش
        applied_txs = 0
        applied_amount = 0
        for enroll, txs, total in safe_links:
            locked = db.query(Enrollment).filter(Enrollment.id == enroll.id).with_for_update().first()
            if locked is None or locked.is_deleted:
                print(f"  ⚠️ ثبت‌نام #{enroll.id} هم‌زمان حذف شد؛ رد شد.")
                continue
            # بازبینی نهایی: هنوز تک‌ثبت‌نامی است؟
            still = db.query(Enrollment.id).filter(Enrollment.student_id == locked.student_id).all()
            if len(still) != 1:
                print(f"  ⚠️ شاگرد {locked.student_id} دیگر تک‌ثبت‌نامی نیست؛ رد شد.")
                continue
            for t in txs:
                t.enrollment_id = locked.id
                applied_txs += 1
            locked.total_paid = (locked.total_paid or 0) + total
            applied_amount += total
        db.commit()
        print(f"\n✅ اعمال شد: {applied_txs} تراکنش ({applied_amount:,} تومان) به ثبت‌نام‌های تک‌ثبت‌نامی لینک شد.")
        print("موارد دستی بدون تغییر باقی ماندند.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
